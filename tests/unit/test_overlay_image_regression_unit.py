from __future__ import annotations

import os
from pathlib import Path

from PIL import Image
import pytest

# Skip module if pytest-regressions is not available
pytest.importorskip("pytest_regressions")

# Gate snapshot test behind env var until real baseline is available
if os.environ.get("OST_ENABLE_IMAGE_REGRESSIONS") != "1":
    pytest.skip(
        "Image regression tests disabled (set OST_ENABLE_IMAGE_REGRESSIONS=1 to enable)",
        allow_module_level=True,
    )


def test_overlay_image_regression(cfg_no_ui, fake_simbad, tmp_path, image_regression):
    # Directory for baselines; skip if baseline not present to avoid spurious failures
    baseline_dir = Path(__file__).resolve().parents[1] / "_image_regressions"
    basename = "overlay_title_fov_secondary"
    baseline_path = baseline_dir / f"{basename}.png"
    if not baseline_path.exists():
        pytest.skip(
            "Image baseline missing; add _image_regressions/overlay_title_fov_secondary.png"
        )

    # Configure a deterministic overlay
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

    out = tmp_path / "overlay.png"
    gen = OverlayGenerator(config=cfg_no_ui)
    gen.generate_overlay(ra_deg=30.0, dec_deg=10.0, output_file=str(out), image_size=(200, 150))

    with Image.open(out) as img:
        image_regression.check(img.convert("RGBA"), basename=basename, directory=str(baseline_dir))
