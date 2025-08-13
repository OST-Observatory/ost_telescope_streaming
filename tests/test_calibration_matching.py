from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from calibration_applier import CalibrationApplier  # noqa: E402


class DummyConfig:
    def __init__(self):
        self._camera = {"camera_type": "alpaca"}
        self._overlay = {}
        self._frame = {}
        self._telescope = {}

    def get_camera_config(self):
        return self._camera

    def get_overlay_config(self):
        return self._overlay

    def get_frame_processing_config(self):
        return self._frame

    def get_telescope_config(self):
        return self._telescope


def test_find_best_master_dark_prefers_within_tolerance_over_nearest():
    applier = CalibrationApplier(DummyConfig(), logger=None)
    applier.calibration_tolerance = 0.5  # seconds
    applier.master_dark_cache = {
        "d1": {
            "file": "d1",
            "exposure_time": 10.1,
            "gain": 100,
            "offset": 50,
            "readout_mode": 0,
            "data": None,
        },
        "d2": {
            "file": "d2",
            "exposure_time": 9.0,
            "gain": 100,
            "offset": 50,
            "readout_mode": 0,
            "data": None,
        },
    }
    # exp=10.0 is within tolerance to d1, though d2 is farther away
    best = applier._find_best_master_dark(10.0, gain=100, offset=50, readout_mode=0)
    assert best is not None and best["file"] == "d1"


def test_find_best_master_dark_falls_back_to_nearest():
    applier = CalibrationApplier(DummyConfig(), logger=None)
    applier.calibration_tolerance = 0.05
    applier.master_dark_cache = {
        "d1": {"file": "d1", "exposure_time": 10.2, "data": None},
        "d2": {"file": "d2", "exposure_time": 9.4, "data": None},
    }
    best = applier._find_best_master_dark(10.0)
    assert best is not None
    # Nearest to 10.0 is 10.2
    assert abs(best["exposure_time"] - 10.2) < 1e-6


def test_find_best_master_flat_matches_settings():
    applier = CalibrationApplier(DummyConfig(), logger=None)
    applier.calibration_tolerance = 0.5
    applier.master_flat_cache = {
        "file": "flat1",
        "gain": 100,
        "offset": 50,
        "readout_mode": 0,
        "data": None,
    }
    flat = applier._find_best_master_flat(gain=100, offset=50, readout_mode=0)
    assert flat is not None and flat["file"] == "flat1"


def test_find_best_master_flat_mismatch_returns_none():
    applier = CalibrationApplier(DummyConfig(), logger=None)
    applier.calibration_tolerance = 0.1
    applier.master_flat_cache = {
        "file": "flat1",
        "gain": 120,
        "offset": 60,
        "readout_mode": 1,
        "data": None,
    }
    flat = applier._find_best_master_flat(gain=100, offset=50, readout_mode=0)
    assert flat is None
