from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

from collections import OrderedDict

from IPython.html import widgets

import ccdproc

from . import gui

__all__ = [
    'ReductionSettings',
    'CombinerWidget',
    'CosmicRaySettingsWidget',
    'SliceWidget',
    'CalibrationStepWidget',
    'OverscanWidget',
]


class ReductionSettings(gui.ToggleGoWidget):
    """docstring for ReductionSettings"""
    def __init__(self, *arg, **kwd):
        allow_flat = kwd.pop('allow_flat', True)
        allow_dark = kwd.pop('allow_dark', True)
        allow_bias = kwd.pop('allow_bias', True)
        self.image_collection = kwd.pop('image_collection', None)
        self.apply_to = kwd.pop('apply_to', None)
        super(ReductionSettings, self).__init__(*arg, **kwd)
        self._overscan = OverscanWidget(description='Subtract overscan?')
        self._trim = SliceWidget(description='Trim (specify region to keep)?')
        self._cosmic_ray = CosmicRaySettingsWidget()
        self._bias_calib = CalibrationStepWidget(description="Subtract bias?")
        self._bias_calib.action = ccdproc.subtract_bias
        self._dark_calib = CalibrationStepWidget(description="Subtract dark?")
        self._flat_calib = CalibrationStepWidget(description="Flat correct?")
        self.add_child(self._overscan)
        self.add_child(self._trim)
        self.add_child(self._cosmic_ray)

        if allow_bias:
            self.add_child(self._bias_calib)
        if allow_dark:
            self.add_child(self._dark_calib)
        if allow_flat:
            self.add_child(self._flat_calib)

    def display(self):
        from IPython.display import display
        display(self)
        self.format()

    @property
    def is_sane(self):
        # There are two ways to be insane here:

        # 1. No steps are selected
        for child in self.container.children:
            if child.toggle.value:
                break
        else:
            # Reminder: this executes if the loop completes successfully,
            # i.e. none of the children are selected
            return False

        # 2. There is a combination of settings that doesn't make sense.
        mental_state = [child.is_sane for child in
                        self.container.children if child.is_sane is not None]
        sanity = all(mental_state)
        return sanity

    def action(self):
        if not self.image_collection:
            raise ValueError("No images to reduce")
        reduced_images = []
        for hdu, fname in self.image_collection.hdus(return_fname=True,
                                                     **self.apply_to):
            ccd = ccdproc.CCDData(data=hdu.data, meta=hdu.header, unit="adu")
            if self._overscan.toggle.value:
                oscan0 = slice(None, None)
                oscan1 = slice(self._overscan._start.value,
                               self._overscan._stop.value)
                print("subtracting overscan for ", fname)
                reduced = ccdproc.subtract_overscan(ccd,
                                                    overscan=ccd[oscan0, oscan1])
            if self._trim.toggle.value:
                print("trimming ", fname)


class ClippingWidget(gui.ToggleContainerWidget):
    """docstring for ClippingWidget"""
    def __init__(self, *args, **kwd):
        super(ClippingWidget, self).__init__(*args, **kwd)
        self._min_max = gui.ToggleMinMaxWidget(description="Clip by min/max?")
        self._sigma_clip = gui.ToggleMinMaxWidget(description="Sigma clip?")
        self.add_child(self._min_max)
        self.add_child(self._sigma_clip)

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
        super(ClippingWidget, self).format()
        self._sigma_clip.format()
        self._min_max.format()


class CombinerWidget(gui.ToggleGoWidget):
    """
    Widget for displaying options for ccdproc.Combiner.

    Parameters
    ----------

    description : str, optional
        Text displayed next to check box for selecting options.
    """
    def __init__(self, *args, **kwd):
        group_by_in = kwd.pop('group_by', None)
        super(CombinerWidget, self).__init__(*args, **kwd)
        self._clipping_widget = \
            ClippingWidget(description="Clip before combining?")
        self._combine_method = \
            widgets.ToggleButtonsWidget(description="Combination method:",
                                        values=[
                                            'None',
                                            'Average',
                                            'Median'
                                        ])

        self.add_child(self._clipping_widget)
        self.add_child(self._combine_method)

        if group_by_in is not None:
            self._group_by = widgets.TextWidget(description='Group by:',
                                                value=group_by_in)
            self.add_child(self._group_by)
        else:
            self._group_by = None

    @property
    def is_sane(self):
        """
        Indicates whether the combination of selected settings is at least
        remotely sane.
        """
        sanity = self._combine_method.value != 'None'
        if self._clipping_widget.is_sane is not None:
            sanity = sanity and self._clipping_widget.is_sane

        return sanity

    def format(self):
        super(CombinerWidget, self).format()
        self._clipping_widget.format()

    def _perform_combination(self):
        if not self.images:
            raise ValueError("No images provided to act on")
        if self._group_by:
            pass
        combiner = ccdproc.Combiner(self.images)
        if self._clipping_widget.value:
            if self.min_max.value:
                combiner.minmax_clipping(min_clip=self.min_max.min,
                                         max_clip=self.min_max.max)
            if self.sigma_clip.value:
                combiner.sigma_clipping(low_thresh=self.sigma_clip.min,
                                        high_thresh=self.sigma_clip.max)


