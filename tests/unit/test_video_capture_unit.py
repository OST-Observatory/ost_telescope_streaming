import types
from typing import Any, Dict

import pytest


class _StubConfig:
    def __init__(self, camera_type: str = "opencv") -> None:
        self._camera_type = camera_type

    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "output_dir": "captured_frames",
            "cache_dir": "cache",
        }

    def get_camera_config(self) -> Dict[str, Any]:
        return {
            "camera_type": self._camera_type,
            "opencv": {
                "camera_index": 0,
                "fps": 30,
                "resolution": [640, 480],
                "exposure_time": 0.01,
            },
            "ascom": {"gain": 100.0, "offset": 50.0, "readout_mode": 0, "binning": 1},
            "cooling": {"enable_cooling": False},
        }

    def get_telescope_config(self) -> Dict[str, Any]:
        return {"focal_length": 1000}


class _FakeCapture:
    def __init__(self) -> None:
        self.opened = True
        self.props: Dict[int, Any] = {}

    def isOpened(self) -> bool:  # noqa: N802 (opencv-style API)
        return True

    def set(self, prop: int, value: Any) -> bool:
        self.props[prop] = value
        return True

    def read(self):
        return False, None

    def release(self) -> None:
        self.opened = False


def _install_fake_cv2(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.SimpleNamespace()
    fake.CAP_PROP_FRAME_WIDTH = 3
    fake.CAP_PROP_FRAME_HEIGHT = 4
    fake.CAP_PROP_FPS = 5
    fake.CAP_PROP_AUTO_EXPOSURE = 6
    fake.CAP_PROP_EXPOSURE = 7
    fake.CAP_PROP_GAIN = 8
    fake.VideoCapture = lambda idx: _FakeCapture()
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake)


def test_initialize_camera_opencv_success(monkeypatch: pytest.MonkeyPatch):
    _install_fake_cv2(monkeypatch)
    from capture.controller import VideoCapture

    vc = VideoCapture(config=_StubConfig("opencv"))
    status = vc._initialize_camera()
    assert getattr(status, "is_success", False), (
        status.message if hasattr(status, "message") else status
    )
    assert vc.cap is not None
    assert vc.camera is not None


def test_start_and_stop_capture_thread(monkeypatch: pytest.MonkeyPatch):
    _install_fake_cv2(monkeypatch)
    from capture.controller import VideoCapture

    vc = VideoCapture(config=_StubConfig("opencv"))
    start_status = vc.start_capture()
    assert start_status.is_success
    assert vc.is_capturing is True
    stop_status = vc.stop_capture()
    assert stop_status.is_success
    assert vc.is_capturing is False
