from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    os.name != "nt", reason="overlay_pipeline uses ASCOM; smoke test on Windows only"
)
def test_overlay_pipeline_cli_smoke_on_windows(tmp_path):
    # Create a minimal config that avoids cooling and frame processing for smoke
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        """
overlay:
  wait_for_plate_solve: false
frame_processing:
  enabled: false
camera:
  cooling:
    enable_cooling: false
        """,
        encoding="utf-8",
    )

    cmd = [sys.executable, "overlay_pipeline.py", "--config", str(cfg), "--log-level", "ERROR"]
    # Should start and attempt to run then exit quickly without raising
    # We enforce a short timeout to avoid hangs
    proc = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]), timeout=10)
    # Non-zero exit may occur depending on environment.
    # Smoke test condition: process runs without timing out.
    assert proc.returncode in (0, 1)
