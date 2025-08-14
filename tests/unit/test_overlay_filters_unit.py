from __future__ import annotations

from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image


def _mock_simbad_rows(rows):
    class FakeRow:
        def __init__(self, data: dict):
            self._data = data
            self.colnames = list(data.keys())

        def __getitem__(self, key: str):
            return self._data[key]

        def get(self, key: str, default=None):
            return self._data.get(key, default)

    class FakeResult:
        def __init__(self, rows):
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
            return []

        def reset_votable_fields(self):
            self._fields = []

        def add_votable_fields(self, *args):
            self._fields.extend(args)

        def query_region(self, center, radius):  # noqa: ARG002 - signature match
            return FakeResult(rows)

    astroquery_mod = types.ModuleType("astroquery")
    simbad_mod = types.ModuleType("astroquery.simbad")
    simbad_mod.Simbad = FakeSimbad
    sys.modules["astroquery"] = astroquery_mod
    sys.modules["astroquery.simbad"] = simbad_mod


def _count_nontransparent(p: Path) -> int:
    a = np.array(Image.open(p).convert("RGBA"))
    return int((a[:, :, 3] > 0).sum())


def test_magnitude_limit_filters_objects(tmp_path, monkeypatch):
    rows = [
        {"ra": 0.0, "dec": 0.0, "V": 8.0, "otype": "Star", "main_id": "A"},
        {"ra": 0.08, "dec": 0.05, "V": 11.0, "otype": "Star", "main_id": "B"},
    ]
    _mock_simbad_rows(rows)

    from overlay.generator import OverlayGenerator

    out1 = tmp_path / "m9.png"
    out2 = tmp_path / "m12.png"

    class _CfgNoUI:
        def get_overlay_config(self):
            return {
                "title": {"enabled": False},
                "info_panel": {"enabled": False},
                "secondary_fov": {"enabled": False},
            }

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

    gen = OverlayGenerator(config=_CfgNoUI())
    gen.generate_overlay(
        ra_deg=0.0, dec_deg=0.0, output_file=str(out1), image_size=(200, 150), mag_limit=9.0
    )
    gen.generate_overlay(
        ra_deg=0.0, dec_deg=0.0, output_file=str(out2), image_size=(200, 150), mag_limit=12.0
    )

    # Fewer pixels should be drawn when mag limit is stricter (9.0)
    assert _count_nontransparent(out1) < _count_nontransparent(out2)


def test_object_type_filter(tmp_path):
    rows = [
        {"ra": 0.0, "dec": 0.0, "V": 8.0, "otype": "G", "main_id": "G1"},
        {"ra": 0.05, "dec": 0.03, "V": 8.5, "otype": "Star", "main_id": "S1"},
    ]
    _mock_simbad_rows(rows)

    from overlay.generator import OverlayGenerator

    class _CfgNoUI:
        def get_overlay_config(self):
            return {
                "title": {"enabled": False},
                "info_panel": {"enabled": False},
                "secondary_fov": {"enabled": False},
            }

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

    gen = OverlayGenerator(config=_CfgNoUI())
    # Restrict to galaxies only
    gen.object_types = ["G"]
    out = tmp_path / "otype_galaxies.png"
    gen.generate_overlay(ra_deg=0.0, dec_deg=0.0, output_file=str(out))
    # Should draw fewer pixels than when allowing both types
    base = tmp_path / "both.png"
    gen.object_types = []
    gen.generate_overlay(ra_deg=0.0, dec_deg=0.0, output_file=str(base))
    assert _count_nontransparent(out) < _count_nontransparent(base)
