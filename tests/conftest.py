import sys
import os
from pathlib import Path

import pytest

from config_manager import ConfigManager
import logging


def _has_module(modname: str) -> bool:
    try:
        __import__(modname)
        return True
    except Exception:
        return False


HAS_CV2 = _has_module('cv2')
HAS_ALPACA = _has_module('alpaca')
CAMERA_CONNECTED = os.environ.get('OST_CAMERA_CONNECTED', '0') in ('1', 'true', 'yes')


def pytest_ignore_collect(path, config):
    """Skip certain tests when optional deps are missing."""
    p = Path(str(path))
    name = p.name

    # Skip Alpaca-specific tests when alpaca lib is missing
    if not HAS_ALPACA and (name.startswith('test_alpaca_') or name == 'test_overlay_runner_alpaca.py'):
        return True

    # Skip cv2-dependent tests that import cv2 directly
    if not HAS_CV2 and name in {
        'test_image_orientation.py',
        'test_video_system.py',
    }:
        return True

    # If no real camera is connected, skip camera integration-heavy tests
    if not CAMERA_CONNECTED and name in {
        'test_ascom_camera.py',
        'test_cooling_cache.py',
        'test_cooling_debug.py',
        'test_cooling_power.py',
        'test_image_orientation.py',
        'test_final_integration.py',
        'test_video_system.py',
        'test_zwo_direct.py',
    }:
        return True

    return False


@pytest.fixture
def config():
    """Provide a default ConfigManager for tests expecting a 'config' fixture."""
    return ConfigManager()


@pytest.fixture
def logger():
    """Provide a simple logger for tests expecting a 'logger' fixture."""
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    return _logging.getLogger("tests")


# Default logger fallbacks for tests that pass logger=None
import logging as _global_logging
if not _global_logging.getLogger().handlers:
    _global_logging.basicConfig(level=_global_logging.INFO)


@pytest.fixture
def camera_index():
    return 0


@pytest.fixture
def fits_path(tmp_path):
    """Create a minimal dummy FITS file for tests that require a FITS input."""
    try:
        import astropy.io.fits as fits
        import numpy as np
    except Exception:
        pytest.skip("astropy not available")
    data = (np.ones((10, 10), dtype=np.uint16) * 100)
    f = tmp_path / "dummy.fits"
    hdu = fits.PrimaryHDU(data)
    hdu.writeto(f, overwrite=True)
    return str(f)


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "out"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)
