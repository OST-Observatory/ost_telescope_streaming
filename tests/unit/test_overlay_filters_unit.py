from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _mock_simbad_rows(rows):
    # Reuse the shared fake_simbad fixture mechanism by patching sys.modules directly
    import sys
    import types

    class _Row:
        def __init__(self, d):
            self._d = d
            self.colnames = list(d.keys())

        def __getitem__(self, k):
            return self._d[k]

        def get(self, k, default=None):
            return self._d.get(k, default)

    class _Res:
        def __init__(self, rows):
            self._rows = [_Row(r) for r in rows]

        def __len__(self):
            return len(self._rows)

        def __iter__(self):
            return iter(self._rows)

        @property
        def colnames(self):
            return self._rows[0].colnames if self._rows else []

    class _Simbad:
        def reset_votable_fields(self):
            pass

        def add_votable_fields(self, *a):  # noqa: ARG002
            pass

        @staticmethod
        def list_votable_fields():
            return []

        def query_region(self, center, radius):  # noqa: ARG002
            return _Res(rows)

    astro = types.ModuleType("astroquery")
    simbad = types.ModuleType("astroquery.simbad")
    simbad.Simbad = _Simbad
    sys.modules["astroquery"] = astro
    sys.modules["astroquery.simbad"] = simbad


def _count_nontransparent(p: Path) -> int:
    a = np.array(Image.open(p).convert("RGBA"))
    return int((a[:, :, 3] > 0).sum())


def test_magnitude_limit_filters_objects(tmp_path, monkeypatch, cfg_no_ui):
    rows = [
        {"ra": 0.0, "dec": 0.0, "V": 8.0, "otype": "Star", "main_id": "A"},
        {"ra": 0.08, "dec": 0.05, "V": 11.0, "otype": "Star", "main_id": "B"},
    ]
    _mock_simbad_rows(rows)

    from overlay.generator import OverlayGenerator

    out1 = tmp_path / "m9.png"
    out2 = tmp_path / "m12.png"

    gen = OverlayGenerator(config=cfg_no_ui)
    gen.generate_overlay(
        ra_deg=0.0, dec_deg=0.0, output_file=str(out1), image_size=(200, 150), mag_limit=9.0
    )
    gen.generate_overlay(
        ra_deg=0.0, dec_deg=0.0, output_file=str(out2), image_size=(200, 150), mag_limit=12.0
    )

    # Fewer pixels should be drawn when mag limit is stricter (9.0)
    assert _count_nontransparent(out1) < _count_nontransparent(out2)


def test_object_type_filter(tmp_path, cfg_no_ui):
    rows = [
        {"ra": 0.0, "dec": 0.0, "V": 8.0, "otype": "G", "main_id": "G1"},
        {"ra": 0.05, "dec": 0.03, "V": 8.5, "otype": "Star", "main_id": "S1"},
    ]
    _mock_simbad_rows(rows)

    from overlay.generator import OverlayGenerator

    gen = OverlayGenerator(config=cfg_no_ui)
    # Restrict to galaxies only
    gen.object_types = ["G"]
    out = tmp_path / "otype_galaxies.png"
    gen.generate_overlay(ra_deg=0.0, dec_deg=0.0, output_file=str(out))
    # Should draw fewer pixels than when allowing both types
    base = tmp_path / "both.png"
    gen.object_types = []
    gen.generate_overlay(ra_deg=0.0, dec_deg=0.0, output_file=str(base))
    assert _count_nontransparent(out) < _count_nontransparent(base)


def test_exclude_objects_without_magnitude(tmp_path, cfg_no_ui):
    # Include one object with magnitude and one without
    rows = [
        {"ra": 0.0, "dec": 0.0, "V": 8.0, "otype": "Star", "main_id": "WithMag"},
        {"ra": 0.04, "dec": 0.03, "V": "--", "otype": "Star", "main_id": "NoMag"},
    ]
    _mock_simbad_rows(rows)

    from overlay.generator import OverlayGenerator

    # Baseline with include_no_magnitude = True
    cfg_no_ui.get_overlay_config()["include_no_magnitude"] = True
    gen = OverlayGenerator(config=cfg_no_ui)
    out_all = tmp_path / "all.png"
    gen.generate_overlay(ra_deg=0.0, dec_deg=0.0, output_file=str(out_all), image_size=(200, 150))

    # Now exclude objects without magnitude
    gen.include_no_magnitude = False
    out_filtered = tmp_path / "filtered.png"
    gen.generate_overlay(
        ra_deg=0.0, dec_deg=0.0, output_file=str(out_filtered), image_size=(200, 150)
    )

    assert _count_nontransparent(out_filtered) < _count_nontransparent(out_all)
