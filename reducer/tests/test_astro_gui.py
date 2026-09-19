import errno

import numpy as np

import pytest

from astropy.io import fits
from astropy.nddata import CCDData
import ccdproc

from reducer import astro_gui
from reducer.astro_gui import _combine_in_bands, _no_uncertainty


# Deliberately not a multiple of any of the band heights used below.
IMAGE_SHAPE = (97, 61)
N_IMAGES = 6

# Small enough that the images above are combined in more than a dozen bands,
# so that anything that depended on how the image was split would show up.
MEM_LIMIT = 5e4

WCS_CARDS = {
    'CTYPE1': 'RA---TAN', 'CTYPE2': 'DEC--TAN',
    'CRVAL1': 339.27, 'CRVAL2': 34.42,
    'CRPIX1': 30.5, 'CRPIX2': 48.5,
    'CD1_1': -1.5e-4, 'CD1_2': 2.0e-6,
    'CD2_1': 2.0e-6, 'CD2_2': 1.5e-4,
}


def make_images(dtype):
    """
    Synthetic images of the same field whose sky level rises from one to the
    next, so that scaling matters, each with a few pixels far enough from
    the others that clipping removes them.
    """
    rng = np.random.default_rng(8675309)
    field = rng.normal(loc=0, scale=300, size=IMAGE_SHAPE).clip(min=0)
    images = []
    for idx in range(N_IMAGES):
        image = (field + 1000 + 150 * idx +
                 rng.normal(scale=20, size=IMAGE_SHAPE))
        rows = rng.integers(0, IMAGE_SHAPE[0], size=10)
        columns = rng.integers(0, IMAGE_SHAPE[1], size=10)
        image[rows[:5], columns[:5]] = 60000
        image[rows[5:], columns[5:]] = 3
        images.append(image.round().astype(dtype))
    return images


def write_images(directory, dtype='uint16', unit='adu', wcs=True):
    """
    Write the synthetic images to ``directory`` as FITS files with the image
    in the first HDU and return the list of paths.
    """
    paths = []
    for idx, image in enumerate(make_images(dtype)):
        hdu = fits.PrimaryHDU(image)
        hdu.header['imagetyp'] = 'LIGHT'
        hdu.header['filter'] = 'B'
        hdu.header['exposure'] = 30.0
        hdu.header['frame'] = idx
        if unit is not None:
            hdu.header['bunit'] = unit
        if wcs:
            hdu.header.update(WCS_CARDS)
        path = directory / 'frame-{:02d}.fit'.format(idx)
        hdu.writeto(path)
        paths.append(str(path))
    return paths


@pytest.fixture(params=['uint16', 'float32'])
def image_files(request, tmp_path):
    """
    Paths of FITS files to combine, as unsigned integers (which FITS stores
    with a BZERO, as a camera does) and as floats (as calibrated images are).
    """
    return write_images(tmp_path, dtype=request.param)


def scale_to_mean(arr):
    """The scaling function the widget uses to scale to the same mean."""
    return 1 / np.ma.average(arr)


def scale_to_median(arr):
    """The scaling function the widget uses to scale to the same median."""
    return 1 / np.ma.median(arr)


SIGMA_CLIP = {
    'sigma_clip': True,
    'sigma_clip_low_thresh': 2.5,
    'sigma_clip_func': 'median',
    'sigma_clip_dev_func': 'mad_std',
}

MINMAX_CLIP = {
    'minmax_clip': True,
    'minmax_clip_min': 10,
    'minmax_clip_max': 50000,
}

# Each of the things the Combiner widget can ask for, alone and all together.
COMBINE_OPTIONS = {
    'plain': {},
    'sigma_clip': SIGMA_CLIP,
    # With the functions ccdproc uses unless told otherwise, the mean and the
    # standard deviation, no value among six is as much as 2.1 deviations out.
    'sigma_clip_mean_std': {'sigma_clip': True,
                            'sigma_clip_low_thresh': 1.5,
                            'sigma_clip_high_thresh': 1.5},
    'minmax_clip': MINMAX_CLIP,
    'scale_mean': {'scale': scale_to_mean},
    'scale_median': {'scale': scale_to_median},
    'scale_array': {'scale': np.linspace(0.8, 1.3, N_IMAGES)},
    'everything': dict(scale=scale_to_median, **SIGMA_CLIP, **MINMAX_CLIP),
}


