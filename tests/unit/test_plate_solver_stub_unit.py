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
