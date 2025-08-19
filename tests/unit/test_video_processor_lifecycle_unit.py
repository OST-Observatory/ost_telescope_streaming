from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class _CfgBase:
    def __init__(self, dir_path: str, wait_for_completion: bool) -> None:
        self._dir = dir_path
        self._wait = wait_for_completion

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
        return {
            "slewing_detection": {
                "enabled": True,
                "check_before_capture": True,
                "wait_for_completion": self._wait,
                "wait_timeout": 0.1,
                "check_interval": 0.01,
            }
        }


class _FakeStatus:
    def __init__(
        self, ok: bool, data: Any = None, message: str = "ok", details: Dict[str, Any] | None = None
    ) -> None:
        self.is_success = ok
        self.data = data
        self.message = message
        self.details = details or {}


class _FakeMount:
    def __init__(self, slewing: bool, wait_success: bool) -> None:
        self._slewing = slewing
        self._wait_success = wait_success

    def is_slewing(self):
        return _FakeStatus(True, data=self._slewing)

    def wait_for_slewing_complete(self, timeout: float, check_interval: float):  # noqa: ARG002
        return _FakeStatus(True, data=self._wait_success)

    # Warmup flow hooks (used by OverlayRunner in shutdown)
    def start_warmup(self):
        return _FakeStatus(True)

    def wait_for_warmup_completion(self, timeout: float):  # noqa: ARG002
        return _FakeStatus(True)


class _FakeCapture:
    camera_type = "opencv"
    camera = object()

    def __init__(self, path: Path):
        self.path = path

    def get_current_frame(self):
        return _FakeStatus(True, data=str(self.path), details={"dimensions": (10, 10)})

    def capture_single_frame(self):  # for completeness
        return _FakeStatus(True, data=str(self.path), details={"dimensions": (10, 10)})

    def stop_capture(self):
        return None

    def disconnect(self):
        return None


def _stub_save(self, frame, path, metadata=None):  # noqa: ARG002
    class _S:
        is_success = True
        message = "ok"

    Path(path).write_bytes(b"x")
    return _S()


def test_slewing_skip_mode(tmp_path, monkeypatch, caplog):
    from processing.processor import VideoProcessor

    monkeypatch.setattr("services.frame_writer.FrameWriter.save", _stub_save, raising=True)

    vp = VideoProcessor(config=_CfgBase(str(tmp_path), wait_for_completion=False))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")
    vp.mount = _FakeMount(slewing=True, wait_success=False)

    caplog.clear()
    vp._capture_and_solve()
    # Should skip capture due to slewing
    assert vp.capture_count == 0


def test_slewing_wait_mode_then_capture(tmp_path, monkeypatch):
    from processing.processor import VideoProcessor

    monkeypatch.setattr("services.frame_writer.FrameWriter.save", _stub_save, raising=True)

    vp = VideoProcessor(config=_CfgBase(str(tmp_path), wait_for_completion=True))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")
    vp.mount = _FakeMount(slewing=True, wait_success=True)

    vp._capture_and_solve()
    # After waiting completes, capture proceeds
    assert vp.capture_count == 1
