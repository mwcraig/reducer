from io import BytesIO

import numpy as np

import pytest

from PIL import Image

from astropy.io import fits
from astropy.nddata import block_reduce

from reducer.image_browser import (banded_block_reduce, hdu_to_png,
                                   ndarray_to_png, _PNG_WIDTH)


# Deliberately not a multiple of the block sizes or band heights used below.
IMAGE_SHAPE = (613, 470)


def make_image(shape=IMAGE_SHAPE):
    """
    Synthetic image with a NaN and one very bright pixel.
    """
    rng = np.random.default_rng(432)
    image = rng.normal(loc=1000.0, scale=20.0, size=shape)
    image[100, 100] = np.nan
    image[200, 300] = 1e6
    return image


@pytest.fixture
def image_hdu(tmp_path):
    """
    A 2D image HDU, read from a file so that ``section`` reads from disk.
    """
    image = make_image()
    path = tmp_path / 'image.fits'
    fits.PrimaryHDU(image).writeto(path)
    with fits.open(path) as hdulist:
        yield hdulist[0]


@pytest.mark.parametrize('block_size', [1, 3, 4, 8])
def test_banded_matches_whole_image(image_hdu, block_size):
    # A band height that is small compared to the image so that several
    # bands are needed.
    banded = banded_block_reduce(image_hdu, block_size, band_rows=30)
    whole = block_reduce(image_hdu.data, block_size)
    assert np.array_equal(banded, whole, equal_nan=True)


def test_banded_band_size_does_not_matter(image_hdu):
    whole = block_reduce(image_hdu.data, 4)
    for band_rows in [1, 4, 7, 30, 256, 10000]:
        banded = banded_block_reduce(image_hdu, 4, band_rows=band_rows)
        assert np.array_equal(banded, whole, equal_nan=True)


def test_banded_default_band_size(image_hdu):
    banded = banded_block_reduce(image_hdu, 4)
    assert np.array_equal(banded, block_reduce(image_hdu.data, 4),
                          equal_nan=True)


def test_banded_block_size_tuple(image_hdu):
    banded = banded_block_reduce(image_hdu, (4, 5), band_rows=30)
    whole = block_reduce(image_hdu.data, (4, 5))
    assert np.array_equal(banded, whole, equal_nan=True)


def test_banded_preprocess_is_applied(image_hdu):
    def clamp(data):
        return np.clip(data, None, 1e5)

    banded = banded_block_reduce(image_hdu, 4, band_rows=30,
                                 preprocess=clamp)
    whole = block_reduce(clamp(image_hdu.data), 4)
    assert np.array_equal(banded, whole, equal_nan=True)
    # Make sure the clamp actually changed something.
    assert not np.array_equal(banded, block_reduce(image_hdu.data, 4),
                              equal_nan=True)


def test_banded_block_larger_than_image(image_hdu):
    block_size = IMAGE_SHAPE[0] + 10
    banded = banded_block_reduce(image_hdu, block_size)
    whole = block_reduce(image_hdu.data, block_size)
    assert banded.shape == whole.shape
    assert np.array_equal(banded, whole, equal_nan=True)


def test_banded_non_2d_raises(tmp_path):
    path = tmp_path / 'cube.fits'
    fits.PrimaryHDU(np.zeros((3, 20, 20))).writeto(path)
    with fits.open(path) as hdulist:
        with pytest.raises(ValueError):
            banded_block_reduce(hdulist[0], 2)


def test_hdu_to_png_non_2d_returns_none(tmp_path):
    path = tmp_path / 'cube.fits'
    fits.PrimaryHDU(np.zeros((3, 20, 20))).writeto(path)
    with fits.open(path) as hdulist:
        assert hdu_to_png(hdulist[0]) is None


def test_hdu_to_png_matches_ndarray_to_png(image_hdu):
    assert hdu_to_png(image_hdu) == ndarray_to_png(image_hdu.data)


def test_png_is_grayscale_and_downsampled(image_hdu):
    png_bytes = hdu_to_png(image_hdu)
    image = Image.open(BytesIO(png_bytes))
    assert image.mode == 'L'

    ny, nx = IMAGE_SHAPE
    downsample = (nx // _PNG_WIDTH) + 1
    expected = block_reduce(image_hdu.data, downsample).shape
    # PIL reports (width, height).
    assert image.size == (expected[1], expected[0])


def test_png_of_big_image_is_downsampled(tmp_path):
    # Wide enough that the preview really is reduced.
    path = tmp_path / 'big.fits'
    fits.PrimaryHDU(make_image((1300, 1801))).writeto(path)
    with fits.open(path) as hdulist:
        hdu = hdulist[0]
        png_bytes = hdu_to_png(hdu)
        assert png_bytes == ndarray_to_png(hdu.data)

    image = Image.open(BytesIO(png_bytes))
    assert image.mode == 'L'
    # 1801 // 600 + 1 == 4
    assert image.size == (1801 // 4, 1300 // 4)
