#!/usr/bin/env python3
"""
Plate Solver Module for Astronomical Image Processing

This module provides a unified interface for different plate-solving engines,
including PlateSolve 2 and Astrometry.net. It implements a factory pattern
to create appropriate solver instances based on configuration.

Key Features:
- Unified interface for multiple plate-solving engines
- Factory pattern for solver instantiation
- Robust error handling and status reporting
- Configuration-based solver selection
- Support for both local (PlateSolve 2) and cloud-based (Astrometry.net) solving

Architecture:
- Abstract base class for solver implementations
- Factory class for solver creation
- Status-based error handling
- Configuration integration

Dependencies:
- External plate-solving software (PlateSolve 2, Astrometry.net)
- Configuration management
- Status and exception handling
"""

from abc import ABC, abstractmethod
import logging
import math
import os
import time
from typing import Dict, Optional, Tuple, Type

import numpy as np
from status import PlateSolveStatus, error_status, success_status


class PlateSolveResult:
    """Container for plate-solving results."""

    def __init__(
        self,
        ra_center: float,
        dec_center: float,
        fov_width: float,
        fov_height: float,
        solving_time: float,
        method: str,
        confidence: Optional[float] = None,
        position_angle: Optional[float] = None,
        image_size: Optional[Tuple[int, int]] = None,
        is_flipped: Optional[bool] = None,
        wcs_path: Optional[str] = None,
    ):
        self.ra_center = ra_center
        self.dec_center = dec_center
        self.fov_width = fov_width
        self.fov_height = fov_height
        self.solving_time = solving_time
        self.method = method
        self.confidence = confidence
        self.position_angle = position_angle
        self.image_size = image_size
        self.is_flipped = is_flipped
        self.wcs_path = wcs_path

    def __str__(self) -> str:
        try:
            ra_str = f"{self.ra_center:.4f}" if self.ra_center is not None else "None"
            dec_str = f"{self.dec_center:.4f}" if self.dec_center is not None else "None"
            fov_w_str = f"{self.fov_width:.3f}" if self.fov_width is not None else "None"
            fov_h_str = f"{self.fov_height:.3f}" if self.fov_height is not None else "None"
            time_str = f"{self.solving_time:.1f}" if self.solving_time is not None else "None"
            pa_str = f"{self.position_angle:.1f}" if self.position_angle is not None else "None"
            flipped_str = "Yes" if self.is_flipped else "No"
            confidence_str = ""
            if self.confidence is not None:
                try:
                    confidence_str = f", confidence={self.confidence:.2f}"
                except (ValueError, TypeError):
                    confidence_str = f", confidence={self.confidence}"
            return (
                f"PlateSolveResult(RA={ra_str}°, Dec={dec_str}°, "
                f"FOV={fov_w_str}°x{fov_h_str}°, PA={pa_str}°, "
                f"method={self.method}, time={time_str}s, flipped={flipped_str}{confidence_str})"
            )
        except Exception as e:
            return f"PlateSolveResult(error_formatting: {e})"

    def __repr__(self) -> str:
        return self.__str__()


