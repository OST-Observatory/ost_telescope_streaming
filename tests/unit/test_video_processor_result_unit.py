from typing import Any


class _S:
    def __init__(
        self,
        ok: bool,
        data: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        msg: str = "",
    ) -> None:
        self.is_success = ok
        self.data = data or {}
        self.details = details or {}
        self.message = msg


def _vp():
    from processing.processor import VideoProcessor

    class _Cfg:
        def get_frame_processing_config(self):
            return {"enabled": False, "plate_solve_dir": "."}

        def get_plate_solve_config(self):
            return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 1}

        def get_mount_config(self):
            return {"slewing_detection": {"enabled": False}}

    return VideoProcessor(config=_Cfg())


def test_status_to_result_basic():
    vp = _vp()
    st = _S(
        True,
        data={"ra_center": 10.5, "dec_center": -20.25, "fov_width": 1.2, "fov_height": 0.8},
        details={"solving_time": 2.5, "method": "automated"},
    )
    res = vp._status_to_result(st)
    assert res is not None
    assert res.ra_center == 10.5 and res.dec_center == -20.25
    assert res.fov_width == 1.2 and res.fov_height == 0.8
    assert res.solving_time == 2.5 and res.method == "automated"


def test_status_to_result_flip_parsing():
    vp = _vp()
    for raw in (1, 1.0, "true", "Flipped", True):
        st = _S(True, data={"flipped": raw})
        res = vp._status_to_result(st)
        assert res is not None and res.is_flipped is True
    for raw in (0, 0.0, "false", "no", False, None):
        st = _S(True, data={"flipped": raw})
        res = vp._status_to_result(st)
        assert res is not None and res.is_flipped is False


def test_status_to_result_handles_bad_types():
    vp = _vp()
    # bad strings convert to defaults
    st = _S(True, data={"ra_center": "bad", "fov_width": "x"}, details={"solving_time": "y"})
    res = vp._status_to_result(st)
    assert res is not None
    assert res.ra_center == 0.0
    assert res.fov_width == 1.0
    assert res.solving_time == 0.0


def test_status_to_result_image_size_and_pa_defaults():
    vp = _vp()
    st = _S(True, data={"image_size": (320, 240)}, details={})
    res = vp._status_to_result(st)
    assert res is not None
    assert res.image_size == (320, 240)
    assert res.position_angle is None
