from pathlib import Path

import numpy as np
from processing.stacker import FrameStacker
import pytest


def _make_stars(shape=(128, 128), points=((30, 40), (80, 90), (50, 100))):
    img = np.zeros(shape, dtype=np.uint8)
    for y, x in points:
        img[y, x] = 255
    return img


@pytest.mark.integration
@pytest.mark.parametrize(
    "angle_deg,scale,shift_xy",
    [
        (12.0, 1.0, (5, -7)),
        (30.0, 1.0, (8, 3)),
        (45.0, 1.03, (0, 0)),
        (0.0, 0.97, (10, -4)),
    ],
)
def test_alignment_handles_rotation_scale_shift(tmp_path: Path, angle_deg, scale, shift_xy):
    base = _make_stars()
    try:
        import cv2
    except Exception:
        pytest.skip("OpenCV required for synthetic transform")

    center = (base.shape[1] // 2, base.shape[0] // 2)
    M = cv2.getRotationMatrix2D(center, angle_deg, scale)
    warped = cv2.warpAffine(base, M, (base.shape[1], base.shape[0]), flags=cv2.INTER_NEAREST)
    if shift_xy != (0, 0):
        dy, dx = shift_xy
        warped = np.roll(warped, shift=dy, axis=0)
        warped = np.roll(warped, shift=dx, axis=1)

    s = FrameStacker(
        output_dir=tmp_path,
        method="median",
        sigma_clip_enabled=True,
        sigma=3.0,
        align="astroalign",
    )
    s.add_frame(base)
    s.add_frame(warped)
    snap = s.get_snapshot()
    assert snap is not None
    img = snap.image_uint8
    assert img is not None
    # Expect bright peaks remain after alignment/median
    max_val = int(np.max(img))
    assert max_val >= 200
    # Expect at least two star pixels above 200
    assert int(np.sum(img >= 200)) >= 2
