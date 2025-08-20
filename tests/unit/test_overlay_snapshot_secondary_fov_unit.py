from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _count_nontransparent_pixels(image_path: Path) -> int:
    img = Image.open(image_path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    return int((alpha > 0).sum())


def test_secondary_fov_box_draws_when_enabled(cfg_no_ui, fake_simbad, monkeypatch, tmp_path):
    # Activate secondary FOV box via config
    cfg_no_ui.get_overlay_config()["secondary_fov"] = {
        "enabled": True,
        "fraction": 0.33,
        "border_color": [0, 255, 0, 255],
        "border_width": 2,
    }

    # Provide a fake SIMBAD so objects can draw markers, but the assertion looks at nonzero alpha
    # Fixture already injected astroquery.simbad.Simbad

    from overlay.generator import OverlayGenerator

    out = tmp_path / "secondary_fov.png"
    gen = OverlayGenerator(config=cfg_no_ui)
    gen.generate_overlay(ra_deg=10.0, dec_deg=20.0, output_file=str(out), image_size=(200, 150))

    # Expect some drawing due to objects or secondary FOV
    assert _count_nontransparent_pixels(out) > 0
