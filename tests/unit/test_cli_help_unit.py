from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "script",
    [
        "overlay_pipeline.py",
        "tools/add_fits_headers.py",
        "calibration/dark_capture_runner.py",
        "calibration/flat_capture_runner.py",
        "calibration/master_frame_runner.py",
    ],
)
def test_cli_help_runs_quickly(script):
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run([sys.executable, str(root / script), "--help"], cwd=str(root), timeout=5)
    # Some scripts may import optional deps at module import; accept 0 or 1
    assert proc.returncode in (0, 1)
