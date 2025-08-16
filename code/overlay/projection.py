from __future__ import annotations

from typing import Tuple

import numpy as np


def skycoord_to_pixel_with_rotation(
    obj_ra_deg: float,
    obj_dec_deg: float,
    center_ra_deg: float,
    center_dec_deg: float,
    size_px: Tuple[int, int],
    fov_width_deg: float,
    fov_height_deg: float,
    position_angle_deg: float = 0.0,
    flip_x: bool = False,
    flip_y: bool = False,
    ra_increases_left: bool = True,
    **_legacy_kwargs,
) -> Tuple[int, int]:
    """Project sky coordinates to pixel coordinates with rotation and flip.

    Args:
        obj_ra_deg: Object RA in degrees
        obj_dec_deg: Object Dec in degrees
        center_ra_deg: Image center RA in degrees
        center_dec_deg: Image center Dec in degrees
        size_px: (width, height) in pixels
        fov_width_deg: Field of view width in degrees
        fov_height_deg: Field of view height in degrees
        position_angle_deg: Rotation angle (degrees)
        is_flipped: Mirror in X
        ra_increases_left: Astronomical convention toggle
    Returns:
        (x, y) pixel coordinates
    """
    # Angular separations (arcmin), scale RA by cos(dec)
    delta_ra_basic_arcmin = (obj_ra_deg - center_ra_deg) * 60.0 * np.cos(np.deg2rad(center_dec_deg))
    delta_dec_arcmin = (obj_dec_deg - center_dec_deg) * 60.0

    delta_ra_arcmin = -delta_ra_basic_arcmin if ra_increases_left else delta_ra_basic_arcmin

    pa_rad = np.deg2rad(position_angle_deg)
    cos_pa = np.cos(pa_rad)
    sin_pa = np.sin(pa_rad)

    # Rotate
    delta_ra_rot = delta_ra_arcmin * cos_pa + delta_dec_arcmin * sin_pa
    delta_dec_rot = -delta_ra_arcmin * sin_pa + delta_dec_arcmin * cos_pa

    # Pixel scales (arcmin per pixel)
    scale_x = (fov_width_deg * 60.0) / float(size_px[0])
    scale_y = (fov_height_deg * 60.0) / float(size_px[1])

    x = size_px[0] / 2.0 + (delta_ra_rot / scale_x)
    y = size_px[1] / 2.0 - (delta_dec_rot / scale_y)

    # Backward compatibility: allow legacy 'is_flipped' kwarg
    if not flip_x and "is_flipped" in _legacy_kwargs:
        try:
            flip_x = bool(_legacy_kwargs.get("is_flipped", False))
        except Exception:
            flip_x = False

    if flip_x:
        x = size_px[0] - x
    if flip_y:
        y = size_px[1] - y

    # Use rounding to make flip symmetry exact in tests
    return int(round(x)), int(round(y))
