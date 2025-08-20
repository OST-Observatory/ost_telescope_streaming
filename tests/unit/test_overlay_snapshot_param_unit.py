from __future__ import annotations

from pathlib import Path
import sys
import types
from typing import Any, cast

import numpy as np
from PIL import Image
import pytest


def _as_rgba_array(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGBA"))


def _mock_simbad(monkeypatch: pytest.MonkeyPatch) -> None:
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
            return []

        def reset_votable_fields(self):
            self._fields = []

        def add_votable_fields(self, *args):
            self._fields.extend(args)

        def query_region(self, center, radius):  # noqa: ARG002 - signature match
            rows = [
                {
                    "ra": center.ra.degree + 0.12,
                    "dec": center.dec.degree + 0.06,
                    "V": 8.5,
                    "otype": "G",
                    "main_id": "A",
                },
                {
                    "ra": center.ra.degree - 0.08,
                    "dec": center.dec.degree + 0.05,
                    "V": 9.0,
                    "otype": "Star",
                    "main_id": "B",
                },
                {
                    "ra": center.ra.degree + 0.05,
                    "dec": center.dec.degree - 0.07,
                    "V": 8.0,
                    "otype": "OC",
                    "main_id": "C",
                },
            ]
            return FakeResult(rows)

    astroquery_mod = types.ModuleType("astroquery")
    simbad_mod = cast(Any, types.ModuleType("astroquery.simbad"))
    simbad_mod.Simbad = FakeSimbad
    monkeypatch.setitem(sys.modules, "astroquery", astroquery_mod)
    monkeypatch.setitem(sys.modules, "astroquery.simbad", simbad_mod)


@pytest.mark.parametrize("is_flipped,pa_deg", [(False, 0.0), (True, 0.0), (False, 90.0)])
def test_overlay_parametrized_snapshot(tmp_path, monkeypatch, is_flipped, pa_deg):
    _mock_simbad(monkeypatch)
    from config_manager import ConfigManager
    from overlay.generator import OverlayGenerator

    out = tmp_path / f"ovl_f{int(is_flipped)}_pa{int(pa_deg)}.png"
    gen = OverlayGenerator(config=ConfigManager())
    path = gen.generate_overlay(
        ra_deg=100.0,
        dec_deg=22.0,
        output_file=str(out),
        image_size=(200, 150),
        fov_width_deg=1.2,
        fov_height_deg=1.0,
        position_angle_deg=pa_deg,
        is_flipped=is_flipped,
    )
    arr = _as_rgba_array(Path(path))
    assert (arr[:, :, 3] > 0).any()


def test_overlay_differs_when_pa_changes(tmp_path, monkeypatch):
    _mock_simbad(monkeypatch)
    from config_manager import ConfigManager
    from overlay.generator import OverlayGenerator

    gen = OverlayGenerator(config=ConfigManager())
    p0 = tmp_path / "ovl_pa0.png"
    p90 = tmp_path / "ovl_pa90.png"
    gen.generate_overlay(
        ra_deg=250.0,
        dec_deg=-10.0,
        output_file=str(p0),
        image_size=(220, 160),
        position_angle_deg=0.0,
    )
    gen.generate_overlay(
        ra_deg=250.0,
        dec_deg=-10.0,
        output_file=str(p90),
        image_size=(220, 160),
        position_angle_deg=90.0,
    )

    a0 = _as_rgba_array(p0)
    a90 = _as_rgba_array(p90)
    # Images should not be identical when PA differs significantly
    assert not np.array_equal(a0, a90)
