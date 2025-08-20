from __future__ import annotations

from pathlib import Path
import sys
import types
from typing import Any, cast

import numpy as np
from PIL import Image
import pytest


def _count_nontransparent_pixels(image_path: Path) -> int:
    img = Image.open(image_path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    return int((alpha > 0).sum())


class _CfgNoUI:
    def __init__(self):
        self._ovl = {
            "title": {"enabled": False},
            "info_panel": {"enabled": False},
            "secondary_fov": {"enabled": False},
        }

    def get_overlay_config(self):
        return self._ovl

    def get_display_config(self):
        return {
            "object_color": [255, 0, 0],
            "text_color": [255, 255, 255],
            "marker_size": 5,
            "text_offset": [8, -8],
        }

    def get_advanced_config(self):
        return {"save_empty_overlays": True}

    def get_platform_config(self):
        return {"fonts": {"linux": []}}


def test_empty_overlay_when_astroquery_missing(tmp_path, monkeypatch) -> None:
    # Ensure from astroquery.simbad import Simbad fails inside generator
    monkeypatch.setitem(sys.modules, "astroquery", types.ModuleType("astroquery"))
    # Also ensure any preloaded submodule is removed
    monkeypatch.setitem(sys.modules, "astroquery.simbad", None)

    # Lazy import after monkeypatch
    from overlay.generator import OverlayGenerator

    out_path = tmp_path / "overlay_empty.png"
    gen = OverlayGenerator(config=_CfgNoUI())
    result = gen.generate_overlay(
        ra_deg=180.0,
        dec_deg=0.0,
        output_file=str(out_path),
        image_size=(120, 90),
    )

    assert Path(result).exists()
    non_transparent = _count_nontransparent_pixels(out_path)
    assert non_transparent == 0


def test_overlay_with_mocked_simbad_nonempty(tmp_path, monkeypatch) -> None:
    # Build a minimal fake Simbad API
    class FakeRow:
        def __init__(self, data: dict):
            self._data = data
            self.colnames = list(data.keys())

        def __getitem__(self, key: str):
            return self._data[key]

        def get(self, key: str, default=None):
            return self._data.get(key, default)

    class FakeResult:
        def __init__(self, rows: list[dict]):
            self._rows = [FakeRow(r) for r in rows]

        def __len__(self) -> int:
            return len(self._rows)

        def __iter__(self):
            return iter(self._rows)

        @property
        def colnames(self):
            return self._rows[0].colnames if self._rows else []

    class FakeSimbad:
        def __init__(self):
            self._fields = []

        @staticmethod
        def list_votable_fields():
            # Keep simple; drawing works without dimension fields
            return []

        def reset_votable_fields(self):
            self._fields = []

        def add_votable_fields(self, *args):
            self._fields.extend(args)

        def query_region(self, center, radius):  # noqa: ARG002 - signature match
            # Two objects near center, within image bounds
            rows = [
                {
                    "ra": center.ra.degree,
                    "dec": center.dec.degree,
                    "V": 8.0,
                    "otype": "Star",
                    "main_id": "CenterStar",
                },
                {
                    "ra": center.ra.degree + 0.05,
                    "dec": center.dec.degree + 0.03,
                    "V": 9.5,
                    "otype": "G",
                    "main_id": "Obj2",
                },
            ]
            return FakeResult(rows)

    # Prepare module structure astroquery.simbad.Simbad = FakeSimbad
    astroquery_mod = types.ModuleType("astroquery")
    simbad_mod = cast(Any, types.ModuleType("astroquery.simbad"))
    simbad_mod.Simbad = FakeSimbad
    monkeypatch.setitem(sys.modules, "astroquery", astroquery_mod)
    monkeypatch.setitem(sys.modules, "astroquery.simbad", simbad_mod)

    from overlay.generator import OverlayGenerator

    out_path = tmp_path / "overlay_mock.png"
    gen = OverlayGenerator(config=_CfgNoUI())
    result = gen.generate_overlay(
        ra_deg=210.0,
        dec_deg=10.0,
        output_file=str(out_path),
        image_size=(160, 120),
        mag_limit=12.0,
    )

    assert Path(result).exists()
    non_transparent = _count_nontransparent_pixels(out_path)
    # Expect some drawing occurred
    assert non_transparent > 0


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

    # Ensure no astroquery side effects: remove module so generator treats it as unavailable
    monkeypatch.setitem(__import__("sys").modules, "astroquery", None)
    monkeypatch.setitem(__import__("sys").modules, "astroquery.simbad", None)

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
