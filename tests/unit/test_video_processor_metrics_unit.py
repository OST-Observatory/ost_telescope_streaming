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
        return object()


def test_metrics_and_counters(tmp_path, monkeypatch, caplog):
    from processing.processor import VideoProcessor

    # Avoid actual IO when saving
    def _fake_save(self, frame, path, metadata=None):  # noqa: ARG002
        class _S:
            is_success = True
            message = "ok"

        Path(path).write_bytes(b"x")
        return _S()

    monkeypatch.setattr("services.frame_writer.FrameWriter.save", _fake_save, raising=True)

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    vp.video_capture = _FakeCapture(tmp_path / "cap.png")

    # Run twice to see counter growth
    caplog.clear()
    vp._capture_and_solve()
    vp._capture_and_solve()

    assert vp.capture_count >= 2
    # No solver => no solves
    assert vp.solve_count == 0

    # Check timing log present
    found = False
    for rec in caplog.records:
        if "timings_ms" in rec.getMessage() and "capture=" in rec.getMessage():
            found = True
            break
    assert found


def test_solver_prefers_fits_when_available(tmp_path, monkeypatch):
    from processing.processor import VideoProcessor

    # Create both PNG and FITS candidates
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    png = frames_dir / "capture_0001.PNG"
    fits = frames_dir / "capture_0001.fits"
    png.write_bytes(b"p")
    fits.write_bytes(b"f")

    class _Cfg2(_Cfg):
        def get_frame_processing_config(self) -> Dict[str, Any]:
            cfg = super().get_frame_processing_config()
            cfg.update({"plate_solve_dir": str(frames_dir), "save_plate_solve_frames": True})
            return cfg

    # Fake solver with spy to capture given path
    called = {"path": None}

    class _FakeSolver:
        def is_available(self):
            return True

        def get_name(self):
            return "fake"

        def solve(self, path: str):
            called["path"] = path

            class _S:
                is_success = False
                message = "failed"
                details: Dict[str, Any] = {}

            return _S()

    def _fake_create(_solver_type, config=None, logger=None):  # noqa: ARG002
        return _FakeSolver()

    monkeypatch.setattr(
        "platesolve.solver.PlateSolverFactory.create_solver", _fake_create, raising=True
    )

    vp = VideoProcessor(config=_Cfg2(str(tmp_path)))
    vp.auto_solve = True
    vp.plate_solver = _FakeSolver()
    # Simulate that saving produced files and call _maybe_plate_solve directly
    vp._maybe_plate_solve(fits_filename=fits, frame_filename=png)
    assert called["path"] == str(fits)
