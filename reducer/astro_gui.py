from collections import OrderedDict
from contextlib import ExitStack
import errno
import os
import warnings

from astropy import units as u
from astropy.io import fits
from astropy.modeling import models
from astropy.wcs import WCS
import ccdproc

import numpy as np

from . import gui

import ipywidgets as widgets
from traitlets import Any, link

__all__ = [
    'Reduction',
    'Combiner',
    'CosmicRaySettings',
    'Slice',
    'CalibrationStep',
    'BiasSubtract',
    'DarkSubtract',
    'FlatCorrect',
    'Overscan',
    'Trim'
]

DEFAULT_IMAGE_UNIT = "adu"

# The dictionary below is used to map the dtype of the image being
# reduced to the dtype of the output. The assumption is that the output
# is typically some kind of floating point, but that there is no need
# for very high precision output given relatively low resolution
# input.
REDUCE_IMAGE_DTYPE_MAPPING = {
    'uint8': 'float32',
    'int8': 'float32',
    'uint16': 'float32',
    'int16': 'float32',
    'float32': 'float32',
    'uint32': 'float64',
    'int32': 'float64',
    'float64': 'float64'
}

# The limit below, in bytes, is used by the combining function to decide how
# large a chunk of the images to work on at one time. It is not the peak memory
# use of the combine: measured peak is roughly 2 to 3 times this limit plus the
# size of one output image. The value below therefore keeps the combine to a
# few hundred MB even for 4096 x 4096 images.
DEFAULT_MEMORY_LIMIT = 5e7  # bytes


def _no_uncertainty(data, axis=0):
    """
    Uncertainty function for ``ccdproc.combine`` that does no work; used
    when the uncertainty it produces would be discarded anyway.
    """
    return np.zeros(data.shape[1:], dtype=data.dtype)


# Names of the extensions in which CCDData keeps anything other than the image.
_CCDDATA_EXTENSIONS = {'MASK', 'UNCERT', 'PSF'}

_COMBINE_METHODS = {
    'average': 'average_combine',
    'median': 'median_combine',
    'sum': 'sum_combine',
}


def _unit_from_header(header):
    """
    Unit of the image with this header, found the way ``CCDData.read`` finds
    it, or ``None`` if the header has no usable ``BUNIT``.
    """
    unit_string = header.get('bunit')
    if not unit_string or not isinstance(unit_string, str):
        return None
    if unit_string.strip().lower() == 'adu':
        unit_string = unit_string.lower()
    unit_string = ccdproc.CCDData.known_invalid_fits_unit_strings.get(
        unit_string, unit_string)
    try:
        return u.Unit(unit_string)
    except ValueError:
        return None


def _wcs_from_header(header):
    """
    WCS of the image with this header, or ``None`` if the header has no WCS,
    which is what ``CCDData.read`` would attach to the image.
    """
    try:
        wcs = WCS(header)
    except Exception:
        return None
    if not wcs.wcs.ctype[0]:
        return None
    return wcs


