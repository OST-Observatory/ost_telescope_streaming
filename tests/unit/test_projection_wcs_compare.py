import math
import os

import numpy as np
import pytest


@pytest.mark.skipif(
    os.environ.get("TEST_PROJECTION_FITS") is None,
    reason="Set TEST_PROJECTION_FITS to a FITS file path to run this test",
)
def test_projection_math_matches_wcs_from_fits():
    try:
        import astropy.io.fits as fits
        from astropy.wcs import WCS
        from astropy.wcs.utils import proj_plane_pixel_scales
    except Exception as e:  # pragma: no cover - optional dependency in CI
        pytest.skip(f"Astropy not available: {e}")

    from overlay.projection import (
        skycoord_to_pixel_wcs,
        skycoord_to_pixel_with_rotation,
    )

    fits_path = os.environ["TEST_PROJECTION_FITS"]
    assert os.path.exists(fits_path), f"FITS file not found: {fits_path}"

    # Read header and WCS
    with fits.open(fits_path) as hdul:
        hdu = hdul[0]
        header = hdu.header
        height, width = (
            hdu.data.shape
            if hdu.data is not None
            else (
                int(header.get("NAXIS2", 0)),
                int(header.get("NAXIS1", 0)),
            )
        )

    w = WCS(header)
    if not w.has_celestial:  # pragma: no cover
        pytest.skip("FITS lacks celestial WCS; cannot run comparison")

    # Center from WCS
    ra0 = float(w.wcs.crval[0])
    dec0 = float(w.wcs.crval[1])

    # Pixel scales (deg/pix) -> arcsec/pix
    scales_deg = proj_plane_pixel_scales(w)
    scale_x_deg = float(scales_deg[0])
    scale_y_deg = float(scales_deg[1])
    # Use average scale for a scalar pixel scale
    pixel_scale_arcsec = (scale_x_deg + scale_y_deg) * 0.5 * 3600.0

    # Approximate PA from the WCS CD/PC matrix
    cd = None
    if getattr(w.wcs, "cd", None) is not None and np.array(w.wcs.cd).shape == (2, 2):
        cd = np.array(w.wcs.cd, dtype=float)
    else:
        pc = np.array(getattr(w.wcs, "pc", np.eye(2)), dtype=float)
        cdelt = np.array(getattr(w.wcs, "cdelt", [scale_x_deg, scale_y_deg]), dtype=float)
        cd = pc @ np.diag(cdelt)

    # Derive a PA that is consistent for both methods (not necessarily the true sky PA)
    # This keeps the comparison focused on internal consistency.
    # Angle of pixel X axis in world basis; account for Y-down display later (handled in projection)
    pa_rad = math.atan2(cd[0, 1], cd[0, 0])
    position_angle_deg = math.degrees(pa_rad)

    # FOV from scale and image size
    fov_width_deg = scale_x_deg * float(width)
    fov_height_deg = scale_y_deg * float(height)

    # RA handedness heuristic: if increasing RA maps to decreasing X in header WCS
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    c0 = SkyCoord(ra0 * u.deg, dec0 * u.deg, frame="icrs")
    dra = 1.0 / 3600.0  # 1 arcsec in degrees
    c_ra = SkyCoord((ra0 + dra) * u.deg, dec0 * u.deg, frame="icrs")
    x0, y0 = w.world_to_pixel(c0)
    x_ra, y_ra = w.world_to_pixel(c_ra)
    ra_increases_left = (x_ra - x0) < 0.0

    # Sample a few offsets around center (small offsets within FOV)
    tests = [
        (ra0, dec0),
        (ra0 + 0.1 * fov_width_deg, dec0),
        (ra0 - 0.1 * fov_width_deg, dec0),
        (ra0, dec0 + 0.1 * fov_height_deg),
        (ra0, dec0 - 0.1 * fov_height_deg),
        (ra0 + 0.05 * fov_width_deg, dec0 + 0.05 * fov_height_deg),
    ]

    tol_px = 2.0  # allow a couple of pixels due to approximations

    for ra_deg, dec_deg in tests:
        x_math, y_math = skycoord_to_pixel_with_rotation(
            ra_deg,
            dec_deg,
            ra0,
            dec0,
            (width, height),
            fov_width_deg,
            fov_height_deg,
            position_angle_deg=position_angle_deg,
            flip_x=False,
            flip_y=False,
            ra_increases_left=ra_increases_left,
        )

        x_wcs, y_wcs = skycoord_to_pixel_wcs(
            ra_deg,
            dec_deg,
            ra0,
            dec0,
            (width, height),
            pixel_scale_arcsec=pixel_scale_arcsec,
            position_angle_deg=position_angle_deg,
            flip_x=False,
            flip_y=False,
            ra_increases_left=ra_increases_left,
        )

        dx = abs(x_math - x_wcs)
        dy = abs(y_math - y_wcs)
        assert dx <= tol_px and dy <= tol_px, (
            "Pixel mismatch exceeds tolerance: "
            f"dX={dx:.2f}, dY={dy:.2f} at RA={ra_deg:.6f}, Dec={dec_deg:.6f} "
            f"(math=({x_math},{y_math}), wcs=({x_wcs},{y_wcs}))"
        )
