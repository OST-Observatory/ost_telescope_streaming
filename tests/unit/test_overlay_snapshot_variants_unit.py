from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _alpha(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.array(im.convert("RGBA"))[:, :, 3]


def test_overlay_flip_and_pa_change_pixels(cfg_no_ui, fake_simbad, tmp_path, monkeypatch):
    # Override SIMBAD to return off-center objects to ensure flip/PA change alpha mask
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

    class _Result:
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
            rows = [
                {
                    "ra": center.ra.degree + 0.05,
                    "dec": center.dec.degree + 0.03,
                    "V": 8.0,
                    "otype": "Star",
                    "main_id": "A",
                },
                {
                    "ra": center.ra.degree + 0.15,
                    "dec": center.dec.degree + 0.01,
                    "V": 9.0,
                    "otype": "G",
                    "main_id": "B",
                },
            ]
            return _Result(rows)

    astro = types.ModuleType("astroquery")
    simbad_mod = types.ModuleType("astroquery.simbad")
    simbad_mod.Simbad = _Simbad
    monkeypatch.setitem(sys.modules, "astroquery", astro)
    monkeypatch.setitem(sys.modules, "astroquery.simbad", simbad_mod)

    from overlay.generator import OverlayGenerator

    gen = OverlayGenerator(config=cfg_no_ui)

    base = tmp_path / "base.png"
    flip = tmp_path / "flip.png"
    pa90 = tmp_path / "pa90.png"

    gen.generate_overlay(ra_deg=30.0, dec_deg=10.0, output_file=str(base), image_size=(200, 150))
    gen.generate_overlay(
        ra_deg=30.0, dec_deg=10.0, output_file=str(flip), image_size=(200, 150), is_flipped=True
    )
    gen.generate_overlay(
        ra_deg=30.0,
        dec_deg=10.0,
        output_file=str(pa90),
        image_size=(200, 150),
        position_angle_deg=90.0,
    )

    a_base = _alpha(base)
    a_flip = _alpha(flip)
    a_pa = _alpha(pa90)

    # Compare alpha masks: flipped and PA images should differ from base significantly
    diff_flip = np.count_nonzero(a_base != a_flip)
    diff_pa = np.count_nonzero(a_base != a_pa)
    total = a_base.size
    assert diff_flip > total * 0.01  # at least 1% pixels differ
    assert diff_pa > total * 0.01
