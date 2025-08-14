import types

import pytest


class _Cfg:
    def get_overlay_config(self):
        return {
            "field_of_view": 1.5,
            "magnitude_limit": 10.0,
            "include_no_magnitude": True,
            "image_size": [160, 120],
            "default_filename": "overlay.png",
            "info_panel": {"enabled": False},
            "title": {
                "enabled": True,
                "text": "Snapshot",
                "position": "top_center",
                "font_size": 12,
                "font_color": [255, 255, 0, 255],
                "background_color": [0, 0, 0, 180],
            },
            "secondary_fov": {"enabled": False},
            "coordinates": {"ra_increases_left": True},
        }

    def get_display_config(self):
        return {
            "object_color": [255, 0, 0],
            "text_color": [255, 255, 255],
            "marker_size": 3,
            "text_offset": [8, -8],
        }

    def get_advanced_config(self):
        return {"save_empty_overlays": True, "debug_simbad": False}

    def get_platform_config(self):
        return {"fonts": {"linux": []}}

    def get_telescope_config(self):
        return {"focal_length": 1000, "aperture": 200, "focal_ratio": 5.0, "type": "Newtonian"}

    def get_camera_config(self):
        return {
            "camera_type": "opencv",
            "sensor_width": 23.5,
            "sensor_height": 15.6,
            "pixel_size": 3.76,
            "bit_depth": 16,
        }


def test_overlay_title_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from overlay.generator import OverlayGenerator

    # Ensure no astroquery side effects
    monkeypatch.setitem(__import__("sys").modules, "astroquery", types.SimpleNamespace())

    out = tmp_path / "snap.png"
    gen = OverlayGenerator(config=_Cfg())
    path = gen.generate_overlay(
        ra_deg=10.0, dec_deg=20.0, output_file=str(out), image_size=(160, 120)
    )

    from PIL import Image

    with Image.open(path) as im:
        assert im.size == (160, 120)
        assert im.mode in {"RGBA", "RGB", "L"}
        rgba = im.convert("RGBA")
        pixels = rgba.getdata()
        # When astroquery is unavailable, generator saves an empty transparent overlay
        non_transparent = sum(1 for r, g, b, a in pixels if a != 0)
        assert non_transparent == 0
