from pathlib import Path

import numpy as np
from processing.processor import VideoProcessor
import pytest


@pytest.mark.integration
def test_stack_rollover_creates_named_snapshot(tmp_path: Path, monkeypatch):
    class DummyConfig:
        def __init__(self):
            self._cfg = {
                "frame_processing": {
                    "enabled": True,
                    "plate_solve_dir": str(tmp_path / "frames"),
                    "file_format": "PNG",
                    "stacking": {
                        "enabled": True,
                        "method": "median",
                        "sigma_clip": {"enabled": False},
                        "max_frames": 100,
                        "output_format": ["png"],
                    },
                },
                "plate_solve": {"auto_solve": False},
            }

        def get_frame_processing_config(self):
            return self._cfg["frame_processing"]

        def get_plate_solve_config(self):
            return self._cfg["plate_solve"]

        def get_mount_config(self):
            return {}

    cfg = DummyConfig()
    vp = VideoProcessor(config=cfg)
    # Prepare stacker
    from processing.stacker import FrameStacker

    stacks_dir = Path(cfg.get_frame_processing_config()["plate_solve_dir"]) / "stacks"
    vp.stacker = FrameStacker(output_dir=stacks_dir)
    # Add some frames to make a non-empty stack
    for _ in range(3):
        vp.stacker.add_frame((np.ones((16, 16), dtype=np.uint8) * 50))

    # Provide last solve result coords for naming
    class R:
        ra_center = 123.456
        dec_center = -12.345

    vp.last_solve_result = R()

    # Trigger rollover
    vp._rollover_stack(reason="test")

    # Expect a file with stack_ prefix in stacks_dir
    assert stacks_dir.exists()
    files = list(stacks_dir.glob("stack_*.png"))
    assert files, "Expected a rolled-over stack PNG file"
    # Name should contain RA/DEC
    assert any("RA" in f.name and "DEC" in f.name for f in files)
