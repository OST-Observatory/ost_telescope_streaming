from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class _Cfg:
    def __init__(self, dir_path: str):
        self._dir = dir_path

    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "save_plate_solve_frames": False,
            "plate_solve_dir": self._dir,
            "file_format": "PNG",
            "use_timestamps": False,
        }

    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 0}

    def get_mount_config(self) -> Dict[str, Any]:
        return {"slewing_detection": {"enabled": False}}


class _FakeCapture:
    camera_type = "opencv"
    camera = object()

    def __init__(self, path: Path):
        self.path = path
        self._current_frame = object()

    def start_capture(self):
        path_str = str(self.path)

        class _Status:
            is_success = True
            data = path_str

        return _Status()

    def stop_capture(self):
        return None

    def disconnect(self):
        return None

    def get_current_frame(self):
        return self._current_frame


def test_video_processor_callbacks(tmp_path, monkeypatch):
    from processing.processor import VideoProcessor

    # Fake FrameWriter.save to avoid IO
    def _fake_save(self, frame, path, metadata=None):  # noqa: ARG002
        class _S:
            is_success = True
            message = "ok"

        Path(path).write_bytes(b"x")
        return _S()

    monkeypatch.setattr("services.frame_writer.FrameWriter.save", _fake_save, raising=True)

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")

    # Track callbacks
    events = {"solve": 0, "capture": 0, "error": 0}

    def on_solve(res):  # noqa: ARG001
        events["solve"] += 1

    def on_cap(frame, path):  # noqa: ARG001
        events["capture"] += 1

    def on_err(exc):  # noqa: ARG001
        events["error"] += 1

    vp.set_callbacks(on_solve_result=on_solve, on_capture_frame=on_cap, on_error=on_err)

    # Run a single cycle via private method to avoid thread complexity
    vp._capture_and_solve()

    assert events["capture"] == 1
    # No solver configured, so no solve callback
    assert events["solve"] == 0
    assert events["error"] == 0
