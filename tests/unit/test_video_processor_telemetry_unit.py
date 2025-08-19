from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class _Cfg:
    def __init__(self, dir_path: str):
        self._dir = dir_path

    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "save_plate_solve_frames": True,
            "plate_solve_dir": self._dir,
            "file_format": "PNG",
            "use_timestamps": True,
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

    def get_current_frame(self):
        path_str = str(self.path)

        class _S:
            is_success = True
            data = path_str
            details = {"dimensions": (10, 10), "exposure_time_s": 1.5}

        return _S()

    def stop_capture(self):
        return None

    def disconnect(self):
        return None


def _fake_save(self, frame, path, metadata=None):  # noqa: ARG002
    class _S:
        is_success = True
        message = "ok"

    Path(path).write_bytes(b"x")
    return _S()


def test_telemetry_logs_present(tmp_path, monkeypatch, caplog):
    from processing.processor import VideoProcessor

    monkeypatch.setattr("services.frame_writer.FrameWriter.save", _fake_save, raising=True)

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")

    caplog.clear()
    vp._capture_and_solve()

    msgs = [r.getMessage() for r in caplog.records]
    # Frame saved logs
    assert any("Frame saved:" in m for m in msgs)
    assert any("FITS frame saved:" in m for m in msgs)
    # Timing telemetry present
    assert any(
        "timings_ms" in m and "capture=" in m and "save=" in m and "solve=" in m for m in msgs
    )
