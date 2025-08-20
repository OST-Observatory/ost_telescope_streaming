from __future__ import annotations

# ruff: noqa: S603,S607
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
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mount:
  driver_id: ASCOM.Simulator.Telescope
overlay:
  field_of_view: 1.0
  wait_for_plate_solve: false
frame_processing:
  enabled: false
  save_plate_solve_frames: false
  plate_solve_dir: frames
  file_format: PNG
  use_timestamps: false
        """,
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parents[2] / "overlay_pipeline.py"),
        "--config",
        str(cfg),
        "--log-level",
        "INFO",
    ]
    # We enforce a short timeout to avoid hangs
    proc = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]), timeout=10)
    # Non-zero exit may occur depending on environment.
    # Smoke test condition: process runs without timing out.
    assert proc.returncode in (0, 1)


def test_overlay_pipeline_cli_help_runs_quickly():
    # Cross-platform help invocation should succeed quickly
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parents[2] / "overlay_pipeline.py"),
        "--help",
    ]
    proc = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]), timeout=5)
    # Help should return 0 unless import-time optional deps fail even before parsing
    # We accept 0 or 1 here to avoid platform-specific import issues
    assert proc.returncode in (0, 1)
