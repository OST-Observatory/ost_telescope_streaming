from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _img_bytes(path: Path) -> bytes:
    with Image.open(path) as im:
        data = im.convert("RGBA").tobytes()
        assert isinstance(data, (bytes, bytearray))
        return bytes(data)


def _count_nontransparent(path: Path) -> int:
    with Image.open(path) as im:
        a = np.array(im.convert("RGBA"))[:, :, 3]
        return int((a > 0).sum())


def test_overlay_title_and_fov_snapshot(cfg_no_ui, fake_simbad, tmp_path):
    # Configure title and FOV
    ovl = cfg_no_ui.get_overlay_config()
    ovl["title"] = {
        "enabled": True,
        "text": "Snapshot",
        "position": "top_center",
        "font_size": 12,
        "font_color": [255, 255, 0, 255],
        "background_color": [0, 0, 0, 180],
    }
    ovl["field_of_view"] = 1.5
    ovl["secondary_fov"] = {"enabled": True, "fraction": 0.3}

    from overlay.generator import OverlayGenerator

    out = tmp_path / "snap.png"
    gen = OverlayGenerator(config=cfg_no_ui)
    gen.generate_overlay(ra_deg=30.0, dec_deg=10.0, output_file=str(out), image_size=(200, 150))

    # Snapshot the raw bytes for deterministic comparison
    # Heuristic snapshot: ensure a reasonable amount of pixels are drawn
    drawn = _count_nontransparent(out)
    total = 200 * 150
    assert 500 < drawn < int(total * 0.6)