def assert_same_image(banded, expected):
    """
    Check that a banded combination is the image ``ccdproc.combine`` made,
    apart from the mask and uncertainty that reducer throws away.
    """
    assert banded.data.dtype == expected.data.dtype
    # Bitwise identical, not just close.
    np.testing.assert_array_equal(banded.data, expected.data)
    assert banded.unit == expected.unit
    assert banded.mask is None
    assert banded.uncertainty is None
    assert (banded.wcs.to_header(relax=True) ==
            expected.wcs.to_header(relax=True))


@pytest.mark.parametrize('method', ['average', 'median'])
@pytest.mark.parametrize('options', COMBINE_OPTIONS.values(),
                         ids=COMBINE_OPTIONS.keys())
def test_banded_matches_ccdproc_combine(image_files, method, options):
    """Combining in bands gives exactly the image ``ccdproc.combine`` gives
    with the same arguments, for both methods and for every kind of
    clipping and scaling the widget offers.
    """
    kwargs = dict(method=method, mem_limit=MEM_LIMIT, dtype='float32',
                  **options)
    if method == 'median':
        kwargs['combine_uncertainty_function'] = _no_uncertainty

    expected = ccdproc.combine(image_files, **kwargs)
    banded = _combine_in_bands(image_files, **kwargs)

    assert_same_image(banded, expected)
    # Make sure the comparison above is of something: clipping and scaling
    # must each have changed the result.
    if options:
        plain = ccdproc.combine(image_files, method=method, dtype='float32')
        assert not np.array_equal(plain.data, expected.data)


@pytest.mark.parametrize('mem_limit', [2e3, 3e4, 1e5, 16e9])
def test_banded_band_height_does_not_matter(tmp_path, mem_limit):
    """The result is the same whether the image is combined a row at a time
    (the smallest limit allows less than one row), in a few bands, or all at
    once.
    """
    image_files = write_images(tmp_path)
    kwargs = dict(method='median', dtype='float32', **SIGMA_CLIP)

    expected = ccdproc.combine(image_files, **kwargs)
    banded = _combine_in_bands(image_files, mem_limit=mem_limit, **kwargs)

    assert_same_image(banded, expected)


def test_banded_default_dtype_and_sum(tmp_path):
    """With no dtype the result is float64, as it is from
    ``ccdproc.combine``, and the third method ccdproc has, the sum, works
    too.
    """
    image_files = write_images(tmp_path)

    expected = ccdproc.combine(image_files, method='sum', mem_limit=MEM_LIMIT)
    banded = _combine_in_bands(image_files, method='sum', mem_limit=MEM_LIMIT)

    assert banded.data.dtype == np.float64
    assert_same_image(banded, expected)


def test_banded_header_is_that_of_first_file(tmp_path):
    """The combined image carries the whole header of the first file."""
    image_files = write_images(tmp_path)

    banded = _combine_in_bands(image_files, mem_limit=MEM_LIMIT)

    assert banded.header['frame'] == 0
    assert banded.header['filter'] == 'B'


def test_banded_without_wcs(tmp_path):
    """Images with no WCS combine to an image with no WCS, as they do with
    ``ccdproc.combine``.
    """
    image_files = write_images(tmp_path, wcs=False)

    expected = ccdproc.combine(image_files, mem_limit=MEM_LIMIT)
    banded = _combine_in_bands(image_files, mem_limit=MEM_LIMIT)

    assert expected.wcs is None
    assert banded.wcs is None
    np.testing.assert_array_equal(banded.data, expected.data)


def test_banded_unit_in_upper_case(tmp_path):
    """A ``BUNIT`` of ``ADU``, which is not a valid FITS unit but which
    ``CCDData.read`` accepts, is accepted here too.
    """
    image_files = write_images(tmp_path, unit='ADU')

    expected = ccdproc.combine(image_files, mem_limit=MEM_LIMIT)
    banded = _combine_in_bands(image_files, mem_limit=MEM_LIMIT)

    assert_same_image(banded, expected)