class PlateSolver(ABC):
    """Abstract base class for plate-solving engines."""

    def __init__(self, config=None, logger=None):
        from config_manager import ConfigManager

        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)

    @abstractmethod
    def solve(self, image_path: str) -> PlateSolveStatus:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class PlateSolve2(PlateSolver):
    """PlateSolve 2 Integration."""

    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)
        self.plate_solve_config = self.config.get_plate_solve_config()
        ps2_cfg = self.plate_solve_config.get("platesolve2", {})
        self.executable_path: str = ps2_cfg.get("executable_path", "")
        self.working_directory: str = ps2_cfg.get("working_directory", "")
        self.timeout: int = ps2_cfg.get("timeout", 60)
        self.verbose: bool = ps2_cfg.get("verbose", False)
        self.auto_mode: bool = ps2_cfg.get("auto_mode", True)
        self.number_of_regions: int = ps2_cfg.get("number_of_regions", 1)
        self.min_stars: int = ps2_cfg.get("min_stars", 20)
        self.max_stars: int = ps2_cfg.get("max_stars", 200)
        try:
            from .platesolve2 import PlateSolve2Automated

            self.automated_solver = PlateSolve2Automated(config=self.config, logger=self.logger)
            self.automated_available: bool = True
            self.logger.info("Automated PlateSolve 2 solver available")
        except ImportError:
            self.automated_solver = None
            self.automated_available: bool = False
            self.logger.info("Automated PlateSolve 2 solver not available, using manual mode")

    def get_name(self) -> str:
        return "PlateSolve 2"

    def is_available(self) -> bool:
        return bool(self.executable_path)

    def solve(self, image_path: str) -> PlateSolveStatus:
        if not self.is_available():
            return error_status("PlateSolve 2 not available")
        if not os.path.exists(image_path):
            return error_status(f"Image file not found: {image_path}")
        start_time = time.time()
        try:
            if self.automated_available and self.automated_solver:
                self.logger.info("Attempting automated PlateSolve 2 solving")

                ra_deg = None
                dec_deg = None
                try:
                    from drivers.ascom.mount import ASCOMMount

                    mount = ASCOMMount(config=self.config, logger=self.logger)
                    mount_status = mount.get_coordinates()
                    if mount_status.is_success:
                        ra_deg, dec_deg = mount_status.data
                        self.logger.info(
                            f"Using mount coordinates: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°"
                        )
                    else:
                        self.logger.warning(
                            f"Could not get mount coordinates: {mount_status.message}"
                        )
                except Exception as e:
                    self.logger.warning(f"Could not get mount coordinates: {e}")

                fov_width_deg = None
                fov_height_deg = None
                try:
                    telescope_config = self.config.get_telescope_config()
                    camera_config = self.config.get_camera_config()
                    focal_length = telescope_config.get("focal_length", 1000)
                    sensor_width = camera_config.get("sensor_width", 6.17)
                    sensor_height = camera_config.get("sensor_height", 4.55)
                    # width/height swapped per ASCOM transposition
                    fov_width_deg = math.degrees(2 * math.atan(sensor_height / (2 * focal_length)))
                    fov_height_deg = math.degrees(2 * math.atan(sensor_width / (2 * focal_length)))
                    self.logger.info(
                        "Calculated FOV (transposed): %.4f° x %.4f° (focal=%smm, sensor=%sx%smm)",
                        fov_width_deg,
                        fov_height_deg,
                        str(focal_length),
                        str(sensor_width),
                        str(sensor_height),
                    )
                except Exception as e:
                    self.logger.warning(f"Could not calculate FOV: {e}")

                automated_result = self.automated_solver.solve(
                    image_path,
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                    fov_width_deg=fov_width_deg,
                    fov_height_deg=fov_height_deg,
                )

                if automated_result.is_success:
                    solving_time = time.time() - start_time
                    self.logger.info(f"Plate-solving successful in {solving_time:.2f} seconds")
                    return success_status(
                        "Automated solving successful",
                        data=automated_result.data,
                        details={"method": "automated", "solving_time": solving_time},
                    )
                else:
                    solving_time = time.time() - start_time
                    self.logger.warning(
                        "Automated solving failed after %.2f seconds: %s",
                        solving_time,
                        automated_result.message,
                    )
                    self.logger.info("Continuing with next exposure - conditions may improve")
                    return error_status(
                        f"Plate-solving failed: {automated_result.message}",
                        details={
                            "method": "automated",
                            "solving_time": solving_time,
                            "reason": "no_stars_or_poor_conditions",
                        },
                    )
            else:
                self.logger.error("No automated PlateSolve 2 solver available")
                return error_status("No automated PlateSolve 2 solver available")

        except Exception as e:
            solving_time = time.time() - start_time
            self.logger.error(f"PlateSolve 2 exception after {solving_time:.2f} seconds: {e}")
            return error_status(
                f"PlateSolve 2 error: {str(e)}", details={"solving_time": solving_time}
            )


class AstrometryNetSolver(PlateSolver):
    """Astrometry.net API Integration (Placeholder)."""

    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)
        self.api_key: str = (
            self.config.get_plate_solve_config().get("astrometry", {}).get("api_key", "")
        )
        self.api_url: str = "http://nova.astrometry.net/api/"

    def get_name(self) -> str:
        return "Astrometry.net"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def solve(self, image_path: str) -> PlateSolveStatus:
        return error_status("Astrometry.net solver not yet implemented")


