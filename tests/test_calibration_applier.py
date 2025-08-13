from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from calibration_applier import CalibrationApplier  # noqa: E402
import numpy as np  # noqa: E402


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


def test_calibrate_frame_no_masters_returns_frame():
    cfg = DummyConfig()
    applier = CalibrationApplier(cfg, logger=None)

    # Simple synthetic frame
    frame = np.ones((50, 80), dtype=np.uint16) * 1000
    status = applier.calibrate_frame(
        frame, exposure_time_s=1.0, frame_details={"gain": 100, "offset": 50, "readout_mode": 0}
    )
    assert status.is_success
    out = status.data
    assert isinstance(out, np.ndarray)
    assert out.shape == (50, 80)