def test_banded_opens_each_file_once(tmp_path, monkeypatch):
    """Every file is opened exactly once however many bands there are, and
    ``CCDData.read`` is never called; re-reading the files for every band is
    what made ``ccdproc.combine`` slow.
    """
    image_files = write_images(tmp_path)
    opened = []
    real_open = fits.open

    def counting_open(name, *args, **kwargs):
        opened.append(name)
        return real_open(name, *args, **kwargs)

    def no_read(*args, **kwargs):
        raise AssertionError('CCDData.read should not be called')

    monkeypatch.setattr(astro_gui.fits, 'open', counting_open)
    monkeypatch.setattr(CCDData, 'read', no_read)

    banded = _combine_in_bands(image_files, method='median',
                               mem_limit=MEM_LIMIT, scale=scale_to_median,
                               **SIGMA_CLIP)

    assert banded is not None
    assert sorted(opened) == sorted(image_files)


def test_banded_blank_pixels_in_scaled_integers(tmp_path):
    """Integer images with a ``BSCALE`` and with ``BLANK`` pixels, which are
    read as NaN, combine to what ``ccdproc.combine`` gives, with and without
    a scaling function. Reading ``hdu.data`` for the scaling function used
    to leave astropy unable to read a section of such an image.
    """
    paths = []
    for idx, image in enumerate(make_images('float64')):
        image = image.clip(max=30000).astype('int16')
        # Blank in every image at one pixel, and in one image at another.
        image[3, 3] = -32768
        image[5, 3 + idx] = -32768
        hdu = fits.PrimaryHDU(image)
        hdu.header['bscale'] = 2.5
        hdu.header['bzero'] = 10.0
        hdu.header['blank'] = -32768
        hdu.header['bunit'] = 'adu'
        path = tmp_path / 'blank-{}.fit'.format(idx)
        hdu.writeto(path)
        paths.append(str(path))

    def scale_ignoring_nan(arr):
        return 1 / np.nanmedian(arr)

    for scale in [None, scale_ignoring_nan]:
        kwargs = dict(mem_limit=MEM_LIMIT, dtype='float32', scale=scale)
        expected = ccdproc.combine(paths, **kwargs)
        banded = _combine_in_bands(paths, **kwargs)

        assert np.isnan(expected.data[3, 3])
        assert np.isfinite(expected.data[4]).all()
        np.testing.assert_array_equal(banded.data, expected.data)


def add_extension(path, name):
    """Add an image extension called ``name`` to the FITS file at ``path``."""
    with fits.open(path, mode='append') as hdu_list:
        hdu_list.append(fits.ImageHDU(np.zeros(IMAGE_SHAPE, dtype='uint8'),
                                      name=name))


@pytest.mark.parametrize('extension', ['MASK', 'UNCERT', 'PSF'])
def test_banded_declines_ccddata_extensions(tmp_path, extension):
    """Files in which any one has a mask, uncertainty or PSF extension are
    left for ``ccdproc.combine``, which takes those into account.
    """
    image_files = write_images(tmp_path)
    # Not the first file, which is the only one reducer used to look at.
    add_extension(image_files[3], extension)

    assert _combine_in_bands(image_files, mem_limit=MEM_LIMIT) is None


def test_banded_declines_missing_unit(tmp_path):
    """Files with no ``BUNIT`` are left for ``ccdproc.combine``, so that
    whatever it does about that does not change.
    """
    image_files = write_images(tmp_path, unit=None)

    assert _combine_in_bands(image_files, mem_limit=MEM_LIMIT) is None


def test_banded_declines_bad_or_mixed_units(tmp_path):
    """A unit that cannot be parsed, or that differs from one file to
    another, is left for ``ccdproc.combine`` to complain about.
    """
    image_files = write_images(tmp_path)

    fits.setval(image_files[2], 'bunit', value='electron')
    assert _combine_in_bands(image_files, mem_limit=MEM_LIMIT) is None

    fits.setval(image_files[2], 'bunit', value='not a unit')
    assert _combine_in_bands(image_files, mem_limit=MEM_LIMIT) is None


