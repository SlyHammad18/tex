from tex.capture.base import Rect, smallest_containing, normalize, crop_image
from PIL import Image


def test_normalize_swaps_and_mins():
    r = normalize(30, 20, 10, 5)
    assert (r.x, r.y, r.w, r.h) == (10, 5, 20, 15)
    tiny = normalize(5, 5, 5, 5, min_size=1)
    assert tiny.w == 1 and tiny.h == 1


def test_smallest_containing_prefers_nested():
    big = Rect(0, 0, 500, 400)
    small = Rect(100, 100, 50, 40)
    assert smallest_containing([big, small], 120, 120) == 1
    assert smallest_containing([big, small], 10, 10) == 0
    assert smallest_containing([big, small], 600, 600) is None


def test_crop_image_clamps():
    img = Image.new("RGB", (100, 80), "white")
    out = crop_image(img, Rect(50, 40, 100, 100))
    assert out.size == (50, 40)
    out2 = crop_image(img, Rect(0, 0, 100, 80))
    assert out2.size == (100, 80)
    import pytest

    with pytest.raises(ValueError):
        crop_image(img, Rect(200, 200, 10, 10))
