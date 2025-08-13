from __future__ import annotations

import os
import sys

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from processing.normalization import normalize_to_uint8  # noqa: E402


class DummyConfig:
    def get_frame_processing_config(self):
        return {"normalization": {"method": "zscale", "contrast": 0.2}}


def test_normalize_uint16_to_uint8():
    img = np.linspace(0, 65535, 10000, dtype=np.uint16).reshape(100, 100)
    out = normalize_to_uint8(img, DummyConfig(), logger=None)
    assert out.dtype == np.uint8
    assert out.shape == img.shape


def test_normalize_rgb_float32():
    rng = np.random.default_rng(123)
    img = rng.random((64, 64, 3), dtype=np.float32) * 1000.0
    out = normalize_to_uint8(img, DummyConfig(), logger=None)
    assert out.dtype == np.uint8
    assert out.shape == img.shape