def _combine_in_bands(file_list,
                      method='average',
                      scale=None,
                      mem_limit=16e9,
                      minmax_clip=False,
                      minmax_clip_min=None,
                      minmax_clip_max=None,
                      sigma_clip=False,
                      sigma_clip_low_thresh=3,
                      sigma_clip_high_thresh=3,
                      sigma_clip_func=np.ma.mean,
                      sigma_clip_dev_func=np.ma.std,
                      dtype=None,
                      combine_uncertainty_function=None):
    """
    Combine images the way ``ccdproc.combine`` does, but open each file only
    once and read it one band of rows at a time.

    Parameters
    ----------

    file_list : list of str
        Paths of the FITS files to combine.

    method, scale, mem_limit, dtype, combine_uncertainty_function : optional
        The same meaning, and the same defaults, as the arguments of
        ``ccdproc.combine`` with the same names.

    minmax_clip, minmax_clip_min, minmax_clip_max : optional
        As in ``ccdproc.combine``.

    sigma_clip, sigma_clip_low_thresh, sigma_clip_high_thresh : optional
        As in ``ccdproc.combine``.

    sigma_clip_func, sigma_clip_dev_func : optional
        As in ``ccdproc.combine``.

    Returns
    -------

    combined : `ccdproc.CCDData` or None
        The combined image, with the header, unit and WCS of the first file
        and no mask or uncertainty. ``None`` if these files cannot be
        combined this way, in which case nothing has been done and
        ``ccdproc.combine`` should be used instead. That is the case unless
        every file has a two-dimensional image in its first HDU, a ``BUNIT``,
        the same unit and shape as the others, and no mask, uncertainty or
        PSF extension. It is also the case if there are too many files to
        have them all open at once.

    Notes
    -----

    ``ccdproc.combine`` limits memory by combining a piece of the image at a
    time, but it calls ``CCDData.read`` on every file for every piece. The
    read is lazy, so that costs little memory, but it costs the time it
    takes to parse the header and build a WCS, and the number of pieces
    grows with the number of files. Combining *N* files therefore takes time
    proportional to *N* squared: 40 frames that are 4096 x 4096 take several
    minutes with a ``mem_limit`` of 5e7. See
    https://github.com/astropy/ccdproc/issues/1012.

    Here each file is opened once and each band is read with ``hdu.section``.
    The bands are the height that ``ccdproc.combine`` would use for the same
    ``mem_limit``, each one is combined by a ``ccdproc.Combiner`` set up the
    way ``ccdproc.combine`` would set it up, and every pixel of the result
    depends only on that pixel in the inputs (and, with ``scale``, on a
    number found from each whole image beforehand), so the combined image is
    identical. The one difference is that a band is never less than a whole
    row, where ``ccdproc.combine`` would go on to split the rows if
    ``mem_limit`` were too small for even one row of every image.
    """
    if method not in _COMBINE_METHODS:
        raise ValueError(f"unrecognised combine method : {method}.")

    if dtype is None:
        dtype = np.float64

    with ExitStack() as stack:
        try:
            hdu_lists = [stack.enter_context(fits.open(a_file, memmap=False))
                         for a_file in file_list]
        except OSError as err:
            if err.errno != errno.EMFILE:
                raise
            # Too many open files; ccdproc.combine opens one at a time.
            return None

        for hdu_list in hdu_lists:
            if _CCDDATA_EXTENSIONS & {hdu.name.upper() for hdu in hdu_list}:
                return None

        hdus = [hdu_list[0] for hdu_list in hdu_lists]
        shapes = {hdu.shape for hdu in hdus}
        units = [_unit_from_header(hdu.header) for hdu in hdus]
        if (len(shapes) != 1 or len(hdus[0].shape) != 2 or
                any(unit is None or unit != units[0] for unit in units)):
            return None

        ny, nx = hdus[0].shape

        if callable(scale):
            # The function is applied to each whole image, one at a time.
            # Read the image as a section too: ``hdu.data`` would keep the
            # image on the HDU, and for integers with a BSCALE and a BLANK
            # it leaves the HDU unable to read a section afterwards.
            scale = np.array([scale(hdu.section[:, :]) for hdu in hdus])

        # The same arithmetic as ccdproc.combine, which counts an uncertainty
        # with the dtype of the data and a one byte mask for each image.
        memory_factor = (3 if method == 'median' else 2) * 1.3
        size_of_an_image = ny * nx * (2 * np.dtype(dtype).itemsize + 1)
        n_chunks = int(memory_factor * size_of_an_image * len(hdus) /
                       mem_limit) + 1
        band_rows = max(1, int(ny / n_chunks))

        combine_kwds = {}
        if combine_uncertainty_function is not None:
            combine_kwds['uncertainty_func'] = combine_uncertainty_function

        result = np.empty((ny, nx), dtype=dtype)
        for start in range(0, ny, band_rows):
            stop = min(ny, start + band_rows)
            bands = [ccdproc.CCDData(hdu.section[start:stop, :],
                                     unit=units[0])
                     for hdu in hdus]
            band_combiner = ccdproc.Combiner(bands, dtype=dtype)
            if scale is not None:
                band_combiner.scaling = scale
            if minmax_clip:
                band_combiner.minmax_clipping(min_clip=minmax_clip_min,
                                              max_clip=minmax_clip_max)
            if sigma_clip:
                band_combiner.sigma_clipping(
                    low_thresh=sigma_clip_low_thresh,
                    high_thresh=sigma_clip_high_thresh,
                    func=sigma_clip_func,
                    dev_func=sigma_clip_dev_func
                )
            combined_band = getattr(band_combiner,
                                    _COMBINE_METHODS[method])(**combine_kwds)
            result[start:stop] = combined_band.data
            # Free the band before reading the next one.
            del bands, band_combiner, combined_band

        header = hdus[0].header.copy()

    return ccdproc.CCDData(result, unit=units[0], meta=header,
                           wcs=_wcs_from_header(header))


DEFAULT_IMAGETYPE_MAP = {
    'bias': 'BIAS',
    'dark': 'DARK',
    'flat': 'FLAT',
    'light': 'LIGHT'
}


class ReducerBase(gui.ToggleGo):
    """
    Base class for reduction and combination widgets that provides a couple
    of properties common to both.

    Parameters
    ----------

    apply_to : dict
        Key-value pair(s) that select images that will be acted on by the
        widget.

    destination : str
        Directory in which reduced images will be stored.

    imagetype_map : dict
        Key-value pairs where the keys are "bias", "dark", "flat", and "light"
        and the values are the values of the "imagetyp" keyword that will be
        used to select the appropriate images.
    """
    def __init__(self, *arg, **kwd):
        self._apply_to = kwd.pop('apply_to', None)
        self._destination = kwd.pop('destination', None)
        self._imagetype_map = kwd.pop('imagetype_map', DEFAULT_IMAGETYPE_MAP)
        self._exposure_time_keyword = kwd.pop('exposure_keyword', 'exposure')
        super(ReducerBase, self).__init__(*arg, **kwd)

    @property
    def destination(self):
        return self._destination

    @property
    def apply_to(self):
        """
        Do some magical changing of the "imagetyp" keyword to the value
        that will be used to select the appropriate images.
        """
        return_value = dict(self._apply_to)
        for k, v in self._apply_to.items():
            if k == 'imagetyp':
                return_value[k] = self._imagetype_map[v]
        return return_value

    @property
    def imagetype_map(self):
        return self._imagetype_map