class CosmicRaySettingsWidget(gui.ToggleContainerWidget):
    def __init__(self, *args, **kwd):
        descript = kwd.pop('description', 'Clean cosmic rays?')
        kwd['description'] = descript
        super(CosmicRaySettingsWidget, self).__init__(*args, **kwd)
        cr_choices = widgets.DropdownWidget(
            description='Method:',
            values={'median': None, 'LACosmic': None}
        )
        self.add_child(cr_choices)

    def display(self):
        from IPython.display import display
        display(self)


class SliceWidget(gui.ToggleContainerWidget):
    def __init__(self, *arg, **kwd):
        self.images = kwd.pop('images', [])
        super(SliceWidget, self).__init__(*arg, **kwd)
        drop_desc = ('Region is along all of')
        self._axis_selection = widgets.ContainerWidget()
        values = OrderedDict()
        values["axis 0"] = 0
        values["axis 1"] = 1
        self._pre = widgets.ToggleButtonsWidget(description=drop_desc,
                                                values=values)
        self._start = widgets.IntTextWidget(description='and on the other axis from index ')
        self._stop = widgets.IntTextWidget(description='up to (but not including):')
        self._axis_selection.children = [
            self._pre,
            self._start,
            self._stop
        ]
        self.add_child(self._axis_selection)
        for child in self._axis_selection.children:
            self._child_notify_parent_on_change(child)

    def format(self):
        super(SliceWidget, self).format()
        hbox_these = [self._axis_selection]  # [self, self.container]
        for hbox in hbox_these:
            hbox.remove_class('vbox')
            hbox.add_class('hbox')
        self._start.set_css('width', '30px')
        self._stop.set_css('width', '30px')

    @property
    def is_sane(self):
        """
        Determine whether combination of settings is at least remotely
        plausible.
        """
        # If the SliceWidget is not selected, return None
        if not self.toggle.value:
            return None
        # Stop value must be larger than start (i.e. slice must contain at
        # least one row/column).
        sanity = self._stop.value > self._start.value
        return sanity


class CalibrationStepWidget(gui.ToggleContainerWidget):
    """
    Represents a calibration step that corresponds to a ccdproc command.

    Parameters
    ----------

    None
    """
    def __init__(self, *args, **kwd):
        super(CalibrationStepWidget, self).__init__(*args, **kwd)
        self._source_dict = {'Created in this notebook': 'notebook',
                             'File on disk': 'disk'}
        self._settings = \
            widgets.ContainerWidget(description="Reduction choices")

        self._source = widgets.ToggleButtonsWidget(description='Source:',
                                                   values=self._source_dict)
        self._file_select = widgets.DropdownWidget(description="Select file:",
                                                   values=["Not working yet"],
                                                   visible=False)
        self._settings.children = [self._source, self._file_select]
        self.add_child(self._settings)
        self._source.on_trait_change(self._file_select_visibility(),
                                     str('value_name'))

    def _file_select_visibility(self):
        def file_visibility(name, value):
            self._file_select.visible = self._source_dict[value] == 'disk'
        return file_visibility


class OverscanWidget(SliceWidget):
    """docstring for OverscanWidget"""
    def __init__(self, *arg, **kwd):
        super(OverscanWidget, self).__init__(*arg, **kwd)
        poly_desc = "Fit polynomial to overscan?"
        self._polyfit = gui.ToggleContainerWidget(description=poly_desc)
        poly_values = OrderedDict()
        poly_values["Order 0/one term (constant)"] = 1
        poly_values["Order 1/two term (linear)"] = 2
        poly_values["Order 2/three team (quadratic)"] = 3
        poly_values["Are you serious? Higher order is silly."] = None
        poly_dropdown = widgets.DropdownWidget(description="Choose fit",
                                               values=poly_values,
                                               value=1)
        self._polyfit.add_child(poly_dropdown)
        self.add_child(self._polyfit)

    def format(self):
        super(OverscanWidget, self).format()
        self._polyfit.format()
        self._polyfit.remove_class('vbox')
        self._polyfit.add_class('hbox')

    @property
    def is_sane(self):
        # Am I even active? If not, return None
        if not self.toggle.value:
            return None

        # See what the SliceWidget thinks....
        sanity = super(OverscanWidget, self).is_sane
        if self._polyfit.toggle.value:
            poly_dropdown = self._polyfit.container.children[0]
            sanity = sanity and (poly_dropdown.value is not None)
        return sanity
