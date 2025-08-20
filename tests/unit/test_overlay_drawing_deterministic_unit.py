import types

import numpy as np
import pytest


def _fake_simbad_module(monkeypatch: pytest.MonkeyPatch):
    # Minimal fake Simbad returning a small deterministic table-like object
    class _Row(dict):
        @property
        def colnames(self):
            return list(self.keys())

    class _FakeSimbad:
        def reset_votable_fields(self):
            pass

        def add_votable_fields(self, *args):
            pass

        def query_region(self, center, radius):
            # Return two objects with basic fields
            return [
                _Row(
                    {
                        "RA": center.ra.degree + 0.1,
                        "DEC": center.dec.degree,
                        "V": 8.0,
                        "otype": "G",
                        "main_id": "OBJ1",
                    }
                ),
                _Row(
                    {
                        "RA": center.ra.degree - 0.1,
                        "DEC": center.dec.degree,
                        "V": 9.0,
                        "otype": "OC",
                        "main_id": "OBJ2",
                    }
                ),
            ]

    fake_mod = types.SimpleNamespace(Simbad=_FakeSimbad)
    monkeypatch.setitem(__import__("sys").modules, "astroquery.simbad", fake_mod)
    # Ensure astroquery is importable
    monkeypatch.setitem(__import__("sys").modules, "astroquery", types.SimpleNamespace())


def test_overlay_with_fake_catalog_draws_objects(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from overlay.generator import OverlayGenerator

    _fake_simbad_module(monkeypatch)
    out = tmp_path / "ovl.png"
    gen = OverlayGenerator(config=None)
    path = gen.generate_overlay(
        ra_deg=10.0, dec_deg=20.0, output_file=str(out), image_size=(160, 120)
    )

    from PIL import Image

    with Image.open(path) as im:
        assert im.size == (160, 120)
        rgba = im.convert("RGBA")
        arr = np.array(rgba)
        # Basic assertion: should have some non-transparent content due to markers/text
        assert np.count_nonzero(arr[:, :, 3]) > 0
