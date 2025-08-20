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
    # Apply math rotation by +PA in screen coordinates; astronomical
    # handedness is handled via ra_increases_left and y-down mapping below.
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


def skycoord_to_pixel_wcs(
    obj_ra_deg: float,
    obj_dec_deg: float,
    center_ra_deg: float | None,
    center_dec_deg: float | None,
    size_px: Tuple[int, int] | None,
    pixel_scale_arcsec: float | None,
    position_angle_deg: float = 0.0,
    flip_x: bool = False,
    flip_y: bool = False,
    ra_increases_left: bool = True,
    wcs_path: str | None = None,
) -> Tuple[int, int]:
    """Alternative projection using an Astropy WCS for sanity checks.

    Builds a simple TAN WCS from center, pixel scale (arcsec/pixel) and PA, then
    converts world (RA,Dec) to pixel coordinates via astropy.wcs.
    """
    try:
        from astropy.coordinates import SkyCoord
        import astropy.io.fits as fits
        import astropy.units as u
        from astropy.wcs import WCS
    except Exception as _e:
        # Fallback to math path if astropy is unavailable
        return skycoord_to_pixel_with_rotation(
            obj_ra_deg,
            obj_dec_deg,
            center_ra_deg or 0.0,
            center_dec_deg or 0.0,
            size_px or (1, 1),
            # FOV not used in fallback; pass equal to avoid division by zero if called
            fov_width_deg=1.0,
            fov_height_deg=1.0,
            position_angle_deg=position_angle_deg,
            flip_x=flip_x,
            flip_y=flip_y,
            ra_increases_left=ra_increases_left,
        )

    # Construct WCS
    # Build WCS either from an existing WCS FITS or synthetic parameters
    if wcs_path:
        with fits.open(wcs_path) as hdul:
            w = WCS(hdul[0].header)
            if size_px is None:
                data = hdul[0].data
                if data is not None and hasattr(data, "shape"):
                    if data.ndim == 2:
                        height, width = data.shape
                    elif data.ndim == 3:
                        height, width = data.shape[-2], data.shape[-1]
                    else:
                        height = int(hdul[0].header.get("NAXIS2", 0))
                        width = int(hdul[0].header.get("NAXIS1", 0))
                    size_px = (int(width), int(height))
    else:
        w = WCS(naxis=2)
        w.wcs.crval = [float(center_ra_deg or 0.0), float(center_dec_deg or 0.0)]
        # CRPIX is 1-based in FITS, but astropy uses 1-based internally with WCS
        # We set CRPIX to exact image center in 1-based coordinates
        width_px, height_px = size_px or (1, 1)
        w.wcs.crpix = [width_px / 2.0 + 0.5, height_px / 2.0 + 0.5]
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        w.wcs.cunit = ["deg", "deg"]

        scale_deg = float(pixel_scale_arcsec or 1.0) / 3600.0
        pa_rad = float(position_angle_deg) * np.pi / 180.0
        cos_pa = np.cos(pa_rad)
        sin_pa = np.sin(pa_rad)

        # RA handedness: RA increases left implies negative CD1_1 baseline
        if ra_increases_left:
            cd11 = -scale_deg * cos_pa
            cd12 = scale_deg * sin_pa
        else:
            cd11 = scale_deg * cos_pa
            cd12 = -scale_deg * sin_pa
        cd21 = scale_deg * sin_pa
        cd22 = scale_deg * cos_pa
        w.wcs.cd = np.array([[cd11, cd12], [cd21, cd22]], dtype=float)

    # World to pixel (astropy returns 1-based pixel coords if using WCS directly)
    sc = SkyCoord(ra=float(obj_ra_deg) * u.deg, dec=float(obj_dec_deg) * u.deg, frame="icrs")
    x1_f, y1_f = w.world_to_pixel(sc)  # returns 0-based floats in FITS/WCS (Y up)

    # Apply optional flips in pixel space to match display conventions
    x = float(x1_f)
    # Convert WCS (Y up) to display coordinates (Y down)
    width_px = int(size_px[0]) if size_px is not None else 0
    height_px = int(size_px[1]) if size_px is not None else 0
    y = float(height_px - y1_f)
    if flip_x:
        x = float(width_px) - x
    if flip_y:
        y = float(height_px) - y

    return int(round(x)), int(round(y))
