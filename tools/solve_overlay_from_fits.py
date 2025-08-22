#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple

# Ensure local code package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from config_manager import ConfigManager  # noqa: E402
from overlay.generator import OverlayGenerator  # noqa: E402
from platesolve.solver import PlateSolverFactory  # noqa: E402
from processing.processor import VideoProcessor  # noqa: E402


def _setup_logging(level: str) -> logging.Logger:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric, format="%(asctime)s - %(levelname)s - %(message)s")
    return logging.getLogger("solve_overlay_cli")


def _parse_ra_dec_from_header(header: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None

    def _parse_ra(val: str) -> Optional[float]:
        try:
            if ":" in val:
                h, m, s = [float(x) for x in val.split(":")]
                return h * 15.0 + m * 0.25 + s * (0.0041667)
            return float(val)
        except Exception:
            return None

    def _parse_dec(val: str) -> Optional[float]:
        try:
            if ":" in val:
                dd, mm, ss = val.split(":")
                sign = -1 if str(dd).strip().startswith("-") else 1
                return sign * (abs(float(dd)) + float(mm) / 60.0 + float(ss) / 3600.0)
            return float(val)
        except Exception:
            return None

    for key in ("RA", "CRVAL1", "OBJCTRA"):
        if key in header and ra_deg is None:
            ra_deg = _parse_ra(str(header[key]))
    for key in ("DEC", "CRVAL2", "OBJCTDEC"):
        if key in header and dec_deg is None:
            dec_deg = _parse_dec(str(header[key]))
    return ra_deg, dec_deg


def extract_fits_parameters(fits_path: str, logger: logging.Logger) -> Dict[str, Any]:
    try:
        import astropy.io.fits as fits
    except Exception as e:  # pragma: no cover - dependency optional
        logger.error(f"astropy not available: {e}")
        return {}

    try:
        with fits.open(fits_path) as hdul:
            header = {k: v for k, v in hdul[0].header.items()}
            data = hdul[0].data
            if data is None:
                raise ValueError("FITS has no primary data array")

            # Dimensions
            height, width = (data.shape[-2], data.shape[-1]) if data.ndim >= 2 else (1, 1)

            # Telescope params
            focal_length = float(header.get("FOCALLEN", 1000.0))
            aperture = float(header.get("APERTURE", 200.0))

            # Sensor and pixel sizes
            pixsize1 = float(header.get("PIXSIZE1", 0.0))  # mm/pixel
            pixsize2 = float(header.get("PIXSIZE2", 0.0))  # mm/pixel
            if pixsize1 > 0 and pixsize2 > 0:
                sensor_width = pixsize1 * width
                sensor_height = pixsize2 * height
            else:
                sensor_width = 6.17  # mm fallback
                sensor_height = 4.55  # mm fallback

            # FOV estimation in degrees
            fov_width_deg = math.degrees(2.0 * math.atan(sensor_width / (2.0 * focal_length)))
            fov_height_deg = math.degrees(2.0 * math.atan(sensor_height / (2.0 * focal_length)))

            # Coordinates
            ra_deg, dec_deg = _parse_ra_dec_from_header(header)

            return {
                "image_width": int(width),
                "image_height": int(height),
                "focal_length": focal_length,
                "aperture": aperture,
                "sensor_width": sensor_width,
                "sensor_height": sensor_height,
                "fov_width_deg": fov_width_deg,
                "fov_height_deg": fov_height_deg,
                "ra_deg": ra_deg,
                "dec_deg": dec_deg,
                "is_color_camera": bool(header.get("COLORCAM", False)),
                "bayer_pattern": header.get("BAYERPAT", None),
            }
    except Exception as e:
        logger.error(f"Failed to extract FITS parameters: {e}")
        return {}


def convert_fits_to_png(fits_path: str, png_path: str, logger: logging.Logger) -> bool:
    try:
        import astropy.io.fits as fits
        import numpy as np
        from PIL import Image
    except Exception as e:  # pragma: no cover - dependency optional
        logger.error(f"Required libraries not available for FITS conversion: {e}")
        return False

    try:
        with fits.open(fits_path) as hdul:
            data = hdul[0].data
            if data is None:
                logger.error("No data in FITS file")
                return False

            arr = np.array(data)
            # Reduce to 2D for display if necessary
            if arr.ndim == 3 and arr.shape[0] in (3, 4):
                arr = arr[0]
            if arr.ndim == 3 and arr.shape[2] in (3, 4):
                arr = arr[:, :, 0]

            arr = arr.astype(float)
            # Robust normalization: ignore NaN/Inf and stretch by percentiles
            finite = np.isfinite(arr)
            if not finite.any():
                logger.error("FITS contains no finite pixel values")
                return False

            vals = arr[finite]
            try:
                lo, hi = np.nanpercentile(vals, (1.0, 99.5))
            except Exception:
                lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))

            if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
                lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))

            if hi <= lo:
                scaled = np.full_like(arr, 128.0)
            else:
                norm = (arr - lo) / (hi - lo)
                norm = np.clip(norm, 0.0, 1.0)
                # Mild asinh stretch to bring out faint detail without blowing highlights
                norm = np.arcsinh(norm * 3.0) / np.arcsinh(3.0)
                scaled = norm * 255.0

            # Let Pillow infer mode from dtype/shape (avoids future deprecation of 'mode=')
            img = Image.fromarray(scaled.astype("uint8")).convert("RGB")
            Path(png_path).parent.mkdir(parents=True, exist_ok=True)
            img.save(png_path)
            return True
    except Exception as e:
        logger.error(f"Failed to convert FITS to PNG: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve FITS and generate overlay + combined image")
    parser.add_argument("fits", help="Input FITS file")
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file path")
    parser.add_argument("--out", "-o", default="out", help="Output directory")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, ...)")
    parser.add_argument(
        "--image-size",
        default=None,
        help="Overlay image size as WIDTHxHEIGHT (default: FITS dimensions)",
    )
    args = parser.parse_args()

    logger = _setup_logging(args.log_level)

    fits_path = os.path.abspath(args.fits)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(fits_path):
        logger.error(f"FITS file not found: {fits_path}")
        sys.exit(1)

    # Load configuration
    config = ConfigManager(args.config)
    logger.info(f"Configuration loaded from: {args.config}")

    # Extract parameters from FITS
    logger.info("Extracting parameters from FITS header...")
    params = extract_fits_parameters(fits_path, logger)
    if not params:
        logger.error("Could not extract parameters from FITS. Aborting.")
        sys.exit(2)

    # Perform plate solving
    logger.info("Performing plate solving...")
    solver = PlateSolverFactory.create_solver(
        config.get_plate_solve_config().get("default_solver", "platesolve2"),
        config=config,
        logger=logger,
    )
    solve_result: Optional[Dict[str, Any]] = None
    wcs_path: Optional[str] = None
    if solver and solver.is_available():
        try:
            status = solver.solve(fits_path)
            if status.is_success and isinstance(status.data, dict):
                solve_result = status.data
                wcs_path = solve_result.get("wcs_path")
                logger.info(
                    "Solve OK: RA=%.4f Dec=%.4f FOV=%.3fx%.3f",
                    solve_result.get("ra_center", 0.0),
                    solve_result.get("dec_center", 0.0),
                    solve_result.get("fov_width", 0.0),
                    solve_result.get("fov_height", 0.0),
                )
            else:
                logger.warning(f"Solve failed: {getattr(status, 'message', 'unknown')}")
        except Exception as e:
            logger.warning(f"Solver error: {e}")
    else:
        logger.warning("Solver unavailable; proceeding with FITS header parameters")

    # Determine overlay parameters
    ra_deg = (solve_result or {}).get("ra_center", params.get("ra_deg", 0.0))
    dec_deg = (solve_result or {}).get("dec_center", params.get("dec_deg", 0.0))
    fov_w = (solve_result or {}).get("fov_width", params.get("fov_width_deg", 1.0))
    fov_h = (solve_result or {}).get("fov_height", params.get("fov_height_deg", 1.0))

    # Select overlay image size
    if args.image_size:
        try:
            w_s, h_s = args.image_size.lower().split("x")
            image_size = (int(w_s), int(h_s))
        except Exception:
            logger.warning("Invalid --image-size, using FITS dimensions")
            image_w = int(params.get("image_width", 1200))
            image_h = int(params.get("image_height", 800))
            image_size = (image_w, image_h)
    else:
        image_w = int(params.get("image_width", 1200))
        image_h = int(params.get("image_height", 800))
        image_size = (image_w, image_h)

    # Generate overlay
    overlay_png = os.path.join(out_dir, f"{Path(fits_path).stem}_overlay.png")
    gen = OverlayGenerator(config=config, logger=logger)
    logger.info("Generating overlay image...")
    gen.generate_overlay(
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        output_file=overlay_png,
        fov_width_deg=float(fov_w),
        fov_height_deg=float(fov_h),
        image_size=image_size,
        wcs_path=wcs_path,
    )
    logger.info(f"Overlay saved: {overlay_png}")

    # Convert FITS to PNG for combination
    base_png = os.path.join(out_dir, f"{Path(fits_path).stem}_image.png")
    logger.info("Converting FITS to PNG for combination...")
    if not convert_fits_to_png(fits_path, base_png, logger):
        logger.error("Failed to create base PNG from FITS; cannot combine")
        sys.exit(3)

    # Combine overlay with base image
    logger.info("Combining overlay with base image...")
    vp = VideoProcessor(config=config, logger=logger)
    combined_png = os.path.join(out_dir, f"{Path(fits_path).stem}_combined.png")
    status = vp.combine_overlay_with_image(base_png, overlay_png, output_path=combined_png)
    if status.is_success:
        logger.info(f"Combined image saved: {status.data}")
    else:
        logger.error(f"Failed to create combined image: {status.message}")
        sys.exit(4)

    print("\n=== Results ===")
    print(f"Overlay:   {overlay_png}")
    print(f"Combined:  {status.data}")


if __name__ == "__main__":
    main()
