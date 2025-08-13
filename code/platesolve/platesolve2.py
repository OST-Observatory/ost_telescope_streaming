#!/usr/bin/env python3
"""
Automated PlateSolve 2 integration using the correct command line format.
Format: ra,dec,width_field_of_view,height_field_of_view,number_of_regions_to_test,path_to_image,"0"
All coordinates and FOV must be in radians.
"""

import logging
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from status import PlateSolveStatus, error_status, success_status


class PlateSolve2Automated:
    """Automated PlateSolve 2 integration with correct command line format."""

    def __init__(self, config=None, logger=None):
        from config_manager import ConfigManager

        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)

        ps2_cfg = self.config.get_plate_solve_config().get("platesolve2", {})
        self.executable_path = ps2_cfg.get("executable_path", "")
        self.working_directory = ps2_cfg.get("working_directory", "")
        self.timeout: float = float(ps2_cfg.get("timeout", 60))
        self.verbose = ps2_cfg.get("verbose", False)
        self.number_of_regions: int = int(ps2_cfg.get("number_of_regions", 1))
        self.current_process = None

    def solve(
        self,
        image_path: str,
        ra_deg: Optional[float] = None,
        dec_deg: Optional[float] = None,
        fov_width_deg: Optional[float] = None,
        fov_height_deg: Optional[float] = None,
    ) -> PlateSolveStatus:
        start_time = time.time()
        try:
            abs_image_path = str(Path(image_path).resolve())
            self.logger.info(f"Using absolute image path: {abs_image_path}")
            if not os.path.exists(abs_image_path):
                return error_status(f"Image file not found: {abs_image_path}")
            if not os.access(abs_image_path, os.R_OK):
                return error_status(f"Image file not readable: {abs_image_path}")
            file_size = os.path.getsize(abs_image_path)
            if file_size == 0:
                return error_status(f"Image file is empty: {abs_image_path}")
            self.logger.info(f"Image file validated: {abs_image_path} (size: {file_size} bytes)")

            apm_path = self._get_apm_path(abs_image_path)
            if os.path.exists(apm_path):
                os.remove(apm_path)
                self.logger.debug(f"Removed old .apm file: {apm_path}")

            ra_rad, dec_rad, fov_width_rad, fov_height_rad = self._prepare_parameters(
                ra_deg, dec_deg, fov_width_deg, fov_height_deg
            )

            cmd_string = self._build_command_string(
                abs_image_path, ra_rad, dec_rad, fov_width_rad, fov_height_rad
            )
            if self.verbose:
                self.logger.info(f"PlateSolve 2 command: {cmd_string}")

            self._execute_platesolve2(cmd_string)

            apm_timeout: float = 10.0
            waited: float = 0.0
            while not os.path.exists(apm_path) and waited < apm_timeout:
                time.sleep(0.5)
                waited += 0.5

            if not os.path.exists(apm_path):
                return error_status(f"No .apm result file found after {apm_timeout}s")

            result_dict: Dict[str, Any] = {}
            result_dict = self._parse_apm_file(apm_path, result_dict, image_path)

            if result_dict.get("success"):
                return success_status(
                    "PlateSolve2 automated solving successful",
                    data=result_dict,
                    details={"solving_time": time.time() - start_time},
                )
            else:
                return error_status(
                    f"PlateSolve2 did not find a valid solution: {result_dict.get('error_message')}"
                )
        except Exception as e:
            self.logger.error(f"PlateSolve2 automation error: {e}")
            return error_status(f"PlateSolve2 automation error: {e}")
        finally:
            self._cleanup()

    def _is_available(self) -> bool:
        if not self.executable_path:
            self.logger.warning("PlateSolve 2 path not configured")
            return False
        executable = Path(self.executable_path)
        if not executable.exists():
            self.logger.warning(f"PlateSolve 2 executable not found: {self.executable_path}")
            return False
        return True

    def _get_apm_path(self, image_path: str) -> str:
        image_path_obj = Path(image_path)
        apm_filename = image_path_obj.stem + ".apm"
        apm_path = image_path_obj.parent / apm_filename
        if self.verbose:
            self.logger.info(f"Expected APM file: {apm_path}")
        return str(apm_path)

    def _prepare_parameters(
        self,
        ra_deg: Optional[float],
        dec_deg: Optional[float],
        fov_width_deg: Optional[float],
        fov_height_deg: Optional[float],
    ) -> tuple[float, float, float, float]:
        ra_rad = math.radians(ra_deg) if ra_deg is not None else 0.0
        dec_rad = math.radians(dec_deg) if dec_deg is not None else 0.0
        if fov_width_deg is None or fov_height_deg is None:
            fov_width_deg, fov_height_deg = self._calculate_fov()
        fov_width_rad = math.radians(fov_width_deg)
        fov_height_rad = math.radians(fov_height_deg)
        if self.verbose:
            self.logger.info(
                "Parameters: RA=%.4f°, Dec=%.4f°, FOV=%.4f°x%.4f°",
                math.degrees(ra_rad),
                math.degrees(dec_rad),
                fov_width_deg,
                fov_height_deg,
            )
        return ra_rad, dec_rad, fov_width_rad, fov_height_rad

    def _calculate_fov(self) -> Tuple[float, float]:
        telescope_config = self.config.get_telescope_config()
        camera_config = self.config.get_camera_config()
        focal_length = telescope_config.get("focal_length", 1000)
        sensor_width = camera_config.get("sensor_width", 6.17)
        sensor_height = camera_config.get("sensor_height", 4.55)
        fov_width_deg = math.degrees(2 * math.atan(sensor_width / (2 * focal_length)))
        fov_height_deg = math.degrees(2 * math.atan(sensor_height / (2 * focal_length)))
        if self.verbose:
            self.logger.info(
                "Calculated FOV: %.4f° x %.4f° (focal=%smm, sensor=%sx%smm)",
                fov_width_deg,
                fov_height_deg,
                focal_length,
                sensor_width,
                sensor_height,
            )
        return fov_width_deg, fov_height_deg

    def _build_command_string(
        self,
        image_path: str,
        ra_rad: float,
        dec_rad: float,
        fov_width_rad: float,
        fov_height_rad: float,
    ) -> str:
        normalized_image_path = str(Path(image_path)).replace("\\", "/")
        cmd_parts = [
            str(ra_rad),
            str(dec_rad),
            str(fov_width_rad),
            str(fov_height_rad),
            str(self.number_of_regions),
            normalized_image_path,
            "0",
        ]
        return ",".join(cmd_parts)

    def _execute_platesolve2(self, cmd_string: str) -> bool:
        try:
            full_cmd = [self.executable_path, cmd_string]
            if self.verbose:
                self.logger.info(f"Executing: {' '.join(full_cmd)}")
            working_dir = None
            if self.working_directory:
                working_dir = str(Path(self.working_directory).resolve())
                if not os.path.exists(working_dir):
                    os.makedirs(working_dir, exist_ok=True)
                    self.logger.info(f"Created working directory: {working_dir}")
                elif not os.access(working_dir, os.W_OK):
                    self.logger.warning(f"Working directory not writable: {working_dir}")
                    working_dir = str(Path(self.executable_path).parent)
            else:
                working_dir = str(Path(self.executable_path).parent)
            self.logger.info(f"Working directory: {working_dir}")
            self.current_process = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=self.timeout, cwd=working_dir
            )
            if self.verbose:
                if self.current_process.stdout:
                    self.logger.info(f"STDOUT: {self.current_process.stdout}")
                if self.current_process.stderr:
                    self.logger.warning(f"STDERR: {self.current_process.stderr}")
            if self.current_process.returncode == 0:
                self.logger.info("PlateSolve 2 executed successfully")
                return True
            else:
                self.logger.error(
                    f"PlateSolve 2 failed with return code: {self.current_process.returncode}"
                )
                if self.current_process.stderr:
                    self.logger.error(f"Error output: {self.current_process.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error("PlateSolve 2 execution timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error executing PlateSolve 2: {e}")
            return False

    def _parse_apm_file(
        self, apm_path: str, result: Dict[str, Any], image_path: str
    ) -> Dict[str, Any]:
        try:
            with open(apm_path, "r") as f:
                lines = [line.strip() for line in f.readlines()]
            if len(lines) < 3:
                result["error_message"] = f".apm file has too few lines: {lines}"
                return result

            line1 = lines[0]
            if self.verbose:
                self.logger.info(f"Parsing line 1: {line1}")
            parts = line1.split(",")
            if len(parts) != 5:
                result["error_message"] = (
                    f"Line 1 does not have exactly 5 parts: {line1} (found {len(parts)} parts)"
                )
                return result

            ra_rad = float(parts[0] + "." + parts[1])
            dec_rad = float(parts[2] + "." + parts[3])
            code_1 = int(parts[4])
            ra_deg = math.degrees(ra_rad)
            dec_deg = math.degrees(dec_rad)
            result["ra_center"] = ra_deg
            result["dec_center"] = dec_deg
            if self.verbose:
                self.logger.info(f"Parsed RA: {ra_rad} rad = {ra_deg:.6f}°")
                self.logger.info(f"Parsed Dec: {dec_rad} rad = {dec_deg:.6f}°")
                self.logger.info(f"Parsed Code_1: {code_1}")

            line2 = lines[1]
            if self.verbose:
                self.logger.info(f"Parsing line 2: {line2}")
            parts2 = line2.split(",")
            if len(parts2) != 9:
                result["error_message"] = (
                    f"Line 2 does not have exactly 9 parts: {line2} (found {len(parts2)} parts)"
                )
                return result

            pixel_scale = float(parts2[0] + "." + parts2[1])
            position_angle = float(parts2[2] + "." + parts2[3])
            if_flipped = int(parts2[4])
            code_2 = int(parts2[5])
            code_3 = float(parts2[6] + "." + parts2[7])
            n_stars = int(parts2[8])

            if if_flipped >= 1:
                position_angle = (position_angle + 180.0) % 360.0

            result["pixel_scale"] = pixel_scale
            result["position_angle"] = position_angle
            result["flipped"] = if_flipped
            result["stars_detected"] = n_stars

            try:
                from PIL import Image

                with Image.open(image_path) as img:
                    image_width, image_height = img.size
                    result["image_size"] = (image_width, image_height)
                    fov_width_deg = (pixel_scale * image_width) / 3600.0
                    fov_height_deg = (pixel_scale * image_height) / 3600.0
                    result["fov_width"] = fov_width_deg
                    result["fov_height"] = fov_height_deg
                    if self.verbose:
                        self.logger.info(f"Image size: {image_width}x{image_height} pixels")
                        self.logger.info(
                            f"Calculated FOV: {fov_width_deg:.4f}° x {fov_height_deg:.4f}°"
                        )
            except Exception as e:
                self.logger.warning(f"Could not determine image size: {e}")
                result["image_size"] = None
                result["fov_width"] = None
                result["fov_height"] = None

            valid_line = lines[2]
            if "Valid" in valid_line:
                result["success"] = True
                result["confidence"] = 0.99
            else:
                result["success"] = False
                result["error_message"] = f"PlateSolve 2 did not find a valid solution: {lines[2]}"
            return result
        except Exception as e:
            result["error_message"] = f"Error parsing .apm file: {str(e)}"
            if self.verbose:
                self.logger.error(f"APM parsing error: {e}")
                self.logger.error(
                    f"APM file content: {lines if 'lines' in locals() else 'Could not read file'}"
                )
            return result

    def _cleanup(self):
        try:
            pass
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        self.current_process = None
