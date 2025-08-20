from __future__ import annotations

from typing import Any, Dict


def test_get_available_solvers_false_by_default():
    from platesolve.solver import PlateSolverFactory

    class _Cfg:
        def get_plate_solve_config(self) -> Dict[str, Any]:
            return {"platesolve2": {"executable_path": ""}, "astrometry": {"api_key": ""}}

    avail = PlateSolverFactory.get_available_solvers(config=_Cfg())
    # Accept presence of additional solver variants; require at least the standard ones
    assert {"platesolve2", "astrometry"}.issubset(set(avail.keys()))
    assert avail["platesolve2"] is False
    assert avail["astrometry"] is False