class LocalAstrometryNetSolver(PlateSolver):
    """Local astrometry.net solver using the 'solve-field' CLI."""

    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)
        a_cfg = self.config.get_plate_solve_config().get("astrometry_local", {})
        self.solve_field_path: str = a_cfg.get("solve_field_path", "solve-field")
        self.working_directory: str = a_cfg.get("working_directory", "astrometry_output")
        self.timeout_s: float = float(a_cfg.get("timeout", 120))
        # Search radius (deg) when RA/Dec hints are provided
        self.search_radius_deg: float = float(a_cfg.get("search_radius_deg", 1.0))
        # Downsample factor (e.g., 2)
        self.downsample: int = int(a_cfg.get("downsample", 2))
        # Pixel scale padding around estimate (arcsec/pix)
        self.scale_pad: float = float(a_cfg.get("scale_pad_arcsec", 0.1))
        # On Windows, 'solve-field' commonly runs via a bash-compatible shell (WSL/Git Bash)
        # Configure a wrapper to invoke through bash if desired.
        self.use_bash_wrapper: bool = bool(a_cfg.get("use_bash", os.name == "nt"))
        self.bash_path: str = a_cfg.get("bash_path", "bash")
        # Default to login + command; PowerShell example: bash -lc "solve-field ..."
        self.bash_args: list[str] = a_cfg.get("bash_args", ["-lc"])

    def get_name(self) -> str:
        return "Astrometry.net (local)"

    def is_available(self) -> bool:
        # Consider available if the command is configured or in PATH
        return bool(self.solve_field_path)

    def _estimate_pixel_scale_arcsec(self) -> float:
        try:
            # Estimate scale from config: pixel_size (µm) and focal_length (mm)
            camera_cfg = self.config.get_camera_config()
            telescope_cfg = self.config.get_telescope_config()
            pixel_size_um = float(camera_cfg.get("pixel_size", 3.75))
            focal_length_mm = float(telescope_cfg.get("focal_length", 1000.0))
            # Apply binning if configured
            bin_x = 1.0
            try:
                # ASCOM-style
                ascom_cfg = camera_cfg.get("ascom", {})
                if "binning" in ascom_cfg:
                    bin_x = float(ascom_cfg.get("binning", 1))
                # Alpaca-style list [bx, by]
                alpaca_cfg = camera_cfg.get("alpaca", {})
                if "binning" in alpaca_cfg:
                    b = alpaca_cfg.get("binning", [1, 1])
                    if isinstance(b, (list, tuple)) and len(b) > 0:
                        bin_x = float(b[0] or 1)
            except Exception:
                pass
            pixel_size_mm = pixel_size_um / 1000.0
            effective_pixel_mm = pixel_size_mm * bin_x
            # 206265 arcsec per radian
            return (effective_pixel_mm / focal_length_mm) * 206265.0
        except Exception:
            # Fallback to a typical small-sensor scale
            return 1.5

    def _build_command(
        self,
        image_path: str,
        ra_deg: Optional[float],
        dec_deg: Optional[float],
        pixel_scale_arcsec: float,
    ) -> tuple[list[str], str]:
        from pathlib import Path as _Path

        # Prepare working directory and output path hints
        out_dir = _Path(self.working_directory)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        img_path = _Path(image_path)
        base = img_path.stem
        new_fits = str(out_dir / f"{base}.new")

        # scale-low/high window around estimate
        low = max(0.01, pixel_scale_arcsec - self.scale_pad)
        high = pixel_scale_arcsec + self.scale_pad

        # Use POSIX-style paths when wrapping via bash (Git Bash / WSL)
        dir_arg = out_dir.as_posix() if self.use_bash_wrapper else str(out_dir)
        img_arg = img_path.as_posix() if self.use_bash_wrapper else str(img_path)

        cmd = [
            self.solve_field_path,
            "--overwrite",
            "--no-plots",
            "--fits-image",
            "--scale-units",
            "arcsecperpix",
            "--scale-low",
            f"{low}",
            "--scale-high",
            f"{high}",
            "--dir",
            dir_arg,
            "--downsample",
            str(self.downsample),
        ]
        if ra_deg is not None and dec_deg is not None:
            cmd.extend(
                [
                    "--ra",
                    f"{ra_deg}",
                    "--dec",
                    f"{dec_deg}",
                    "--radius",
                    f"{self.search_radius_deg}",
                ]
            )
        # Input image path last; ensure safe quoting via shlex.split on composed
        cmd.append(img_arg)
        return cmd, new_fits

    def _parse_sexagesimal_to_deg(self, value: str, is_ra: bool) -> Optional[float]:
        try:
            text = str(value).strip()
            if not text:
                return None
            # Normalize separators
            text = text.replace(" ", ":").replace("::", ":")
            parts_s = text.split(":")
            parts = []
            for p in parts_s:
                if p == "":
                    continue
                parts.append(float(p))
            if not parts:
                return None
            if is_ra:
                # RA given in hours:minutes:seconds -> convert to degrees
                hours = parts[0]
                minutes = parts[1] if len(parts) > 1 else 0.0
                seconds = parts[2] if len(parts) > 2 else 0.0
                hours_total = abs(hours) + minutes / 60.0 + seconds / 3600.0
                if hours < 0:
                    hours_total = -hours_total
                return hours_total * 15.0
            else:
                # Dec in degrees:minutes:seconds
                sign = -1.0 if str(value).lstrip().startswith("-") else 1.0
                degrees = abs(parts[0])
                minutes = parts[1] if len(parts) > 1 else 0.0
                seconds = parts[2] if len(parts) > 2 else 0.0
                deg_total = degrees + minutes / 60.0 + seconds / 3600.0
                return sign * deg_total
        except Exception:
            return None

    def _read_ra_dec_hints_from_image(
        self, image_path: str
    ) -> tuple[Optional[float], Optional[float]]:
        try:
            import astropy.io.fits as fits
        except Exception:
            return None, None
        try:
            with fits.open(image_path) as hdul:
                hdr = hdul[0].header
                # Try common keys with numeric degrees first
                ra = hdr.get("RA")
                dec = hdr.get("DEC")
                ra_deg: Optional[float] = None
                dec_deg: Optional[float] = None
                # Numeric RA/DEC
                if isinstance(ra, (int, float)):
                    ra_deg = float(ra)
                    # Heuristic: RA may be in hours if <= 24
                    if 0.0 <= ra_deg <= 24.0:
                        ra_deg = ra_deg * 15.0
                if isinstance(dec, (int, float)):
                    dec_deg = float(dec)
                # Sexagesimal strings
                if ra_deg is None:
                    ra_str = hdr.get("OBJCTRA") or hdr.get("RA_OBJ") or hdr.get("TELRA")
                    if isinstance(ra_str, str):
                        ra_deg = self._parse_sexagesimal_to_deg(ra_str, is_ra=True)
                if dec_deg is None:
                    dec_str = hdr.get("OBJCTDEC") or hdr.get("DEC_OBJ") or hdr.get("TELDEC")
                    if isinstance(dec_str, str):
                        dec_deg = self._parse_sexagesimal_to_deg(dec_str, is_ra=False)
                # WCS center (if present) as a last resort
                if ra_deg is None and "CRVAL1" in hdr:
                    try:
                        ra_deg = float(hdr.get("CRVAL1"))
                    except Exception:
                        pass
                if dec_deg is None and "CRVAL2" in hdr:
                    try:
                        dec_deg = float(hdr.get("CRVAL2"))
                    except Exception:
                        pass
                # Validate ranges
                if ra_deg is not None and not (0.0 <= ra_deg < 360.0):
                    ra_deg = None
                if dec_deg is not None and not (-90.0 <= dec_deg <= 90.0):
                    dec_deg = None
                return ra_deg, dec_deg
        except Exception:
            return None, None

    def _parse_wcs_result(self, new_fits_path: str, image_path: str) -> Dict[str, object]:
        try:
            import astropy.io.fits as fits
            from astropy.wcs import WCS
            from astropy.wcs.utils import proj_plane_pixel_scales
        except Exception as e:
            raise RuntimeError(f"Astropy required to parse WCS: {e}") from e

        with fits.open(new_fits_path) as hdul:
            hdr = hdul[0].header
            data = hdul[0].data
            w = WCS(hdr)
            if data is not None and hasattr(data, "shape"):
                if data.ndim == 2:
                    height, width = data.shape
                elif data.ndim == 3:
                    height, width = data.shape[-2], data.shape[-1]
                else:
                    height = int(hdr.get("NAXIS2", 0))
                    width = int(hdr.get("NAXIS1", 0))
            else:
                height = int(hdr.get("NAXIS2", 0))
                width = int(hdr.get("NAXIS1", 0))

        # Center from WCS
        ra_center = float(w.wcs.crval[0])
        dec_center = float(w.wcs.crval[1])
        # Pixel scales
        scales_deg = proj_plane_pixel_scales(w)
        scale_x_deg = float(scales_deg[0])
        scale_y_deg = float(scales_deg[1])
        fov_width_deg = scale_x_deg * float(width)
        fov_height_deg = scale_y_deg * float(height)
        # Position angle approximation from CD matrix
        if getattr(w.wcs, "cd", None) is not None:
            cd = np.array(w.wcs.cd, dtype=float)
        else:
            pc = np.array(getattr(w.wcs, "pc", np.eye(2)), dtype=float)
            cdelt = np.array(getattr(w.wcs, "cdelt", [scale_x_deg, scale_y_deg]), dtype=float)
            cd = pc @ np.diag(cdelt)
        pa_rad = math.atan2(cd[0, 1], cd[0, 0])
        position_angle = math.degrees(pa_rad)

        return {
            "ra_center": ra_center,
            "dec_center": dec_center,
            "fov_width": fov_width_deg,
            "fov_height": fov_height_deg,
            "position_angle": position_angle,
            "image_size": (int(width), int(height)),
            "pixel_scale": (scale_x_deg + scale_y_deg) * 0.5 * 3600.0,
            "method": self.get_name(),
            "wcs_path": new_fits_path,
        }

    def solve(self, image_path: str) -> PlateSolveStatus:
        if not self.is_available():
            return error_status("Astrometry.net (local) not available")
        if not os.path.exists(image_path):
            return error_status(f"Image file not found: {image_path}")
        start_time = time.time()
        try:
            # Prefer RA/Dec hints from the FITS header if available
            ra_hint, dec_hint = self._read_ra_dec_hints_from_image(image_path)
            if ra_hint is not None and dec_hint is not None:
                self.logger.info(
                    "Using image header coordinates: RA=%.6f°, Dec=%.6f°",
                    ra_hint,
                    dec_hint,
                )
            else:
                # Fallback to mount coordinates
                try:
                    from drivers.ascom.mount import ASCOMMount

                    mount = ASCOMMount(config=self.config, logger=self.logger)
                    mstat = mount.get_coordinates()
                    if mstat.is_success:
                        ra_hint, dec_hint = mstat.data
                        # Heuristic: if mount returns RA in hours (<=24), convert to degrees
                        if isinstance(ra_hint, (int, float)) and 0.0 <= float(ra_hint) <= 24.0:
                            ra_hint = float(ra_hint) * 15.0
                        self.logger.info(
                            "Using mount coordinates: RA=%.6f°, Dec=%.6f°",
                            float(ra_hint) if ra_hint is not None else float("nan"),
                            float(dec_hint) if dec_hint is not None else float("nan"),
                        )
                except Exception as e:
                    self.logger.debug(f"Mount RA/Dec hint unavailable: {e}")

            scale_arcsec = self._estimate_pixel_scale_arcsec()
            cmd, new_fits = self._build_command(image_path, ra_hint, dec_hint, scale_arcsec)

            import subprocess

            # On Windows or when configured, wrap command via bash (e.g., WSL/Git Bash)
            if self.use_bash_wrapper:
                import shlex as _shlex

                cmd_str = _shlex.join(cmd)
                full_cmd = [self.bash_path] + list(self.bash_args) + [cmd_str]
                # Log as a PowerShell-friendly string with quotes around the -c payload
                try:
                    bash_prefix = " ".join([self.bash_path] + list(self.bash_args))
                    self.logger.info(
                        'Running (bash-wrapped) solve-field: %s "%s"',
                        bash_prefix,
                        cmd_str,
                    )
                except Exception:
                    self.logger.info("Running (bash-wrapped) solve-field: %s", " ".join(full_cmd))
                proc = subprocess.run(
                    full_cmd,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_s,
                )
            else:
                self.logger.info("Running solve-field: %s", " ".join(cmd))
                proc = subprocess.run(
                    cmd,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_s,
                )
            # Log full stdout/stderr at debug level for diagnostics
            if proc.stdout:
                self.logger.debug("solve-field stdout:\n%s", proc.stdout)
            if proc.stderr:
                self.logger.debug("solve-field stderr:\n%s", proc.stderr)

            if proc.returncode != 0:
                msg = proc.stderr or proc.stdout or "solve-field failed"
                # Try to parse hints even on failure
                combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
                hints = self._parse_cli_output_for_hints(combined_output)
                return error_status(
                    f"Astrometry.net solve-field error: {msg}",
                    details={"cli_hints": hints},
                )

            if not os.path.exists(new_fits):
                return error_status("Astrometry.net did not produce a .new FITS file")

            data = self._parse_wcs_result(new_fits, image_path)
            # Enrich data with CLI hints if available
            try:
                combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
                cli_hints = self._parse_cli_output_for_hints(combined_output)
                for k, v in cli_hints.items():
                    # Do not overwrite core WCS-derived fields unless missing
                    if k in (
                        "ra_center",
                        "dec_center",
                        "fov_width",
                        "fov_height",
                        "position_angle",
                    ):
                        if k not in data or data.get(k) in (None, 0, 0.0):
                            data[k] = v
                    else:
                        data[k] = v
            except Exception:
                pass
            solving_time = time.time() - start_time
            return success_status(
                "Astrometry.net local solving successful",
                data=data,
                details={"solving_time": solving_time, "method": self.get_name()},
            )
        except subprocess.TimeoutExpired:
            return error_status(f"Astrometry.net solve-field timed out after {self.timeout_s}s")
        except Exception as e:
            solving_time = time.time() - start_time
            self.logger.error(f"Astrometry.net local exception after {solving_time:.2f}s: {e}")
            return error_status(f"Astrometry.net local error: {e}")

    @staticmethod
    def _parse_cli_output_for_hints(text: str) -> Dict[str, object]:
        """Parse solve-field stdout/stderr for useful hints (best-effort).

        Returns a dict possibly containing keys:
        - solved (bool)
        - ra_center (float)
        - dec_center (float)
        - pixel_scale (float, arcsec/pix)
        - fov_width (float, deg)
        - fov_height (float, deg)
        - position_angle (float, deg East of North)
        - is_flipped (bool) from parity (neg => True)
        """
        import re as _re

        info: Dict[str, object] = {}
        try:
            solved = (
                "Field 1 solved" in text
                or ".solved to indicate this" in text
                or "Field center:" in text
            )
            info["solved"] = bool(solved)

            # RA/Dec (Field center)
            m = _re.search(r"Field center: \(RA,Dec\) = \(([^,]+), ([^)]+)\) deg\.", text)
            if m:
                try:
                    info["ra_center"] = float(m.group(1))
                    info["dec_center"] = float(m.group(2))
                except Exception:
                    pass

            # RA,Dec with scale
            m = _re.search(
                r"RA,Dec = \(([^,]+),([^\)]+)\), pixel scale ([0-9.]+) arcsec/pix",
                text,
            )
            if m:
                try:
                    info.setdefault("ra_center", float(m.group(1)))
                    info.setdefault("dec_center", float(m.group(2)))
                    info["pixel_scale"] = float(m.group(3))
                except Exception:
                    pass

            # Field size
            m = _re.search(
                r"Field size: ([0-9.]+) x ([0-9.]+) degrees",
                text,
            )
            if m:
                try:
                    info["fov_width"] = float(m.group(1))
                    info["fov_height"] = float(m.group(2))
                except Exception:
                    pass

            # Rotation angle
            m = _re.search(
                r"Field rotation angle: up is ([^ ]+) degrees E of N",
                text,
            )
            if m:
                try:
                    info["position_angle"] = float(m.group(1))
                except Exception:
                    pass

            # Parity
            m = _re.search(r"Field parity: (\w+)", text)
            if m:
                parity = m.group(1).strip().lower()
                info["is_flipped"] = parity == "neg"
        except Exception:
            pass
        return info


