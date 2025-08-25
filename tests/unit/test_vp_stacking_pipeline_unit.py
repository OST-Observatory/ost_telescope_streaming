import os
from pathlib import Path

import numpy as np
from processing.processor import VideoProcessor


class DummyConfig:
    def __init__(self):
        self._cfg = {
            "frame_processing": {
                "enabled": True,
                "plate_solve_dir": "plate_solve_frames",
                "file_format": "PNG",
                "stacking": {
                    "enabled": True,
                    "method": "median",
                    "sigma_clip": {"enabled": True, "sigma": 3.0},
                    "max_frames": 5,
                    "write_interval_s": 1,
                    "min_frames_for_stack_solve": 1,
                    "output_format": ["png"],
                },
            },
            "plate_solve": {"auto_solve": False},
            "overlay": {"update": {"update_interval": 1}},
        }

    def get_frame_processing_config(self):
        return self._cfg["frame_processing"]

    def get_plate_solve_config(self):
        return self._cfg["plate_solve"]

    def get_mount_config(self):
        return {}

    def get_overlay_config(self):
        return self._cfg.get("overlay", {})


def test_vp_sets_base_paths_without_overlay(tmp_path: Path, monkeypatch):
    cfg = DummyConfig()
    vp = VideoProcessor(config=cfg)
    # Prepare writer dir
    vp.frame_dir = tmp_path
    vp.stacking_enabled = True
    # Initialize stacker
    from processing.stacker import FrameStacker

    vp.stacker = FrameStacker(output_dir=tmp_path)

    # Mock obtain_frame to return a simple numpy image wrapped as (data, details)
    def fake_obtain():
        img = np.ones((16, 16), dtype=np.uint8) * 100
        return (img, {"exposure_time_s": 1.0})

    monkeypatch.setattr(vp, "_obtain_frame", fake_obtain)

    # Mock save to avoid OpenCV/astropy dependency
    class DummyWriter:
        def save(self, frame, filename, metadata=None):
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            # create a small PNG-ish file to satisfy existence checks
            with open(filename, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")

            class S:
                is_success = True
                data = filename

            return S()

    vp.frame_writer = DummyWriter()
    vp.capture_count = 1
    # Run one capture via worker loop body
    vp._capture_worker = lambda: None  # prevent thread start
    # Directly execute a shortened version: save outputs and push to stack
    frame = fake_obtain()
    frame_png, frame_fits = vp._save_outputs(frame)
    assert frame_png is not None
    vp.stacker.add_frame(frame[0])
    # Solve-only cycle should pick stack or last single and set base paths
    vp._solve_only_cycle_with_stacking()
    assert vp.last_overlay_base_png is not None
    assert os.path.exists(str(vp.last_overlay_base_png))