class Reduction(ReducerBase):
    """
    Primary widget for performing a logical reduction step (e.g. dark
    subtraction or flat correction).
    """
    def __init__(self, *arg, **kwd):
        allow_flat = kwd.pop('allow_flat', True)
        allow_dark = kwd.pop('allow_dark', True)
        allow_bias = kwd.pop('allow_bias', True)
        allow_cosmic_ray = kwd.pop('allow_cosmic_ray', False)
        allow_copy = kwd.pop('allow_copy_only', True)
        self.image_collection = kwd.pop('input_image_collection', None)
        self._master_source = kwd.pop('master_source', None)
        super(Reduction, self).__init__(*arg, **kwd)
        self._overscan = Overscan(description='Subtract overscan?')
        self._trim = Trim(description='Trim (specify region to keep)?')
        self._cosmic_ray = CosmicRaySettings()
        self._bias_calib = BiasSubtract(master_source=self._master_source, imagetype_map=self.imagetype_map)
        self._dark_calib = DarkSubtract(master_source=self._master_source, imagetype_map=self.imagetype_map, exposure_keyword=self._exposure_time_keyword)
        self._flat_calib = FlatCorrect(master_source=self._master_source, imagetype_map=self.imagetype_map)

        if allow_copy:
            self._copy_only = CopyFiles()
            self.add_child(self._copy_only)
        else:
            self._copy_only = None

        self.add_child(self._overscan)
        self.add_child(self._trim)

        if allow_bias:
            self.add_child(self._bias_calib)
        if allow_dark:
            self.add_child(self._dark_calib)
        if allow_flat:
            self.add_child(self._flat_calib)

        if allow_cosmic_ray:
            self.add_child(self._cosmic_ray)

        if self._copy_only:
            self._copy_only._state_monitor.on_trait_change(
                self._disable_all_others(),
                str('value')
            )
        self.visible = kwd.pop('visible', True)

    def action(self):
        if not self.image_collection:
            raise ValueError("No images to reduce")
        self.progress_bar.visible = True
        self.progress_bar.layout.visbility = 'visible'
        self.progress_bar.layout.display = 'flex'

        # Refresh in case files have been added since the widget was created.
        self.image_collection.refresh()

        # Only refresh the master_source if it exists. No need to error check
        # the main image_collection because a sensible error is raised if it
        # does not exist.
        if self._master_source:
            self._master_source.refresh()

        # Suppress warnings that come up here...mostly about HIERARCH keywords
        warnings.filterwarnings('ignore')
        try:
            n_files = \
                len(self.image_collection.files_filtered(**self.apply_to))
            current_file = 0
            for hdu, fname in self.image_collection.hdus(return_fname=True,
                                                         save_location=self.destination,
                                                         **self.apply_to):
                current_file += 1
                try:
                    unit = hdu.header['BUNIT']
                except KeyError:
                    unit = DEFAULT_IMAGE_UNIT
                # Do the reduction in the dtype the output will be written
                # in. Several of the ccdproc operations promote the data to
                # float64, which doubles the memory each image needs, so the
                # data is cast back after each step below.
                desired_dtype = REDUCE_IMAGE_DTYPE_MAPPING[hdu.data.dtype.name]
                # Assign back to the HDU so the original integer array is
                # released now rather than after the last calibration step.
                hdu.data = hdu.data.astype(desired_dtype, copy=False)
                ccd = ccdproc.CCDData(hdu.data, meta=hdu.header, unit=unit)
                for child in self.container.children:
                    if not child.toggle.value:
                        # Nothing to do for this child, so keep going.
                        continue
                    ccd = child.action(ccd)
                    if ccd.data.dtype != desired_dtype:
                        ccd.data = ccd.data.astype(desired_dtype)

                hdu_tmp = ccd.to_hdu()[0]
                hdu.header = hdu_tmp.header
                hdu.data = hdu_tmp.data

                # Workaround to ensure uint16 images are handled properly.
                if 'bzero' in hdu.header:
                    # Check for the unsigned int16 case, and if our data type
                    # is no longer uint16, delete BZERO and BSCALE
                    header_unsigned_int = ((hdu.header['bscale'] == 1) and
                                           (hdu.header['bzero'] == 32768))
                    if (header_unsigned_int and
                        (hdu.data.dtype != np.dtype('uint16'))):

                        del hdu.header['bzero'], hdu.header['bscale']

                self.progress_bar.description = \
                    ("Processed file {} of {}".format(current_file, n_files))
                self.progress_bar.value = current_file / n_files

                # Make sure this image is gone before the next one is read.
                del ccd, hdu_tmp
        except IOError:
            print("One or more of the reduced images already exists. Delete "
                  "those files and try again. This notebook will NOT "
                  "overwrite existing files.")
        finally:
            # Master images can be large, so do not keep them past the end of
            # the reduction. They are re-read, cheaply, on the next run.
            for child in self.container.children:
                getattr(child, '_image_cache', {}).clear()
            self.progress_bar.visible = False
            self.progress_bar.layout.display = 'none'

    def _disable_all_others(self):
        if not self._copy_only:
            return None

        def handler():
            all_but_copy = [c for c in self.container.children
                            if c is not self._copy_only]

            if self._copy_only._state_monitor.value:
                for child in all_but_copy:
                    print(child.description)
                    child.disabled = True
            else:
                for child in all_but_copy:
                    child.disabled = False

        return handler


