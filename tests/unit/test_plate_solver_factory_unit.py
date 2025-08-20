def test_plate_solver_factory_creates_known_types():
    from platesolve.solver import AstrometryNetSolver, PlateSolve2, PlateSolverFactory

    s1 = PlateSolverFactory.create_solver("platesolve2")
    assert isinstance(s1, PlateSolve2)
    s2 = PlateSolverFactory.create_solver("astrometry")
    assert isinstance(s2, AstrometryNetSolver)


def test_plate_solver_factory_unknown_returns_none(caplog):
    from platesolve.solver import PlateSolverFactory

    with caplog.at_level("ERROR"):
        s = PlateSolverFactory.create_solver("unknown_solver_type")
    assert s is None
    # Optionally assert log contains unknown
    assert any("Unknown solver type" in rec.getMessage() for rec in caplog.records)