class PlateSolverFactory:
    """Factory for plate solver instances."""

    @staticmethod
    def create_solver(
        solver_type: Optional[str] = None, config=None, logger=None
    ) -> Optional[PlateSolver]:
        if solver_type is None:
            if config:
                solver_type = config.get_plate_solve_config().get("default_solver", "platesolve2")
            else:
                from config_manager import ConfigManager

                default_config = ConfigManager()
                solver_type = default_config.get_plate_solve_config().get(
                    "default_solver", "platesolve2"
                )

        solvers: Dict[str, Type[PlateSolver]] = {
            "platesolve2": PlateSolve2,
            "astrometry": AstrometryNetSolver,
            "astrometry_local": LocalAstrometryNetSolver,
        }

        solver_class: Optional[Type[PlateSolver]] = solvers.get(solver_type.lower())
        if solver_class:
            return solver_class(config=config, logger=logger)
        else:
            if logger:
                logger.error(f"Unknown solver type: {solver_type}")
            else:
                logging.error(f"Unknown solver type: {solver_type}")
            return None

    @staticmethod
    def get_available_solvers(config=None, logger=None) -> Dict[str, bool]:
        solvers: Dict[str, PlateSolver] = {
            "platesolve2": PlateSolve2(config=config, logger=logger),
            "astrometry": AstrometryNetSolver(config=config, logger=logger),
            "astrometry_local": LocalAstrometryNetSolver(config=config, logger=logger),
        }
        return {name: solver.is_available() for name, solver in solvers.items()}
