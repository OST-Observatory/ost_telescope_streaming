from hypothesis import given, settings
import hypothesis.strategies as st
import numpy as np


class _StubConfig:
    def __init__(self, method: str = "zscale") -> None:
        self._method = method

    def get_frame_processing_config(self):
        return {"normalization": {"method": self._method, "contrast": 0.2}}


@given(
    h=st.integers(min_value=1, max_value=32),
    w=st.integers(min_value=1, max_value=32),
    vals=st.lists(st.integers(min_value=0, max_value=65535), min_size=1, max_size=32),
)
@settings(deadline=None, max_examples=30)
def test_hist_normalize_uint8_bounds_and_shape(h, w, vals):
    from processing.normalization import normalize_to_uint8

    # Build a 2D uint16 array with shape h x w
    flat = np.resize(np.array(vals, dtype=np.uint16), h * w)
    image = flat.reshape((h, w))
    cfg = _StubConfig(method="hist")
    out = normalize_to_uint8(image, cfg)
    assert out.dtype == np.uint8
    assert out.shape == image.shape
    assert out.min() >= 0 and out.max() <= 255


@given(
    h=st.integers(min_value=1, max_value=16),
    w=st.integers(min_value=1, max_value=16),
    vals=st.lists(st.integers(min_value=0, max_value=65535), min_size=3, max_size=65536),
)
@settings(deadline=None, max_examples=20)
def test_hist_normalize_color_uint8_bounds_and_shape(h, w, vals):
    from processing.normalization import normalize_to_uint8

    # Build a 3D uint16 array (H, W, 3)
    flat = np.resize(np.array(vals, dtype=np.uint16), h * w * 3)
    image = flat.reshape((h, w, 3))
    cfg = _StubConfig(method="hist")
    out = normalize_to_uint8(image, cfg)
    assert out.dtype == np.uint8
    assert out.shape == image.shape
    assert out.min() >= 0 and out.max() <= 255