class Clipping(gui.ToggleContainer):
    """docstring for Clipping"""
    def __init__(self, *args, **kwd):
        super(Clipping, self).__init__(*args, **kwd)
        self._min_max = gui.ToggleMinMax(description="Clip by min/max?")
        self._sigma_clip = gui.ToggleMinMax(description="Sigma clip?")
        self.add_child(self._min_max)
        self.add_child(self._sigma_clip)
        self.format()

    @property
    def min_max(self):
        if self._min_max.toggle.value:
            return self._min_max
        else:
            return False

    @property
    def sigma_clip(self):
        if self._sigma_clip.toggle.value:
            return self._sigma_clip
        else:
            return False

    @property
    def is_sane(self):
        # If not selected, sanity state does not matter...
        if not self.toggle.value:
            return None

        # It makes no sense to have selected clipping but not a clipping
        # method....
        sanity = (self._min_max.toggle.value or
                  self._sigma_clip.toggle.value)

        # For min_max clipping, maximum must be greater than minimum.
        if self._min_max.toggle.value:
            sanity = sanity and (self._min_max.max > self._min_max.min)

        # For sigma clipping there is no relationship  between maximum
        # and minimum because both are number of deviations above/below
        # central value, but values of 0 make no sense

        if self._sigma_clip.toggle.value:
            sanity = (sanity and
                      self._sigma_clip.min != 0 and
                      self._sigma_clip.max != 0)

        return sanity

    def format(self):
        super(Clipping, self).format()
        self._sigma_clip.format()
        self._min_max.format()


def override_str_factory(obj):
    """
    Override the __str__ method for widget classes

    Parameters
    ----------

    obj : object
        An IPython widget instance

    Returns
    -------

    new_object : IPython widget with string method overridden
    """

    def new_str_method(self):
        return ": ".join([str(self.description), str(self.value)])

    # This used to use type create a new class, along these lines:
    #   https://stackoverflow.com/questions/5918003/python-override-str-in-an-exception-instance
    #
    # That no longer seems to work, because using the class of the widget from type give a traitlets
    # object not an ipywidgets object, and the value is no longer related to the UI setting.
    #
    # This new way works, but changes the __str__ for every widget type it touches.
    # This whole thing really needs a re-design.

    original_class = type(obj)
    original_class.__str__ = new_str_method
    return obj


class Combine(gui.ToggleContainer):
    """
    Represent combine choices and actions.
    """
    def __init__(self, *args, **kwd):
        super(Combine, self).__init__(*args, **kwd)
        self._combine_option = override_str_factory(
            widgets.ToggleButtons(description="Combination method:",
                                  options=['Average', 'Median'],
                                  style={'description_width': 'initial'})
        )

        self.add_child(self._combine_option)
        self._scaling = gui.ToggleContainer(description="Scale before combining?")
        scal_desc = "Which should scale to same value?"
        self._scale_by = override_str_factory(
            widgets.RadioButtons(description=scal_desc,
                                 options=['mean', 'median'],
                                 style={'description_width': 'initial'})
        )
        self._scaling.add_child(self._scale_by)
        self.add_child(self._scaling)

    @property
    def method(self):
        return self._combine_option.value

    @property
    def scaling_func(self):
        if not self._scaling.toggle.value:
            return None
        if self._scale_by.value == 'mean':
            return lambda arr: 1 / np.ma.average(arr)
        elif self._scale_by.value == 'median':
            return lambda arr: 1 / np.ma.median(arr)

    @property
    def is_sane(self):
        if not self.toggle.value:
            return None
        else:
            # In this case, the only options presented are sane ones
            return True


class GroupBy(gui.ToggleContainer):
    def __init__(self, *args, **kwd):
        self._image_source = kwd.pop('image_source', None)
        input_value = kwd.pop('value', '')
        super(GroupBy, self).__init__(*args, **kwd)
        self._keyword_list = override_str_factory(
            widgets.Text(description='Keywords (comma-separated)',
                         value=input_value,
                         style={'description_width': 'initial'})
        )
        self.add_child(self._keyword_list)
        if input_value:
            self.toggle.value = True

    @property
    def value(self):
        return self._keyword_list.value

    def groups(self, apply_to):
        if not (self.toggle.value and self.value):
            # Return an empty dictionary by default if there is no grouping
            return [{}]

        # remember, the rest is really an else to the above...
        from copy import deepcopy
        keywords = [k.strip() for k in self.value.split(',')]
        # Yuck...need to use an internal method to get the mask I need.
        tmp_coll = deepcopy(self._image_source)
        tmp_coll._find_keywords_by_values(**apply_to)
        mask = tmp_coll.summary['file'].mask
        # Note the logical not below; mask indicates which values
        # should be EXCLUDED.
        filtered_table = tmp_coll.summary[~mask]
        grouped_table = filtered_table.group_by(keywords)
        combine_groups = grouped_table.groups.keys
        group_list = []
        for row in combine_groups:
            d = {c: row[c] for c in combine_groups.colnames}
            group_list.append(d)

        return group_list


