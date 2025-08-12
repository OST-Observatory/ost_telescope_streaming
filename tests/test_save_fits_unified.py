from __future__ import annotations

import os
import sys
import tempfile
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, 'code')
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from video_capture import VideoCapture
from status import success_status


class DummyCamera:
    def __init__(self):
        self.name = 'dummy'
        self.ccdtemperature = -5.0
        self.cooler_power = 10.0
        self.cooler_on = False
        self.sensor_type = 'RGGB'


class DummyConfig:
    def __init__(self):
        self._camera = {
            'camera_type': 'alpaca',
            'pixel_size': 3.76,
            'sensor_width': 23.5,
            'sensor_height': 15.6,
            'ascom': {'gain': 100, 'offset': 50, 'readout_mode': 0},
            'alpaca': {},
        }
        self._telescope = {'focal_length': 400.0}
        self._overlay = {}
        self._frame = {}

    def get_camera_config(self):
        return self._camera

    def get_telescope_config(self):
        return self._telescope

    def get_overlay_config(self):
        return self._overlay

    def get_frame_processing_config(self):
        return self._frame


class DummyVC(VideoCapture):
    def _initialize_camera(self):
        # Skip real camera init
        return success_status("ok")


def test_save_fits_unified_writes_header_and_data(tmp_path):
    try:
        import astropy.io.fits as fits
    except Exception:
        return  # Skip if astropy missing

    cfg = DummyConfig()
    vc = DummyVC(cfg, logger=None, enable_calibration=False)
    vc.camera = DummyCamera()

    img = (np.linspace(0, 65535, 10000, dtype=np.uint16).reshape(100, 100))
    details = {'exposure_time_s': 10.0, 'gain': 100, 'offset': 50, 'readout_mode': 0, 'binning': 1}
    status = success_status("frame", data=img, details=details)

    out_file = tmp_path / "test_frame.fits"
    # Use public save_frame which delegates to FrameWriter
    save_status = vc.save_frame(status, str(out_file))
    assert save_status.is_success
    assert out_file.exists()

    with fits.open(out_file) as hdul:
        hdr = hdul[0].header
        data = hdul[0].data
        assert hdr.get('EXPTIME') == 10.0
        assert int(hdr.get('READOUT')) == 0
        assert data.shape == (100, 100)


