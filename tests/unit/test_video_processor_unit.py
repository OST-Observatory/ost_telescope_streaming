import types
from typing import Any, Dict


class _StubConfig:
    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "save_plate_solve_frames": False,
            "plate_solve_dir": "plate_solve_frames",
            "use_timestamps": False,
            "use_capture_count": True,
            "file_format": "PNG",
        }

    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 1}

    def get_mount_config(self) -> Dict[str, Any]:
        return {"slewing_detection": {"enabled": False}}


def test_video_processor_initialize_without_hardware(monkeypatch):
    from processing.processor import VideoProcessor

    # Fake VideoCapture to avoid real hardware
    class _VC:
        camera = object()
        camera_type = "opencv"

        def __init__(self, *args, **kwargs) -> None:
            pass

        def start_capture(self):
            class _S:
                is_success = True

            return _S()

        def stop_capture(self):
            return types.SimpleNamespace(is_success=True)

        def disconnect(self):
            return types.SimpleNamespace(is_success=True)

        def get_current_frame(self):
            return types.SimpleNamespace(
                is_success=True, data=b"frame", details={"dimensions": (2, 2)}
            )

    monkeypatch.setattr("processing.processor.VideoCapture", _VC)

    vp = VideoProcessor(config=_StubConfig())
    assert vp.initialize() is True
    assert vp.video_capture is not None
    # start then stop
    start_status = vp.start()
    assert start_status.is_success
    stop_status = vp.stop()
    assert stop_status.is_success