class Combiner(ReducerBase):
    """
    Widget for displaying options for ccdproc.Combiner.

    Parameters
    ----------

    description : str, optional
        Text displayed next to check box for selecting options.

    mem_limit : float, optional
        Maximum memory, in bytes, that should be used for the band of the
        images being combined at one time; it sets the height of the band the
        way ``ccdproc.combine`` sets the size of its chunks. If not set, the
        module-level ``DEFAULT_MEMORY_LIMIT`` is used instead.
    """
    def __init__(self, *args, **kwd):
        group_by_in = kwd.pop('group_by', '')
        self._image_source = kwd.pop('image_source', None)
        self._file_base_name = kwd.pop('file_name_base', 'master')
        self._mem_limit = kwd.pop('mem_limit', None)
        super(Combiner, self).__init__(*args, **kwd)
        self._clipping_widget = \
            Clipping(description="Clip before combining?")
        self._combine_method = \
            Combine(description="Combine images?")

        self.add_child(self._clipping_widget)
        self.add_child(self._combine_method)

        self._group_by = GroupBy(description='Group by:',
                                       value=group_by_in,
                                       image_source=self._image_source)
        self.add_child(self._group_by)

        self._combined_path = None

    @property
    def combined(self):
        """
        The most recently combined image, read from disk each time this is
        accessed, or ``None`` if no image has been combined yet.

        The image is not kept in memory because it can be large.
        """
        if self._combined_path is None:
            return None
        try:
            return ccdproc.CCDData.read(self._combined_path)
        except ValueError:
            return ccdproc.CCDData.read(self._combined_path,
                                        unit=DEFAULT_IMAGE_UNIT)

    @property
    def image_source(self):
        return self._image_source

    @property
    def is_sane(self):
        # Start with the default sanity determination...
        sanity = super(Combiner, self).is_sane
        # ...but flip to insane if combination is not selected.
        sanity = sanity and self._combine_method.toggle.value
        return sanity

    def format(self):
        super(Combiner, self).format()
        self._clipping_widget.format()
        # self.progress_bar.add_class('active progress-info progress-striped')

        # ADD STRIPES
        self.progress_bar.bar_style = 'info'

        # Yuck. _dom_classes is a tuple, so make it a list, append to it, then
        # reset. Similar to the way add_child handles children.
        old_dom_classes = list(self.progress_bar._dom_classes)
        if 'prgress-striped' not in old_dom_classes:
            old_dom_classes.append('progress-striped')
            self.progress_bar._dom_classes = old_dom_classes

    def action(self):
        self.progress_bar.visible = True
        self.progress_bar.value = 1.0
        self.progress_bar.layout.visbility = 'visible'
        self.progress_bar.layout.display = 'flex'

        # Refresh image collection in case files were added after widget was
        # created.
        self.image_source.refresh()

        groups_to_combine = self._group_by.groups(self.apply_to)
        n_groups = len(groups_to_combine)
        for idx, combo_group in enumerate(groups_to_combine):
            self.progress_bar.description = \
                ("Processing {} of {} "
                 "(may take several minutes)".format(idx + 1, n_groups))
            combined = self._action_for_one_group(combo_group)
            name_addons = ['_'.join([str(k), str(v)])
                           for k, v in combo_group.items()]
            fname = [self._file_base_name]
            fname.extend(name_addons)
            fname = '_'.join(fname) + '.fit'
            dest_path = os.path.join(self.destination, fname)
            combined.write(dest_path)
            self._combined_path = dest_path
            # The combined image can be large, so do not hang on to it. The
            # ``combined`` property re-reads it from disk if it is needed.
            del combined
        self.progress_bar.visible = False
        self.progress_bar.layout.display = 'none'

    def _action_for_one_group(self, filter_dict=None):
        combined_dict = self.apply_to.copy()
        if filter_dict is not None:
            combined_dict.update(filter_dict)

        file_list = [os.path.join(self.image_source.location, f) for f in
                     self.image_source.files_filtered(**combined_dict)]

        combine_keyword_args = {
            'minmax_clip': self._clipping_widget.min_max,
            'sigma_clip': self._clipping_widget.sigma_clip,
        }

        if self._combine_method.method == 'Average':
            combine_keyword_args['method'] = 'average'
        elif self._combine_method.method == 'Median':
            combine_keyword_args['method'] = 'median'

        if combine_keyword_args['minmax_clip']:
            combine_keyword_args['minmax_clip_min'] = \
                self._clipping_widget.min_max.min
            combine_keyword_args['minmax_clip_max'] = \
                self._clipping_widget.min_max.max

        if combine_keyword_args['sigma_clip']:
            combine_keyword_args['sigma_clip_low_thresh'] = \
                self._clipping_widget.sigma_clip.min
            combine_keyword_args['sigma_clip_low_thresh'] = \
                self._clipping_widget.sigma_clip.min
            # Use the names of the clipping functions rather than the
            # functions themselves; ccdproc has a faster, lower memory path
            # for these.
            combine_keyword_args['sigma_clip_func'] = 'median'
            combine_keyword_args['sigma_clip_dev_func'] = 'mad_std'

        if self._combine_method.scaling_func:
            combine_keyword_args['scale'] = self._combine_method.scaling_func

        # Read only the header and the extension names of one of the images
        # being combined. Reading the image data too, as this used to, costs
        # as much memory as one image and nothing but the header is needed
        # here. CCDData keeps the mask and uncertainty in extensions with
        # these names; looking at the names does not read any image data.
        with fits.open(file_list[0]) as sample_hdulist:
            sample_header = sample_hdulist[0].header
            extension_names = [h.name.lower() for h in sample_hdulist]
        sample_has_mask = 'mask' in extension_names
        sample_has_uncertainty = 'uncert' in extension_names

        # Determine the dtype of the images being combined from the header so
        # that the combined image can be accumulated in an appropriate dtype
        # instead of the float64 ccdproc uses by default. Signed and unsigned
        # integers of the same width map to the same dtype, so BZERO does not
        # need to be checked.
        combine_dtype = REDUCE_IMAGE_DTYPE_MAPPING.get(
            fits.BITPIX2DTYPE[sample_header['bitpix']], 'float64')

        # ccdproc computes an uncertainty for the combined image whether or
        # not the inputs have one. For a median combine that uncertainty is
        # a MAD-based estimate that costs about as much as the combine
        # itself, and it is thrown away below when the inputs have no
        # uncertainty, so replace it with something trivial in that case.
        if (combine_keyword_args.get('method') == 'median' and
                not sample_has_mask and not sample_has_uncertainty):
            combine_keyword_args['combine_uncertainty_function'] = \
                _no_uncertainty

        # Use the limit set for this widget if there is one, and otherwise the
        # module-level default. The default is deliberately looked up here,
        # when the combine happens, so that setting
        # ``astro_gui.DEFAULT_MEMORY_LIMIT`` takes effect.
        mem_limit = self._mem_limit
        if mem_limit is None:
            mem_limit = DEFAULT_MEMORY_LIMIT

        # ccdproc.combine reads every file again for each piece of the image it
        # works on, which takes minutes for a few dozen large images, so
        # combine in bands, opening each file once, whenever that is possible.
        combined = _combine_in_bands(file_list,
                                     mem_limit=mem_limit,
                                     dtype=combine_dtype,
                                     **combine_keyword_args)
        if combined is None:
            combined = ccdproc.combine(file_list,
                                       mem_limit=mem_limit,
                                       dtype=combine_dtype,
                                       **combine_keyword_args)

        # Do not keep the mask or uncertainty if the data has neither. Do this
        # before anything else because ccdproc.combine always makes both of
        # them, and together they are larger than the combined image itself.
        if not sample_has_mask and not sample_has_uncertainty:
            combined.mask = None
            combined.uncertainty = None

        combined.header = sample_header
        combined.header['master'] = True

        return combined


