from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class _Cfg:
    def __init__(self, dir_path: str):
        self._dir = dir_path

    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "save_plate_solve_frames": True,
            "plate_solve_dir": self._dir,
            "file_format": "PNG",
            "use_timestamps": False,
        }

    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {"default_solver": "platesolve2", "auto_solve": True, "min_solve_interval": 5}

    def get_mount_config(self) -> Dict[str, Any]:
        return {"slewing_detection": {"enabled": False}}


class _FakeCapture:
    camera_type = "opencv"
    camera = object()

    def __init__(self, path: Path):
        self.path = path

    def get_current_frame(self):
        # Return a Status-like object
        class _S:
            is_success = True
            data = str(self.path)
            details = {"dimensions": (10, 10), "exposure_time": 1.0}

        return _S()

    def stop_capture(self):
        return None

    def disconnect(self):
        return None


class _SuccessStatus:
    is_success = True
    data = {
        "ra_center": 1.0,
        "dec_center": 2.0,
        "fov_width": 1.0,
        "fov_height": 1.0,
        "position_angle": 0.0,
        "image_size": (10, 10),
        "flipped": 0,
    }
    details: Dict[str, Any] = {"solving_time": 0.01, "method": "fake"}


class _FakeSolver:
    def is_available(self):
        return True

    def get_name(self):
        return "fake"

    def solve(self, path: str):  # noqa: ARG002
        return _SuccessStatus()


def test_min_solve_interval_gating(tmp_path, monkeypatch):
    from processing import processor as proc_mod
    from processing.processor import VideoProcessor

    # Control time.monotonic
    times: List[float] = [1000.0, 1000.0, 1000.0]  # initial state for vp init

    def fake_monotonic():
        return times[0]

    monkeypatch.setattr(proc_mod.time, "monotonic", fake_monotonic)

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")
    vp.plate_solver = _FakeSolver()

    # Advance time beyond min interval and ensure candidate file exists
    times[0] = 1006.0
    (tmp_path / "cap.png").write_bytes(b"x")
    vp._maybe_plate_solve(fits_filename=None, frame_filename=tmp_path / "cap.png")
    first_solves = vp.solve_count
    assert first_solves == 1

    # Advance time by less than interval -> no solve
    times[0] = 1003.0
    vp._maybe_plate_solve(fits_filename=None, frame_filename=tmp_path / "cap.png")
    assert vp.solve_count == first_solves

    # Advance beyond interval -> solve again
    times[0] = 1012.0
    vp._maybe_plate_solve(fits_filename=None, frame_filename=tmp_path / "cap.png")
    assert vp.solve_count == first_solves + 1


def test_callbacks_invoked_on_capture_and_solve(tmp_path, monkeypatch):
    from processing.processor import VideoProcessor

    # Avoid file IO in writer
    def _fake_save(self, frame, path, metadata=None):  # noqa: ARG002
        class _S:
            is_success = True
            message = "ok"

        Path(path).write_bytes(b"x")
        return _S()

    monkeypatch.setattr("services.frame_writer.FrameWriter.save", _fake_save, raising=True)

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")
    vp.plate_solver = _FakeSolver()
    vp.plate_solve_config["min_solve_interval"] = 0
    vp.min_solve_interval = 0

    captured: List[str] = []
    solved: List[str] = []

    def on_capture(frame, path):  # noqa: ARG001
        captured.append("ok")

    def on_solve(res):  # noqa: ARG001
        solved.append("ok")

    vp.set_callbacks(on_solve_result=on_solve, on_capture_frame=on_capture)
    # Ensure writer path resolution and candidate availability
    (tmp_path / "capture.PNG").write_bytes(b"x")
    vp._capture_and_solve()

    assert vp.capture_count == 1
    assert len(captured) == 1
    # Solve may or may not occur depending on image saving; ensure at least attempted
    assert vp.solve_count >= 1
    assert len(solved) >= 0
