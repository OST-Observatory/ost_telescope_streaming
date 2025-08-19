from __future__ import annotations

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
            "use_timestamps": False,
        }

    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {"default_solver": "platesolve2", "auto_solve": True, "min_solve_interval": 0}

    def get_mount_config(self) -> Dict[str, Any]:
        return {"slewing_detection": {"enabled": False}}


class _FakeSolverFailNoStars:
    def is_available(self) -> bool:
        return True

    def get_name(self) -> str:
        return "fake"

    def solve(self, path: str):  # noqa: ARG002
        class _S:
            is_success = False
            message = "Plate-solving failed: no_stars"
            details = {"solving_time": 0.05, "reason": "no_stars"}

        return _S()


def test_solve_failure_logs_and_counts(tmp_path, caplog):
    from processing.processor import VideoProcessor

    # Prepare candidate file
    img = tmp_path / "capture.PNG"
    img.write_bytes(b"x")

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.plate_solver = _FakeSolverFailNoStars()

    caplog.clear()
    vp._maybe_plate_solve(fits_filename=None, frame_filename=img)
    assert vp.solve_count == 1
    # Expect a warning log about failure
    msgs = "\n".join(r.getMessage() for r in caplog.records)
    assert "Plate-solving failed" in msgs


class _FakeSolverTimeout:
    def is_available(self) -> bool:
        return True

    def get_name(self) -> str:
        return "fake"

    def solve(self, path: str):  # noqa: ARG002
        class _S:
            is_success = False
            message = "timeout"
            details = {"solving_time": 5.0, "reason": "timeout"}

        return _S()


def test_solve_timeout_path(tmp_path, caplog):
    from processing.processor import VideoProcessor

    img = tmp_path / "capture.PNG"
    img.write_bytes(b"x")

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.plate_solver = _FakeSolverTimeout()

    caplog.clear()
    vp._maybe_plate_solve(fits_filename=None, frame_filename=img)
    # Count increased; failure path handled
    assert vp.solve_count == 1
    msgs = "\n".join(r.getMessage() for r in caplog.records)
    assert "failed" in msgs or "timeout" in msgs
