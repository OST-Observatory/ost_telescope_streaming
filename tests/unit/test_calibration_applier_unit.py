from typing import Any, Dict

import numpy as np
import pytest


class _StubConfig:
    def __init__(self, enable: bool = True) -> None:
        self._enable = enable

    def get_master_config(self) -> Dict[str, Any]:
        return {
            "output_dir": "master_frames",
            "enable_calibration": self._enable,
            "auto_load_masters": False,  # avoid filesystem in unit test
            "calibration_tolerance": 0.1,
        }


def _make_frame(width: int = 4, height: int = 3, value: float = 100.0) -> np.ndarray:
    return np.full((height, width), value, dtype=np.float32)


def test_calibration_disabled_returns_original(monkeypatch: pytest.MonkeyPatch):
    from calibration_applier import CalibrationApplier

    applier = CalibrationApplier(config=_StubConfig(enable=False))
    frame = _make_frame()
    status = applier.calibrate_frame(frame, exposure_time=1.0)
    assert status.is_success
    assert status.details.get("calibration_applied") is False
    assert np.array_equal(status.data, frame)


def test_no_masters_returns_success_original(monkeypatch: pytest.MonkeyPatch):
    from calibration_applier import CalibrationApplier

    applier = CalibrationApplier(config=_StubConfig(enable=True))
    # ensure caches are empty
    applier.master_dark_cache.clear()
    applier.master_flat_cache = None
    frame = _make_frame(value=50.0)
    status = applier.calibrate_frame(frame, exposure_time=1.0)
    assert status.is_success
    assert status.details.get("reason") == "no_master_frames"
    assert np.array_equal(status.data, frame)


def test_apply_dark_and_flat_simple(monkeypatch: pytest.MonkeyPatch):
    from calibration_applier import CalibrationApplier

    applier = CalibrationApplier(config=_StubConfig(enable=True))
    applier.master_bias_cache = None
    # prepare one dark and one flat with exact match
    applier.master_dark_cache = {
        1.0: {
            "data": np.full((3, 4), 10.0, dtype=np.float32),
            "file": "master_dark_1.0s.fits",
            "exposure_time": 1.0,
            "gain": 100.0,
            "offset": 50.0,
            "readout_mode": 0,
        }
    }
    applier.master_flat_cache = {
        "data": np.full((3, 4), 2.0, dtype=np.float32),
        "file": "master_flat.fits",
        "gain": 100.0,
        "offset": 50.0,
        "readout_mode": 0,
    }

    frame = np.array(
        [[100.0, 120.0, 130.0, 140.0], [90.0, 110.0, 115.0, 100.0], [80.0, 95.0, 105.0, 110.0]],
        dtype=np.float32,
    )
    info = {"gain": 100.0, "offset": 50.0, "readout_mode": 0}

    status = applier.calibrate_frame(frame, exposure_time=1.0, frame_info=info)
    assert status.is_success
    assert status.details["dark_subtraction_applied"] is True
    assert status.details["flat_correction_applied"] is True
    # simple expected transform: (frame - 10) / 2
    expected = (frame - 10.0) / 2.0
    assert np.allclose(status.data, expected)