class CosmicRaySettings(gui.ToggleContainer):
    def __init__(self, *args, **kwd):
        descript = kwd.pop('description', 'Clean cosmic rays?')
        kwd['description'] = descript
        super(CosmicRaySettings, self).__init__(*args, **kwd)
        cr_choices = override_str_factory(
            widgets.Dropdown(description='Method:',
                             options=['median [not connected yet]',
                                      'LACosmic [coming soon]'])
        )
        self.add_child(cr_choices)

    def display(self):
        from IPython.display import display
        display(self)


class AxisSelection(widgets.Box):
    """docstring for AxisSelection"""
    def __init__(self, *args, **kwd):
        super(AxisSelection, self).__init__(*args, **kwd)
        self.layout.display = 'flex'
        values = OrderedDict()
        values["axis 0"] = 0
        values["axis 1"] = 1

        drop_desc = ('Region is all of')
        self._pre = self._make_pre_widget(drop_desc, values)

        style = {'description_width': 'initial'}
        self._start_text = widgets.Label('and along the other axis from ')
        self._start = widgets.IntText(style=style)
        self._stop_text = widgets.Label('up to (but not including):')
        self._stop = widgets.IntText(style=style)
        self.children = [
            self._pre,
            self._start_text,
            self._start,
            self._stop_text,
            self._stop
        ]

    def __str__(self):
        gob = [' '.join([child.description, str(child.value)])
               for child in self.children]
        return ' '.join(gob)

    def _make_pre_widget(self, description, values):
        box = widgets.HBox()
        box.description = description
        text = widgets.Label(value=description)
        style = {'button_width': 'initial'}
        toggles = widgets.ToggleButtons(options=values, style=style)
        # Vertically align text and toggles.
        box.layout.align_items = 'center'
        box.children = [text, toggles]
        box.add_traits(value=Any(sync=True, default_value=toggles.value))

        link((box, 'value'), (toggles, 'value'))
        return box

    @property
    def full_axis(self):
        return self._pre.children[1].value

    @property
    def start(self):
        return self._start.value

    @property
    def stop(self):
        return self._stop.value

    def format(self):
        # self._start.set_css('width', '30px')
        self._start.layout.width = '5em'
        # self._stop.set_css('width', '30px')
        self._stop.layout.width = '5em'


class Slice(gui.ToggleContainer):
    def __init__(self, *arg, **kwd):
        self.images = kwd.pop('images', [])
        super(Slice, self).__init__(*arg, **kwd)
        self._axis_selection = AxisSelection()
        self.add_child(self._axis_selection)
        for child in self._axis_selection.children:
            self._child_notify_parent_on_change(child)

    def format(self):
        super(Slice, self).format()
        hbox_these = [self._axis_selection]  # [self, self.container]
        for hbox in hbox_these:
            hbox.orientation = 'horizontal'
        self._axis_selection.format()

    @property
    def is_sane(self):
        """
        Determine whether combination of settings is at least remotely
        plausible.
        """
        # If the Slice is not selected, return None
        if not self.toggle.value:
            return None
        # Stop value must be larger than start (i.e. slice must contain at
        # least one row/column).
        sanity = self._axis_selection.stop > self._axis_selection.start
        return sanity


class MasterImageSource(widgets.Box):
    """docstring for ReductionSource"""
    def __init__(self):
        super(MasterImageSource, self).__init__(description="Reduction choices")

        self._source_list = [('Created in this notebook', 'notebook'),
                             ('File on disk', 'disk')]
        self._source = widgets.ToggleButtons(description='Source:',
                                             options=self._source_list)
        self._source.observe(self._file_select_visibility(),
                                     str('index'))

        self._file_select = widgets.Dropdown(description="Select file:",
                                             options=["Not working yet"])
        self._file_select.layout.display = 'none'
        self.children = [self._source, self._file_select]

    def __str__(self):
        return self._source.description + ' ' + str(self._source.value)

    def _file_select_visibility(self):
        def file_visibility(change):
            value = change['new']
            self._file_select.visible = self._source_list[value][1] == 'disk'
            if self._file_select.visible:
                self._file_select.layout.display = 'flex'
                self._file_select.layout.visbility = 'visible'
            else:
                self._file_select.layout.display = 'none'
        return file_visibility


