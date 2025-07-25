#!/usr/bin/env python3
"""
Automated PlateSolve 2 integration using the correct command line format.
Format: ra,dec,width_field_of_view,height_field_of_view,number_of_regions_to_test,path_to_image,"0"
All coordinates and FOV must be in radians.
"""

import subprocess
import os
import time
import logging
import math
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import re


from exceptions import PlateSolveError, FileError
from status import PlateSolveStatus, success_status, error_status, warning_status

class PlateSolve2Automated:
    """Automated PlateSolve 2 integration with correct command line format."""
    def __init__(self, config=None, logger=None):
        from config_manager import ConfigManager
        # Only create default config if no config is provided
        # This prevents loading config.yaml when config is passed from tests
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
        import logging
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        
        ps2_cfg = self.config.get_plate_solve_config().get('platesolve2', {})
        self.executable_path = ps2_cfg.get('executable_path', '')
        self.working_directory = ps2_cfg.get('working_directory', '')
        self.timeout = ps2_cfg.get('timeout', 60)
        self.verbose = ps2_cfg.get('verbose', False)
        self.number_of_regions = ps2_cfg.get('number_of_regions', 1)
        # Remove any old direct plate_solve_config accesses for these keys.
        
        # Setup logging
        # self.logger = logging.getLogger(__name__) # This line is now redundant as logger is passed to __init__
        
        # Process tracking
        self.current_process = None
    
    def solve(self, image_path: str, ra_deg: Optional[float] = None, dec_deg: Optional[float] = None, fov_width_deg: Optional[float] = None, fov_height_deg: Optional[float] = None) -> PlateSolveStatus:
        """Automated plate-solving with PlateSolve2.
        Returns:
            PlateSolveStatus: Status object with result or error.
        """
        start_time = time.time()
        try:
            # Remove old .apm file if it exists
            apm_path = self._get_apm_path(image_path)
            if os.path.exists(apm_path):
                os.remove(apm_path)
            # Calculate or estimate parameters
            ra_rad, dec_rad, fov_width_rad, fov_height_rad = self._prepare_parameters(
                ra_deg, dec_deg, fov_width_deg, fov_height_deg
            )
            # Build command line string
            cmd_string = self._build_command_string(
                image_path, ra_rad, dec_rad, fov_width_rad, fov_height_rad
            )
            if self.verbose:
                self.logger.info(f"PlateSolve 2 command: {cmd_string}")
            # Execute PlateSolve 2
            success = self._execute_platesolve2(cmd_string)
            # Wait for .apm file to appear (max 10s)
            apm_timeout = 10
            waited = 0
            while not os.path.exists(apm_path) and waited < apm_timeout:
                time.sleep(0.5)
                waited += 0.5
            if not os.path.exists(apm_path):
                return error_status(f"No .apm result file found after {apm_timeout}s")
            # Parse .apm file
            result_dict = {}
            result_dict = self._parse_apm_file(apm_path, result_dict, image_path)
            if result_dict.get('success'):
                return success_status(
                    "PlateSolve2 automated solving successful",
                    data=result_dict,
                    details={'solving_time': time.time() - start_time}
                )
            else:
                return error_status(f"PlateSolve2 did not find a valid solution: {result_dict.get('error_message')}")
        except Exception as e:
            self.logger.error(f"PlateSolve2 automation error: {e}")
            return error_status(f"PlateSolve2 automation error: {e}")
        finally:
            self._cleanup()
    
    def _is_available(self) -> bool:
        """Checks if PlateSolve 2 is available."""
        if not self.executable_path:
            self.logger.warning("PlateSolve 2 path not configured")
            return False
        
        executable = Path(self.executable_path)
        if not executable.exists():
            self.logger.warning(f"PlateSolve 2 executable not found: {self.executable_path}")
            return False
        
        return True
    
    def _get_apm_path(self, image_path: str) -> str:
        """Generates the path to the APM file based on the image path.
        
        Args:
            image_path: Path to the input image file
            
        Returns:
            str: Path to the expected APM file
        """
        # Convert to Path object for easier manipulation
        image_path_obj = Path(image_path)
        
        # Create APM filename: same name but .apm extension
        apm_filename = image_path_obj.stem + ".apm"
        
        # APM file is in the same directory as the input file
        apm_path = image_path_obj.parent / apm_filename
        
        if self.verbose:
            self.logger.info(f"Expected APM file: {apm_path}")
        
        return str(apm_path)
    
    def _prepare_parameters(self, ra_deg: Optional[float], dec_deg: Optional[float], fov_width_deg: Optional[float], fov_height_deg: Optional[float]) -> tuple[float, float, float, float]:
        """Prepares parameters for the PlateSolve 2 call."""
        
        # Convert RA/Dec to radians (use 0,0 if not provided)
        ra_rad = math.radians(ra_deg) if ra_deg is not None else 0.0
        dec_rad = math.radians(dec_deg) if dec_deg is not None else 0.0
        
        # Calculate FOV if not provided
        if fov_width_deg is None or fov_height_deg is None:
            fov_width_deg, fov_height_deg = self._calculate_fov()
        
        # Convert FOV to radians
        fov_width_rad = math.radians(fov_width_deg)
        fov_height_rad = math.radians(fov_height_deg)
        
        if self.verbose:
            self.logger.info(f"Parameters: RA={math.degrees(ra_rad):.4f}°, Dec={math.degrees(dec_rad):.4f}°, "
                           f"FOV={math.degrees(fov_width_rad):.4f}°x{math.degrees(fov_height_rad):.4f}°")
        
        return ra_rad, dec_rad, fov_width_rad, fov_height_rad
    
    def _calculate_fov(self) -> Tuple[float, float]:
        """Calculate field of view from telescope and camera configuration."""
        telescope_config = self.config.get_telescope_config()
        camera_config = self.config.get_camera_config()
        video_config = self.config.get_video_config()
        
        # Get focal length (mm)
        focal_length = telescope_config.get('focal_length', 1000)
        
        # Get sensor dimensions (mm)
        sensor_width = camera_config.get('sensor_width', 6.17)
        sensor_height = camera_config.get('sensor_height', 4.55)
        
        # Calculate FOV in degrees
        fov_width_deg = math.degrees(2 * math.atan(sensor_width / (2 * focal_length)))
        fov_height_deg = math.degrees(2 * math.atan(sensor_height / (2 * focal_length)))
        
        if self.verbose:
            self.logger.info(f"Calculated FOV: {fov_width_deg:.4f}° x {fov_height_deg:.4f}° "
                           f"(focal={focal_length}mm, sensor={sensor_width}x{sensor_height}mm)")
        
        return fov_width_deg, fov_height_deg
    
    def _build_command_string(self, image_path: str, ra_rad: float, dec_rad: float,
                             fov_width_rad: float, fov_height_rad: float) -> str:
        """Build the command line string for PlateSolve 2."""
        
        # Format: ra,dec,width_field_of_view,height_field_of_view,number_of_regions_to_test,path_to_image,"0"
        cmd_parts = [
            str(ra_rad),           # RA in radians
            str(dec_rad),          # Dec in radians
            str(fov_width_rad),    # FOV width in radians
            str(fov_height_rad),   # FOV height in radians
            str(self.number_of_regions),  # Number of regions to test
            image_path,            # Path to image
            "0"                    # Fixed parameter
        ]
        
        return ",".join(cmd_parts)
    
    def _execute_platesolve2(self, cmd_string: str) -> bool:
        """Execute PlateSolve 2 with the command string."""
        try:
            # Build full command
            full_cmd = [self.executable_path, cmd_string]
            
            if self.verbose:
                self.logger.info(f"Executing: {' '.join(full_cmd)}")
            
            # Execute with timeout
            self.current_process = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_directory if self.working_directory else None
            )
            
            if self.verbose:
                if self.current_process.stdout:
                    self.logger.info(f"STDOUT: {self.current_process.stdout}")
                if self.current_process.stderr:
                    self.logger.warning(f"STDERR: {self.current_process.stderr}")
            
            # Check return code
            if self.current_process.returncode == 0:
                self.logger.info("PlateSolve 2 executed successfully")
                return True
            else:
                self.logger.error(f"PlateSolve 2 failed with return code: {self.current_process.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("PlateSolve 2 execution timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error executing PlateSolve 2: {e}")
            return False
    
    def _parse_apm_file(self, apm_path: str, result: dict[str, Any], image_path: str) -> dict[str, Any]:
        """Parses the .apm result file from PlateSolve 2."""
        import math
        try:
            with open(apm_path, 'r') as f:
                lines = [line.strip() for line in f.readlines()]
            if len(lines) < 3:
                result['error_message'] = f".apm file has too few lines: {lines}"
                return result
            
            # Line 1: RA,Dec,Code_1 (all floats in radians, Code_1 is int)
            # Format is always: RA_part1,RA_part2,DEC_part1,DEC_part2,Code_1
            # So we have exactly 5 parts when split by comma
            
            line1 = lines[0]
            if self.verbose:
                self.logger.info(f"Parsing line 1: {line1}")
            
            # Split by comma - we expect exactly 5 parts
            parts = line1.split(',')
            if len(parts) != 5:
                result['error_message'] = f"Line 1 does not have exactly 5 parts: {line1} (found {len(parts)} parts)"
                return result
            
            # Combine parts: RA = parts[0] + "," + parts[1], Dec = parts[2] + "," + parts[3]
            ra_rad_str = parts[0] + "." + parts[1]
            dec_rad_str = parts[2] + "." + parts[3]
            code_1_str = parts[4]
            
            # Convert to appropriate types
            try:
                ra_rad = float(ra_rad_str)
                dec_rad = float(dec_rad_str)
                code_1 = int(code_1_str)
            except ValueError as e:
                result['error_message'] = f"Failed to convert values: RA='{ra_rad_str}', Dec='{dec_rad_str}', Code_1='{code_1_str}': {e}"
                return result
            
            # Convert to degrees
            ra_deg = ra_rad * 180.0 / math.pi
            dec_deg = dec_rad * 180.0 / math.pi
            result['ra_center'] = ra_deg
            result['dec_center'] = dec_deg
            
            # Calculate FOV from pixel scale and image dimensions
            # Get image dimensions from the input image
            try:
                from PIL import Image
                with Image.open(image_path) as img:
                    image_width, image_height = img.size
                    result['image_size'] = (image_width, image_height)
                    
                    # Calculate FOV from pixel scale
                    # pixel_scale is in arcseconds per pixel
                    # FOV = pixel_scale * image_size / 3600 (convert arcsec to degrees)
                    fov_width_deg = (pixel_scale * image_width) / 3600.0
                    fov_height_deg = (pixel_scale * image_height) / 3600.0
                    result['fov_width'] = fov_width_deg
                    result['fov_height'] = fov_height_deg
                    
                    if self.verbose:
                        self.logger.info(f"Image size: {image_width}x{image_height} pixels")
                        self.logger.info(f"Calculated FOV: {fov_width_deg:.4f}° x {fov_height_deg:.4f}°")
            except Exception as e:
                self.logger.warning(f"Could not determine image size: {e}")
                # Use default values or calculated FOV if available
                result['image_size'] = None
                result['fov_width'] = None
                result['fov_height'] = None
            
            if self.verbose:
                self.logger.info(f"Parsed RA: {ra_rad_str} rad = {ra_deg:.6f}°")
                self.logger.info(f"Parsed Dec: {dec_rad_str} rad = {dec_deg:.6f}°")
                self.logger.info(f"Parsed Code_1: {code_1}")
            
            # Line 2: Pixel_scale,Position_angle,If_Flipped,Code_2,Code_3,N_stars
            # Format: pixel_scale_part1,pixel_scale_part2,position_angle_part1,position_angle_part2,If_Flipped,Code_2,Code_3_part1,Code_3_part2,N_stars
            # Example: 0,45138,146,64,-1,0002,0,00004,388
            # So we have exactly 9 parts when split by comma
            
            line2 = lines[1]
            if self.verbose:
                self.logger.info(f"Parsing line 2: {line2}")
            
            parts2 = line2.split(',')
            if len(parts2) != 9:
                result['error_message'] = f"Line 2 does not have exactly 9 parts: {line2} (found {len(parts2)} parts)"
                return result
            
            # Combine parts according to the format
            pixel_scale_str = parts2[0] + "." + parts2[1]  # 0.45138
            position_angle_str = parts2[2] + "." + parts2[3]  # 146.64
            if_flipped = int(parts2[4])  # -1
            code_2_str = parts2[5]  # 0002
            code_3_str = parts2[6] + "." + parts2[7]  # 0.00004
            n_stars_str = parts2[8]  # 388
            
            # Convert to appropriate types
            try:
                pixel_scale = float(pixel_scale_str)
                position_angle = float(position_angle_str)
                code_2 = int(code_2_str)
                code_3 = float(code_3_str)
                n_stars = int(n_stars_str)
            except ValueError as e:
                result['error_message'] = f"Failed to convert line 2 values: pixel_scale='{pixel_scale_str}', position_angle='{position_angle_str}', code_2='{code_2_str}', code_3='{code_3_str}', n_stars='{n_stars_str}': {e}"
                return result
            
            # If flipped, add 180°
            if if_flipped >= 1:
                position_angle = (position_angle + 180.0) % 360.0
                
            result['pixel_scale'] = pixel_scale
            result['position_angle'] = position_angle
            result['flipped'] = if_flipped
            result['stars_detected'] = n_stars
            
            if self.verbose:
                self.logger.info(f"Parsed pixel_scale: {pixel_scale_str} = {pixel_scale}")
                self.logger.info(f"Parsed position_angle: {position_angle_str} = {position_angle}")
                self.logger.info(f"Parsed if_flipped: {if_flipped}")
                self.logger.info(f"Parsed code_2: {code_2}")
                self.logger.info(f"Parsed code_3: {code_3_str} = {code_3}")
                self.logger.info(f"Parsed n_stars: {n_stars}")
            
            # Line 3: Valid plate solution?
            valid_line = lines[2]
            if 'Valid' in valid_line:
                result['success'] = True
                result['confidence'] = 0.99
            else:
                result['success'] = False
                result['error_message'] = f"PlateSolve 2 did not find a valid solution: {lines[2]}"
                
            return result
            
        except Exception as e:
            result['error_message'] = f"Error parsing .apm file: {str(e)}"
            if self.verbose:
                self.logger.error(f"APM parsing error: {e}")
                self.logger.error(f"APM file content: {lines if 'lines' in locals() else 'Could not read file'}")
            return result
    
    def _cleanup(self):
        """Clean up resources."""
        try:
            # self.current_process is a CompletedProcess object from subprocess.run()
            # It doesn't have poll() method since the process is already completed
            # No cleanup needed for completed processes
            pass
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        
        self.current_process = None 