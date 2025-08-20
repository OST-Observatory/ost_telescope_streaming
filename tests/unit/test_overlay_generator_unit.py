import types
from typing import Any, Dict

import pytest


class _StubConfig:
    def get_overlay_config(self) -> Dict[str, Any]:
        return {
            "field_of_view": 1.5,
            "magnitude_limit": 10.0,
            "include_no_magnitude": True,
            "image_size": [100, 80],
            "max_name_length": 10,
            "default_filename": "overlay.png",
            "info_panel": {"enabled": False},
            "title": {"enabled": False},
            "secondary_fov": {"enabled": False},
            "coordinates": {"ra_increases_left": True},
        }

    def get_display_config(self) -> Dict[str, Any]:
        return {
            "object_color": [255, 0, 0],
            "text_color": [255, 255, 255],
            "marker_size": 3,
            "text_offset": [8, -8],
        }

    def get_advanced_config(self) -> Dict[str, Any]:
        return {"save_empty_overlays": True, "debug_simbad": False}

    def get_platform_config(self) -> Dict[str, Any]:
        return {"fonts": {"linux": []}}

    def get_telescope_config(self) -> Dict[str, Any]:
        return {"focal_length": 1000, "aperture": 200, "focal_ratio": 5.0, "type": "Newtonian"}

    def get_camera_config(self) -> Dict[str, Any]:
        return {
            "camera_type": "opencv",
            "sensor_width": 23.5,
            "sensor_height": 15.6,
            "pixel_size": 3.76,
            "bit_depth": 16,
        }


def test_overlay_generator_creates_empty_overlay_when_no_astroquery(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    from overlay.generator import OverlayGenerator

    # Break astroquery import path inside generate_overlay
    monkeypatch.setitem(__import__("sys").modules, "astroquery", types.SimpleNamespace())

    out = tmp_path / "ovl.png"
    gen = OverlayGenerator(config=_StubConfig())
    path_str = gen.generate_overlay(
        ra_deg=10.0, dec_deg=20.0, output_file=str(out), image_size=(100, 80)
    )

    # Assert file exists and basic properties
    import os

    assert os.path.exists(path_str)
    try:
        from PIL import Image
    except Exception:
        pytest.skip("Pillow not available")
    with Image.open(path_str) as im:
        assert im.size == (100, 80)
        assert im.mode in {"RGBA", "RGB", "L"}


def test_overlay_generator_projection_and_title(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from overlay.generator import OverlayGenerator

    # Force astroquery to be unavailable to avoid network
    monkeypatch.setitem(__import__("sys").modules, "astroquery", types.SimpleNamespace())

    class _Cfg(_StubConfig):
        def get_overlay_config(self) -> Dict[str, Any]:
            cfg = super().get_overlay_config()
            cfg.update(
                {
                    "title": {
                        "enabled": True,
                        "text": "Test Title",
                        "position": "top_center",
                        "font_size": 12,
                        "font_color": [255, 255, 0, 255],
                        "background_color": [0, 0, 0, 180],
                    },
                    "info_panel": {"enabled": False},
                }
            )
            return cfg

    out = tmp_path / "ovl2.png"
    gen = OverlayGenerator(config=_Cfg())
    path_str = gen.generate_overlay(
        ra_deg=10.0,
        dec_deg=20.0,
        output_file=str(out),
        fov_width_deg=2.0,
        fov_height_deg=1.5,
        position_angle_deg=90.0,
        image_size=(120, 90),
    )

    import os

    assert os.path.exists(path_str)
    try:
        from PIL import Image
    except Exception:
        pytest.skip("Pillow not available")
    with Image.open(path_str) as im:
        assert im.size == (120, 90)
