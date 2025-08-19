from __future__ import annotations


def test_platesolve_result_str_contains_fields():
    from platesolve.solver import PlateSolveResult

    r = PlateSolveResult(
        ra_center=10.1234,
        dec_center=-20.5678,
        fov_width=1.234,
        fov_height=0.987,
        solving_time=2.3,
        method="automated",
        confidence=0.85,
        position_angle=45.0,
        image_size=(100, 80),
        is_flipped=True,
    )
    s = str(r)
    assert "RA=10.1234°" in s and "Dec=-20.5678°" in s
    assert "FOV=1.234°x0.987°" in s
    assert "time=2.3s" in s and "flipped=Yes" in s
    assert ", confidence=0.85" in s
