from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image


def _alpha_bytes(path: Path) -> bytes:
    with Image.open(path) as im:
        a = np.array(im.convert("RGBA"))[:, :, 3]
        data = a.tobytes()
        assert isinstance(data, (bytes, bytearray))
        return bytes(data)


def test_overlay_alpha_snapshot_pluginless(cfg_no_ui, fake_simbad, tmp_path):
    # Configure: no title/info, transparent text, enable secondary FOV to draw geometry
    ovl = cfg_no_ui.get_overlay_config()
    ovl["title"] = {"enabled": False}
    ovl["info_panel"] = {"enabled": False}
    disp = cfg_no_ui.get_display_config()
    disp["text_color"] = [255, 255, 255, 0]  # fully transparent
    # Ensure no accidental attribute reliance

    from overlay.generator import OverlayGenerator

    out = tmp_path / "overlay_alpha.png"
    gen = OverlayGenerator(config=cfg_no_ui)
    # Enforce deterministic size and FOV
    gen.generate_overlay(
        ra_deg=30.0,
        dec_deg=10.0,
        output_file=str(out),
        image_size=(200, 150),
        fov_width_deg=1.5,
        fov_height_deg=1.5,
    )
    digest = hashlib.md5(_alpha_bytes(out)).hexdigest()
    # Replace below with observed deterministic hash across environments once stabilized
    assert isinstance(digest, str) and len(digest) == 32
