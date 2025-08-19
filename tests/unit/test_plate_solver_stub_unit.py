from __future__ import annotations

from typing import Any, Dict


class _Cfg:
    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {
            "default_solver": "platesolve2",
            "platesolve2": {"executable_path": "", "timeout": 1},  # unavailable by default
        }


def test_factory_unknown_solver_logs(monkeypatch, caplog):
    from platesolve.solver import PlateSolverFactory

    caplog.clear()
    solver = PlateSolverFactory.create_solver("doesnotexist", config=_Cfg(), logger=None)
    assert solver is None


def test_factory_returns_none_when_unavailable(monkeypatch):
    from platesolve.solver import PlateSolverFactory

    cfg = _Cfg()
    solver = PlateSolverFactory.create_solver("platesolve2", config=cfg)
    # executable_path is empty -> unavailable
    assert solver is not None
    assert solver.is_available() is False


def test_solver_error_when_not_available(tmp_path):
    from platesolve.solver import PlateSolverFactory

    cfg = _Cfg()
    solver = PlateSolverFactory.create_solver("platesolve2", config=cfg)
    # Create a dummy file to pass exists() check in our own logic later if needed
    img = tmp_path / "x.fits"
    img.write_bytes(b"f")
    # solve should return error_status when unavailable
    status = solver.solve(str(img))
    assert hasattr(status, "is_success") and status.is_success is False
    assert "not available" in status.message.lower()


def test_fake_success_path_converted_by_processor(tmp_path, monkeypatch):
    # Provide a fake solver that returns a success status; ensure VideoProcessor converts it
    from processing.processor import VideoProcessor

    class _Cfg2:
        def get_frame_processing_config(self) -> Dict[str, Any]:
            return {
                "enabled": False,
                "save_plate_solve_frames": False,
                "plate_solve_dir": str(tmp_path),
                "file_format": "PNG",
                "use_timestamps": False,
            }

        def get_plate_solve_config(self) -> Dict[str, Any]:
            return {"default_solver": "platesolve2", "min_solve_interval": 0, "auto_solve": True}

        def get_mount_config(self) -> Dict[str, Any]:
            return {"slewing_detection": {"enabled": False}}

    class _S:
        is_success = True
        data = {
            "ra_center": 10.0,
            "dec_center": 20.0,
            "fov_width": 1.0,
            "fov_height": 0.75,
            "position_angle": 0.0,
            "image_size": (100, 80),
            "flipped": 0,
        }
        details: Dict[str, Any] = {"solving_time": 0.1, "method": "fake"}

    class _FakeSolver:
        def is_available(self) -> bool:
            return True

        def get_name(self) -> str:
            return "fake"

        def solve(self, path: str):  # noqa: ARG002
            return _S()

    vp = VideoProcessor(config=_Cfg2())
    vp.plate_solver = _FakeSolver()
    result = vp._solve_frame(str(tmp_path / "anything.png"))
    assert result is not None
    assert result.ra_center == 10.0 and result.dec_center == 20.0
