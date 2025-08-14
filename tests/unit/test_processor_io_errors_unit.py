from pathlib import Path
from typing import Any, Dict

from PIL import Image


class _Cfg:
    def __init__(self, d: str) -> None:
        self._d = d

    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "save_plate_solve_frames": False,
            "plate_solve_dir": self._d,
            "file_format": "PNG",
        }

    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 1}

    def get_mount_config(self) -> Dict[str, Any]:
        return {"slewing_detection": {"enabled": False}}

    def get_overlay_config(self) -> Dict[str, Any]:
        return {"use_timestamps": False}


def test_combine_overlay_missing_files(tmp_path):
    from processing.processor import VideoProcessor

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    st = vp.combine_overlay_with_image(
        str(tmp_path / "missing_base.png"), str(tmp_path / "missing_ovl.png")
    )
    assert st.is_error


def test_combine_overlay_resizes_overlay(tmp_path):
    from processing.processor import VideoProcessor

    base = tmp_path / "base.png"
    overlay = tmp_path / "ovl.png"
    out = tmp_path / "out.png"

    Image.new("RGBA", (80, 60), (20, 20, 20, 255)).save(base)
    # Different size overlay to trigger resize
    Image.new("RGBA", (40, 30), (255, 0, 0, 64)).save(overlay)

    vp = VideoProcessor(config=_Cfg(str(tmp_path)))
    st = vp.combine_overlay_with_image(str(base), str(overlay), str(out))
    assert st.is_success
    assert Path(out).exists()
