from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _count_nontransparent(image_path: Path) -> int:
    img = Image.open(image_path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    return int((alpha > 0).sum())


def test_info_panel_empty_when_no_astroquery(cfg_no_ui, monkeypatch, tmp_path):
    # Current behavior: when astroquery unavailable, generator writes an empty overlay and returns
    monkeypatch.setitem(__import__("sys").modules, "astroquery", None)
    monkeypatch.setitem(__import__("sys").modules, "astroquery.simbad", None)

    ovl = cfg_no_ui.get_overlay_config()
    ovl["info_panel"] = {
        "enabled": True,
        "show_timestamp": False,
        "show_coordinates": True,
        "show_telescope_info": True,
        "show_camera_info": True,
        "show_fov_info": True,
        "position": "top_left",
        "width": 180,
        "padding": 6,
        "line_spacing": 4,
        "background_color": [0, 0, 0, 160],
    }

    from overlay.generator import OverlayGenerator

    out = tmp_path / "with_info.png"
    gen = OverlayGenerator(config=cfg_no_ui)
    gen.generate_overlay(ra_deg=12.0, dec_deg=34.0, output_file=str(out), image_size=(200, 150))
    assert _count_nontransparent(out) == 0


def test_info_panel_draws_with_fake_simbad(cfg_no_ui, fake_simbad, tmp_path):
    # With fake SIMBAD injected, generator proceeds to draw and the info panel should add pixels
    ovl = cfg_no_ui.get_overlay_config()
    ovl["info_panel"] = {
        "enabled": True,
        "show_timestamp": False,
        "show_coordinates": True,
        "show_telescope_info": True,
        "show_camera_info": True,
        "show_fov_info": True,
        "position": "top_left",
        "width": 180,
        "padding": 6,
        "line_spacing": 4,
        "background_color": [0, 0, 0, 160],
    }

    from overlay.generator import OverlayGenerator

    out = tmp_path / "with_info.png"
    gen = OverlayGenerator(config=cfg_no_ui)
    gen.generate_overlay(ra_deg=12.0, dec_deg=34.0, output_file=str(out), image_size=(200, 150))
    assert _count_nontransparent(out) > 0