def test_banded_declines_image_not_in_first_hdu(tmp_path):
    """Files whose first HDU has no image are left for ``ccdproc.combine``,
    which looks for the image in the extensions.
    """
    paths = []
    for idx, image in enumerate(make_images('float32')):
        image_hdu = fits.ImageHDU(image)
        image_hdu.header['bunit'] = 'adu'
        path = tmp_path / 'extension-{}.fit'.format(idx)
        fits.HDUList([fits.PrimaryHDU(), image_hdu]).writeto(path)
        paths.append(str(path))

    assert _combine_in_bands(paths, mem_limit=MEM_LIMIT) is None


def test_banded_declines_different_shapes(tmp_path):
    """Images that are not all the same shape are left for
    ``ccdproc.combine`` to complain about.
    """
    image_files = write_images(tmp_path)
    smaller = fits.PrimaryHDU(np.ones((50, 50), dtype='float32'))
    smaller.header['bunit'] = 'adu'
    smaller.writeto(image_files[-1], overwrite=True)

    assert _combine_in_bands(image_files, mem_limit=MEM_LIMIT) is None


def test_banded_declines_cube(tmp_path):
    """Three-dimensional images are left for ``ccdproc.combine``."""
    paths = []
    for idx in range(3):
        cube = fits.PrimaryHDU(np.ones((3, 20, 20), dtype='float32'))
        cube.header['bunit'] = 'adu'
        path = tmp_path / 'cube-{}.fit'.format(idx)
        cube.writeto(path)
        paths.append(str(path))

    assert _combine_in_bands(paths, mem_limit=MEM_LIMIT) is None


def test_banded_declines_when_too_many_files_are_open(tmp_path, monkeypatch):
    """If the operating system will not allow all of the files to be open at
    once they are left for ``ccdproc.combine``, which opens one at a time,
    and the ones that were opened are closed again.
    """
    image_files = write_images(tmp_path)
    hdu_lists = []
    real_open = fits.open

    def limited_open(name, *args, **kwargs):
        if len(hdu_lists) == 3:
            raise OSError(errno.EMFILE, 'Too many open files')
        hdu_lists.append(real_open(name, *args, **kwargs))
        return hdu_lists[-1]

    monkeypatch.setattr(astro_gui.fits, 'open', limited_open)

    assert _combine_in_bands(image_files, mem_limit=MEM_LIMIT) is None
    assert len(hdu_lists) == 3
    assert all(hdu_list.fileinfo(0)['file'].closed for hdu_list in hdu_lists)


def test_banded_other_errors_are_raised(tmp_path):
    """Any other failure to open a file, here one that does not exist, is
    raised rather than hidden by falling back.
    """
    image_files = write_images(tmp_path)
    image_files.append(str(tmp_path / 'not-there.fit'))

    with pytest.raises(FileNotFoundError):
        _combine_in_bands(image_files, mem_limit=MEM_LIMIT)


def test_banded_unknown_method_raises(tmp_path):
    """A combine method ccdproc does not have raises the error
    ``ccdproc.combine`` raises.
    """
    image_files = write_images(tmp_path)

    with pytest.raises(ValueError, match='unrecognised combine method'):
        _combine_in_bands(image_files, method='mode')