class CalibrationStep(gui.ToggleContainer):
    """
    Represents a calibration step that corresponds to a ccdproc command.

    Parameters
    ----------

    None
    """
    def __init__(self, *args, **kwd):
        self._master_source = kwd.pop('master_source', None)
        self._imagetype_map = kwd.pop('imagetype_map', DEFAULT_IMAGETYPE_MAP)
        super(CalibrationStep, self).__init__(*args, **kwd)
        self._settings = MasterImageSource()
        # self.add_child(self._settings)

        self._image_cache = {}
        self._match_on = []

    @property
    def match_on(self):
        """
        List of keywords whose values should match in the image being
        calibated and the calibration image.
        """
        return self._match_on

    @match_on.setter
    def match_on(self, value):
        self._match_on = value

    @property
    def imagetype_map(self):
        return self._imagetype_map

    def _master_image(self, selector, closest=None):
        """
        Identify appropriate master and return as `ccdproc.CCDData`.

        Parameters
        ----------

        selector : dict-like
            Dictionary of key/value pairs that uniquely select the appropriate
            master image.

        closest : str, optional
            Name of keyword from ``selector`` whose value needs only be
            closest to the value in the dictionary instead of being an
            exact match.
        """
        if not self._master_source:
            raise RuntimeError("No source provided for master.")
        file_name = self._master_source.files_filtered(master=True,
                                                       **selector)
        if len(file_name) > 1:
            raise RuntimeError("Well, crap. Should only be one master but "
                               "found these matches: "
                               "{} for {}.".format(file_name, selector))
        elif len(file_name) == 0:
            if closest is None:
                raise RuntimeError("No master found for {}".format(selector))
            else:
                new_select = selector.copy()
                del new_select[closest]
                file_name = self._master_source.files_filtered(master=True,
                                                               **new_select)
                master_table = self._master_source.summary
                min_dist = 1e20
                for name in file_name:
                    match = master_table['file'] == name
                    distance = abs(master_table[closest][match] -
                                   selector[closest])
                    if distance <= min_dist:
                        best_match = name
                        min_dist = distance
                file_name = [best_match]
        file_name = file_name[0]
        path = os.path.join(self._master_source.location, file_name)
        try:
            return self._image_cache[path]
        except KeyError:
            # Keep at most one master per calibration step. Images are often
            # interleaved by filter or exposure, and re-reading a master costs
            # a fraction of a second, whereas holding one master per filter
            # for the whole reduction costs a full image of memory each.
            self._image_cache.clear()
            # Try getting the unit form the FITS file, but force it to ADU
            try:
                self._image_cache[path] = ccdproc.CCDData.read(path)
            except ValueError:
                self._image_cache[path] = \
                    ccdproc.CCDData.read(path, unit=DEFAULT_IMAGE_UNIT)
            return self._image_cache[path]


class CopyFiles(gui.ToggleContainer):
    """
    Just copy images to destination directory without modifying the file.
    Useful, for example, if the bias frames have no overscan and do not need
    to be trimmed.
    """
    def __init__(self, **kwd):
        desc = kwd.pop('description', 'Copy without any other action?')
        kwd['description'] = desc
        super(CopyFiles, self).__init__(**kwd)

    def action(self, ccd):
        return ccd


class BiasSubtract(CalibrationStep):
    """
    Subtract bias from an image using widget settings.
    """
    def __init__(self, bias_image=None, **kwd):
        desc = kwd.pop('description', 'Subtract bias?')
        kwd['description'] = desc
        super(BiasSubtract, self).__init__(**kwd)

    def action(self, ccd):
        select_dict = {'imagetyp': self.imagetype_map['bias']}
        master = self._master_image(select_dict)
        return ccdproc.subtract_bias(ccd, master)


class DarkScaleSetting(widgets.Box):
    """docstring for DarkScaleSetting"""
    def __init__(self, *arg, **kwd):
        super(DarkScaleSetting, self).__init__(*arg, **kwd)
        value_dict = [('Yes', True), ('No', False)]  # {'Yes': True, 'No': False}

        self._scale = \
        override_str_factory(\
            widgets.ToggleButtons(\
                description='Scale dark by exposure time (if needed)',
                options=value_dict, #))
                value=False))
        self.children = [self._scale]

    @property
    def scale(self):
        return self._scale.value

    def __str__(self):
        return str(self._scale)


