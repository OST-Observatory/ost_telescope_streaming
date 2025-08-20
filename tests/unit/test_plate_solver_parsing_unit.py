from __future__ import annotations

from typing import Any, Dict


def test_processor_status_to_result_parses_partial_fields():
    from processing.processor import VideoProcessor

    class _Cfg:
        def get_frame_processing_config(self) -> Dict[str, Any]:
            return {"enabled": False, "plate_solve_dir": "."}

        def get_plate_solve_config(self) -> Dict[str, Any]:
            return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 1}

        def get_mount_config(self) -> Dict[str, Any]:
            return {"slewing_detection": {"enabled": False}}

    vp = VideoProcessor(config=_Cfg())

    class _S:
        is_success = True
        data = {"ra_center": 0, "dec_center": 0, "fov_width": 2.0}
        details = {"solving_time": 1.2, "method": "test"}

    res = vp._status_to_result(_S())
    assert res is not None
    assert res.fov_width == 2.0 and res.fov_height == 1.0  # default for missing height
    assert res.method == "test"