def make_combiner(source_dir, destination, median=False, sigma_clip=False,
                  min_max=False, scale=None):
    """
    A Combiner widget set up, as the notebook and a person clicking would
    set it up, to combine the light images in ``source_dir``.
    """
    collection = ccdproc.ImageFileCollection(location=str(source_dir),
                                             keywords='*')
    combiner = astro_gui.Combiner(description='Combine',
                                  file_name_base='combined_light',
                                  image_source=collection,
                                  apply_to={'imagetyp': 'light'},
                                  destination=str(destination),
                                  mem_limit=MEM_LIMIT)
    combiner.toggle.value = True
    combiner._combine_method.toggle.value = True
    if median:
        combiner._combine_method._combine_option.value = 'Median'
    if scale is not None:
        combiner._combine_method._scaling.toggle.value = True
        combiner._combine_method._scale_by.value = scale
    clipping = combiner._clipping_widget
    if sigma_clip:
        clipping.toggle.value = True
        clipping._sigma_clip.toggle.value = True
        clipping._sigma_clip._min_box.value = 2.5
        clipping._sigma_clip._max_box.value = 2.5
    if min_max:
        clipping.toggle.value = True
        clipping._min_max.toggle.value = True
        clipping._min_max._min_box.value = 10
        clipping._min_max._max_box.value = 50000
    return combiner


WIDGET_SETTINGS = {
    'average': {},
    'median': {'median': True},
    'median_sigma_clip': {'median': True, 'sigma_clip': True},
    'average_everything': {'sigma_clip': True, 'min_max': True,
                           'scale': 'mean'},
    'median_everything': {'median': True, 'sigma_clip': True,
                          'min_max': True, 'scale': 'median'},
}


@pytest.mark.parametrize('settings', WIDGET_SETTINGS.values(),
                         ids=WIDGET_SETTINGS.keys())
def test_combiner_file_is_unchanged(tmp_path, monkeypatch, settings):
    """The file the Combiner widget writes is the same, in every header card
    and every pixel, as the file it wrote when it always used
    ``ccdproc.combine``.
    """
    source = tmp_path / 'source'
    source.mkdir()
    write_images(source)
    outputs = {}
    for how in ['banded', 'ccdproc']:
        destination = tmp_path / how
        destination.mkdir()
        with monkeypatch.context() as patch:
            if how == 'ccdproc':
                # Declining makes the widget fall back to ccdproc.combine,
                # which is all it did before.
                patch.setattr(astro_gui, '_combine_in_bands',
                              lambda *args, **kwargs: None)
            make_combiner(source, destination, **settings).action()
        outputs[how] = destination / 'combined_light.fit'

    with fits.open(outputs['banded']) as banded, \
            fits.open(outputs['ccdproc']) as expected:
        assert len(banded) == len(expected) == 1
        assert banded[0].header['master'] is True
        assert (banded[0].header.tostring(sep='\n') ==
                expected[0].header.tostring(sep='\n'))
        assert banded[0].data.dtype == expected[0].data.dtype
        np.testing.assert_array_equal(banded[0].data, expected[0].data)


def test_combiner_uses_bands_when_it_can(tmp_path, monkeypatch):
    """With ordinary images the widget never calls ``ccdproc.combine``."""
    source = tmp_path / 'source'
    source.mkdir()
    write_images(source)

    def no_combine(*args, **kwargs):
        raise AssertionError('ccdproc.combine should not be called')

    monkeypatch.setattr(ccdproc, 'combine', no_combine)
    combiner = make_combiner(source, tmp_path, median=True)
    combiner.action()

    assert combiner.combined.shape == IMAGE_SHAPE


def test_combiner_falls_back_for_images_with_a_mask(tmp_path, monkeypatch):
    """When an image has a mask the widget hands the same files and settings
    to ``ccdproc.combine`` and keeps the mask and uncertainty it makes.
    """
    source = tmp_path / 'source'
    source.mkdir()
    for path in write_images(source):
        add_extension(path, 'MASK')
    calls = []
    real_combine = ccdproc.combine

    def recording_combine(file_list, **kwargs):
        calls.append((file_list, kwargs))
        return real_combine(file_list, **kwargs)

    monkeypatch.setattr(ccdproc, 'combine', recording_combine)
    combiner = make_combiner(source, tmp_path, sigma_clip=True)
    combiner.action()

    assert len(calls) == 1
    file_list, kwargs = calls[0]
    assert len(file_list) == N_IMAGES
    assert kwargs['mem_limit'] == MEM_LIMIT
    assert kwargs['sigma_clip']
    assert combiner.combined.mask is not None
    assert combiner.combined.uncertainty is not None
