from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _count_nontransparent_pixels(image_path: Path) -> int:
    img = Image.open(image_path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    return int((alpha > 0).sum())


def test_overlay_edges_flip_and_pa(cfg_no_ui, monkeypatch, tmp_path):
    # Ensure astroquery is unavailable to force empty overlay (transparent)
    monkeypatch.setitem(__import__("sys").modules, "astroquery", None)
    monkeypatch.setitem(__import__("sys").modules, "astroquery.simbad", None)

    from overlay.generator import OverlayGenerator

    gen = OverlayGenerator(config=cfg_no_ui)

    out_base = tmp_path / "base.png"
    out_flip = tmp_path / "flip.png"
    out_pa = tmp_path / "pa.png"

    # Base overlay
    gen.generate_overlay(
        ra_deg=123.0, dec_deg=-20.0, output_file=str(out_base), image_size=(160, 120)
    )
    # Flipped overlay (should be equally transparent since no astroquery)
    gen.generate_overlay(
        ra_deg=123.0,
        dec_deg=-20.0,
        output_file=str(out_flip),
        image_size=(160, 120),
        is_flipped=True,
    )
    # Large position angle
    gen.generate_overlay(
        ra_deg=123.0,
        dec_deg=-20.0,
        output_file=str(out_pa),
        image_size=(160, 120),
        position_angle_deg=135.0,
    )

    assert _count_nontransparent_pixels(out_base) == 0
    assert _count_nontransparent_pixels(out_flip) == 0
    assert _count_nontransparent_pixels(out_pa) == 0
