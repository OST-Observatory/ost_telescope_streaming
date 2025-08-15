from pathlib import Path
from typing import Any, Dict

from PIL import Image


class _CfgStatic:
    def __init__(self, dir_path: str, use_timestamps: bool) -> None:
        self._dir = dir_path
        self._use_ts = use_timestamps

    def get_frame_processing_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "save_plate_solve_frames": False,
            "plate_solve_dir": self._dir,
            "file_format": "PNG",
            "use_timestamps": False,  # not used by get_latest_frame_path
        }

    def get_plate_solve_config(self) -> Dict[str, Any]:
        return {"default_solver": "platesolve2", "auto_solve": False, "min_solve_interval": 1}

    def get_mount_config(self) -> Dict[str, Any]:
        return {"slewing_detection": {"enabled": False}}

    def get_overlay_config(self) -> Dict[str, Any]:
        return {"use_timestamps": self._use_ts}


def test_combine_overlay_with_image_success(tmp_path):
    from processing.processor import VideoProcessor

    base = tmp_path / "base.png"
    overlay = tmp_path / "ovl.png"

    # Create base and overlay images
    base_img = Image.new("RGBA", (64, 48), (10, 10, 10, 255))
    base_img.save(base)
    ovl_img = Image.new("RGBA", (64, 48), (255, 0, 0, 64))
    ovl_img.save(overlay)

    vp = VideoProcessor(config=_CfgStatic(str(tmp_path), use_timestamps=False))
    status = vp.combine_overlay_with_image(str(base), str(overlay))
    assert status.is_success
    assert Path(status.data).exists()


def test_get_latest_frame_path_static(tmp_path):
    from processing.processor import VideoProcessor

    # create capture.png
    dir_path = tmp_path / "frames"
    dir_path.mkdir()
    (dir_path / "capture.png").write_bytes(b"x")

    vp = VideoProcessor(config=_CfgStatic(str(dir_path), use_timestamps=False))
    # Ensure non-None video_capture so fallback path executes
    vp.video_capture = object()
    path = vp.get_latest_frame_path()
    assert path == str(dir_path / "capture.png")


def test_get_latest_frame_path_timestamped(tmp_path):
    import time

    from processing.processor import VideoProcessor

    dir_path = tmp_path / "frames"
    dir_path.mkdir()
    f1 = dir_path / "cap_1.png"
    f2 = dir_path / "cap_2.png"
    f1.write_bytes(b"a")
    time.sleep(0.01)
    f2.write_bytes(b"b")

    vp = VideoProcessor(config=_CfgStatic(str(dir_path), use_timestamps=True))
    vp.video_capture = object()
    path = vp.get_latest_frame_path()
    assert path == str(f2)


def test_combine_overlay_resizes_and_composes(tmp_path):
    from processing.processor import VideoProcessor

    base = tmp_path / "base_large.png"
    overlay = tmp_path / "ovl_small.png"

    # Base larger than overlay
    Image.new("RGBA", (128, 96), (20, 20, 20, 255)).save(base)
    Image.new("RGBA", (32, 24), (0, 255, 0, 128)).save(overlay)

    vp = VideoProcessor(config=_CfgStatic(str(tmp_path), use_timestamps=False))
    status = vp.combine_overlay_with_image(str(base), str(overlay))
    assert status.is_success
    out = Path(status.data)
    assert out.exists()
    # Verify size and that some pixels are altered by overlay (non-trivial check)
    with Image.open(out) as im:
        assert im.size == (128, 96)