class DarkSubtract(CalibrationStep):
    """
    Subtract dark from an image using widget settings.
    """
    def __init__(self, bias_image=None, **kwd):
        desc = kwd.pop('description', 'Subtract Dark?')
        self.exposure_keyword = kwd.pop('exposure_keyword', 'exposure')
        kwd['description'] = desc
        super(DarkSubtract, self).__init__(**kwd)
        self.match_on = [self.exposure_keyword]
        self._scale = DarkScaleSetting()
        self.add_child(self._scale)

    def action(self, ccd):
        from astropy import units as u
        select_dict = {'imagetyp': self.imagetype_map['dark']}
        for keyword in self.match_on:
            if keyword in select_dict:
                raise ValueError("Keyword {} already has a value set".format(keyword))
            select_dict[keyword] = ccd.header[keyword]
        if self._scale.scale:
            master = self._master_image(select_dict, closest=self.match_on[0])
            if not 'subbias' in master.meta:
                raise RuntimeError("Bias has not been subtracted from dark, "
                                   "so cannot scale dark")
            # Scale the dark here instead of letting ccdproc do it. ccdproc
            # multiplies by a float64 quantity, which promotes the master, and
            # then the result, to float64, roughly doubling the memory used.
            # Once https://github.com/astropy/ccdproc/issues/1013 is fixed
            # this block can go and ``scale=self._scale.scale`` can be passed
            # to ``subtract_dark`` again.
            scale_dtype = np.result_type(master.data.dtype, np.float32)
            ratio = scale_dtype.type(ccd.header[self.exposure_keyword] /
                                     master.header[self.exposure_keyword])
            # No-op for the float32 masters reducer writes; keeps an integer
            # master (e.g. from other software) from being promoted to float64
            # by the multiply below.
            master.data = master.data.astype(scale_dtype, copy=False)
            master = master.multiply(ratio, handle_meta='first_found')
        else:
            master = self._master_image(select_dict)
        return ccdproc.subtract_dark(ccd, master,
                                     exposure_time=self.exposure_keyword,
                                     exposure_unit=u.second,
                                     scale=False)


class FlatCorrect(CalibrationStep):
    """
    Subtract dark from an image using widget settings.
    """
    def __init__(self, bias_image=None, **kwd):
        desc = kwd.pop('description', 'Flat correct?')
        kwd['description'] = desc
        super(FlatCorrect, self).__init__(**kwd)
        self.match_on = ['filter']

    def action(self, ccd):
        select_dict = {'imagetyp': self.imagetype_map['flat']}
        for keyword in self.match_on:
            if keyword in select_dict:
                raise ValueError("Keyword {} already has a value set".format(keyword))
            select_dict[keyword] = ccd.header[keyword]
        master = self._master_image(select_dict)
        return ccdproc.flat_correct(ccd, master)


class PolynomialDropdown(widgets.Dropdown):
    def __init__(self):
        poly_values = OrderedDict()
        poly_values["Order 0/one term (constant)"] = 1
        poly_values["Order 1/two term (linear)"] = 2
        poly_values["Order 2/three team (quadratic)"] = 3
        poly_values["Are you serious? Higher order is silly."] = None
        super(PolynomialDropdown, self).__init__(
            description="Choose fit",
            options=poly_values,
            value=1)

    def __str__(self):
        for k, v in self.options.items():
            if v == self.value:
                return k


class Overscan(Slice):
    """docstring for Overscan"""
    def __init__(self, *arg, **kwd):
        super(Overscan, self).__init__(*arg, **kwd)
        poly_desc = "Fit polynomial to overscan?"
        self._polyfit = gui.ToggleContainer(description=poly_desc)
        poly_dropdown = PolynomialDropdown()
        self._polyfit.add_child(poly_dropdown)
        self.add_child(self._polyfit)

    def format(self):
        super(Overscan, self).format()
        self._polyfit.format()
        self._polyfit.orientation = 'horizontal'

    @property
    def is_sane(self):
        # Am I even active? If not, return None
        if not self.toggle.value:
            return None

        # See what the Slice thinks....
        sanity = super(Overscan, self).is_sane
        if self._polyfit.toggle.value:
            poly_dropdown = self._polyfit.container.children[0]
            sanity = sanity and (poly_dropdown.value is not None)
        return sanity

    @property
    def polynomial_order(self):
        # yuck
        return self._polyfit.container.children[0].value

    def action(self, ccd):
        """
        Subtract overscan from image based on settings.

        Parameters
        ----------

        ccd : `ccdproc.CCDData`
            Image to be reduced.
        """
        if not self.toggle.value:
            pass

        whole_axis = slice(None, None)
        partial_axis = slice(self._axis_selection.start,
                             self._axis_selection.stop)
        # create a two-element list which will be filled with the appropriate
        # slice based on the widget settings.
        if self._axis_selection.full_axis == 0:
            first_axis = whole_axis
            second_axis = partial_axis
            oscan_axis = 1
        else:
            first_axis = partial_axis
            second_axis = whole_axis
            oscan_axis = 0

        if self._polyfit.toggle.value:
            poly_model = models.Polynomial1D(self.polynomial_order)
        else:
            poly_model = None

        reduced = ccdproc.subtract_overscan(ccd,
                                            overscan=ccd[first_axis, second_axis],
                                            overscan_axis=oscan_axis,
                                            model=poly_model)
        return reduced


class Trim(Slice):
    """
    Controls and action for trimming a widget.
    """
    def __init__(self, *arg, **kwd):
        super(Trim, self).__init__(*arg, **kwd)
        # TODO: remove the line below sooner rather than later.
        self._axis_selection._stop.value = 4096

    def action(self, ccd):
        """
        Trim an image to bounds given in the widget.

        Returns
        -------

        trimmed : `ccdproc.CCDData`
            Trimmed image.
        """
        # Don't do anything if not activated
        if not self.toggle.value:
            pass
        whole_axis = slice(None, None)
        partial_axis = slice(self._axis_selection.start,
                             self._axis_selection.stop)
        # create a two-element list which will be filled with the appropriate
        # slice based on the widget settings.
        if self._axis_selection.full_axis == 0:
            trimmed = ccdproc.trim_image(ccd[whole_axis, partial_axis])
        else:
            trimmed = ccdproc.trim_image(ccd[partial_axis, whole_axis])

        return trimmed
