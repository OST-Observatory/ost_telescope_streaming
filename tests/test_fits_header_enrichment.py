from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, 'code')
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from utils.fits_utils import enrich_header_from_metadata


class DummyCamera:
    def __init__(self):
        self.name = 'testcam'
        self.ccdtemperature = -10.0
        self.cooler_power = 35.0
        self.cooler_on = True
        self.sensor_type = 'RGGB'


class DummyConfig:
    def __init__(self):
        self._camera = {
            'pixel_size': 3.76,
            'sensor_width': 23.5,
            'sensor_height': 15.6,
            'ascom': {'gain': 100, 'offset': 50, 'readout_mode': 0},
        }
        self._telescope = {'focal_length': 400.0}

    def get_camera_config(self):
        return self._camera

    def get_telescope_config(self):
        return self._telescope

    def get_frame_processing_config(self):
        return {}


def test_enrich_header_adds_core_keys():
    try:
        import astropy.io.fits as fits
    except Exception:
        return  # skip if astropy not installed

    header = fits.Header()
    frame_details = {
        'exposure_time_s': 10.0,
        'gain': 100,
        'offset': 50,
        'readout_mode': 0,
        'binning': 1,
        'calibration_applied': True,
        'dark_subtraction_applied': True,
        'flat_correction_applied': False,
        'master_dark_used': 'master_frames/master_dark_10s_20250101.fits',
    }
    camera = DummyCamera()
    config = DummyConfig()
    enrich_header_from_metadata(header, frame_details, camera, config, 'alpaca', logger=None)

    # Core exposure/gain/offset/readout
    assert 'EXPTIME' in header and header['EXPTIME'] == 10.0
    assert 'GAIN' in header and float(header['GAIN']) == 100.0
    assert 'OFFSET' in header and float(header['OFFSET']) == 50.0
    assert 'READOUT' in header and int(header['READOUT']) == 0

    # Sensor/optics
    assert 'XPIXSZ' in header and header['XPIXSZ'] == 3.76
    assert 'FOCALLEN' in header and header['FOCALLEN'] == 400.0

    # Cooling
    assert 'CCD-TEMP' in header
    assert 'COOLERON' in header

    # Calibration flags
    assert header.get('DARKCOR') is True
    assert header.get('FLATCOR') is False
    assert 'MSTDARK' in header


