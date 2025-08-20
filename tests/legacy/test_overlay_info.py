from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from overlay.info import calculate_secondary_fov, fov_info  # noqa: E402


def test_calculate_secondary_fov_camera():
    cfg = {
        "enabled": True,
        "type": "camera",
        "telescope": {"focal_length": 1000.0},
        "camera": {"sensor_width": 10.0, "sensor_height": 5.0},
    }
    w, h = calculate_secondary_fov(cfg)
    assert 0.5 < w < 1.0
    assert 0.2 < h < 0.6


def test_calculate_secondary_fov_eyepiece():
    cfg = {
        "enabled": True,
        "type": "eyepiece",
        "telescope": {"focal_length": 1000.0},
        "eyepiece": {"focal_length": 25.0, "afov": 50.0, "barlow": 1.0, "aspect_ratio": [1.0, 1.0]},
    }
    w, h = calculate_secondary_fov(cfg)
    # True FOV ~ 1.25 deg
    assert 1.0 < w < 1.5
    assert abs(w - h) < 1e-6


def test_fov_info_format():
    s = fov_info(2.0, 1.5)
    assert "2.00°×1.50°" in s
    assert "120.0'×90.0'" in s
