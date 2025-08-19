import logging as _global_logging
import os
from pathlib import Path as _Path
import sys as _sys
import sysconfig as _sysconfig
from typing import Any

from config_manager import ConfigManager

# Ensure stdlib takes precedence for modules like 'code' (avoid shadowing by local 'code/' pkg)
try:
    _stdlib = _sysconfig.get_paths().get("stdlib")
    if _stdlib and _stdlib not in _sys.path:
        _sys.path.insert(0, _stdlib)
except Exception:
    pass
import pytest


def _has_module(modname: str) -> bool:
    try:
        __import__(modname)
        return True
    except Exception:
        return False


HAS_CV2 = _has_module("cv2")
HAS_ALPACA = _has_module("alpaca")
CAMERA_CONNECTED = os.environ.get("OST_CAMERA_CONNECTED", "0") in ("1", "true", "yes")


def pytest_ignore_collect(collection_path: _Path, config):
    """Skip certain tests when optional deps are missing. Uses pathlib Paths."""
    p = collection_path
    name = p.name
    # Skip integration and legacy directories unless explicitly requested via -m integration
    try:
        marker_expr = config.getoption("-m") or ""
    except Exception:
        marker_expr = ""
    parts = set(p.parts)
    if "integration" in parts and "integration" not in marker_expr:
        return True
    if "legacy" in parts:
        return True

    # Skip Alpaca-specific tests when alpaca lib is missing
    if not HAS_ALPACA and (
        name.startswith("test_alpaca_") or name == "test_overlay_runner_alpaca.py"
    ):
        return True

    # Skip cv2-dependent tests that import cv2 directly
    if not HAS_CV2 and name in {
        "test_image_orientation.py",
        "test_video_system.py",
    }:
        return True

    # If no real camera is connected, skip camera integration-heavy tests
    if not CAMERA_CONNECTED and name in {
        "test_ascom_camera.py",
        "test_cooling_cache.py",
        "test_cooling_debug.py",
        "test_cooling_power.py",
        "test_image_orientation.py",
        "test_final_integration.py",
        "test_video_system.py",
        "test_zwo_direct.py",
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
    data = np.ones((10, 10), dtype=np.uint16) * 100
    f = tmp_path / "dummy.fits"
    hdu = fits.PrimaryHDU(data)
    hdu.writeto(f, overwrite=True)
    return str(f)


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "out"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


# Shared test fixtures/utilities


@pytest.fixture
def cfg_no_ui():
    class _Cfg:
        def get_overlay_config(self) -> dict[str, Any]:
            return {
                "title": {"enabled": False},
                "info_panel": {"enabled": False},
                "secondary_fov": {"enabled": False},
                "include_no_magnitude": True,
                "image_size": [200, 150],
            }

        def get_display_config(self) -> dict[str, Any]:
            return {
                "object_color": [255, 0, 0],
                "text_color": [255, 255, 255],
                "marker_size": 5,
                "text_offset": [8, -8],
            }

        def get_advanced_config(self) -> dict[str, Any]:
            return {"save_empty_overlays": True}

        def get_platform_config(self) -> dict[str, Any]:
            return {"fonts": {"linux": []}}

        # Minimal stubs for other consumers
        def get_telescope_config(self) -> dict[str, Any]:
            return {"focal_length": 1000, "aperture": 200, "focal_ratio": 5.0, "type": "Newt"}

        def get_camera_config(self) -> dict[str, Any]:
            return {
                "camera_type": "opencv",
                "sensor_width": 23.5,
                "sensor_height": 15.6,
                "pixel_size": 3.76,
                "bit_depth": 16,
                "cooling": {"enable_cooling": False},
            }

        def get_frame_processing_config(self) -> dict[str, Any]:
            return {
                "enabled": False,
                "plate_solve_dir": "frames",
                "file_format": "PNG",
                "use_timestamps": False,
                "save_plate_solve_frames": False,
            }

        def get_plate_solve_config(self) -> dict[str, Any]:
            return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 0}

        def get_mount_config(self) -> dict[str, Any]:
            return {"slewing_detection": {"enabled": False}}

    return _Cfg()


@pytest.fixture
def fake_simbad(monkeypatch):
    import sys as _sys
    import types as _types

    class _FakeRow:
        def __init__(self, data: dict):
            self._data = data
            self.colnames = list(data.keys())

        def __getitem__(self, key: str):
            return self._data[key]

        def get(self, key: str, default=None):
            return self._data.get(key, default)

    class _FakeResult:
        def __init__(self, rows):
            self._rows = [_FakeRow(r) for r in rows]

        def __len__(self) -> int:
            return len(self._rows)

        def __iter__(self):
            return iter(self._rows)

        @property
        def colnames(self):
            return self._rows[0].colnames if self._rows else []

    class _FakeSimbad:
        def __init__(self):
            self._fields = []

        @staticmethod
        def list_votable_fields():
            return []

        def reset_votable_fields(self):
            self._fields = []

        def add_votable_fields(self, *args):
            self._fields.extend(args)

        def query_region(self, center, radius):  # noqa: ARG002
            rows = [
                {
                    "ra": center.ra.degree,
                    "dec": center.dec.degree,
                    "V": 8.0,
                    "otype": "Star",
                    "main_id": "C",
                }
            ]
            return _FakeResult(rows)

    astro_mod = _types.ModuleType("astroquery")
    simbad_mod = _types.ModuleType("astroquery.simbad")
    simbad_mod.Simbad = _FakeSimbad
    monkeypatch.setitem(_sys.modules, "astroquery", astro_mod)
    monkeypatch.setitem(_sys.modules, "astroquery.simbad", simbad_mod)
    return _FakeSimbad


@pytest.fixture
def data_assets(tmp_path):
    """Create tiny sample assets (PNG, and FITS if astropy available)."""
    from PIL import Image as _Image

    assets: dict[str, str] = {}

    # Tiny PNG
    png = tmp_path / "sample.png"
    _Image.new("RGBA", (10, 8), (0, 0, 255, 128)).save(png)
    assets["png"] = str(png)

    # Optional FITS
    try:
        import astropy.io.fits as _fits
        import numpy as _np

        fits_path = tmp_path / "sample.fits"
        _fits.PrimaryHDU(_np.zeros((8, 6), dtype=_np.uint16)).writeto(fits_path)
        assets["fits"] = str(fits_path)
    except Exception:
        pass

    return assets
