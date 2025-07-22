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

# Import configuration
from config_manager import config

class PlateSolve2Automated:
    """Automated PlateSolve 2 integration with correct command line format."""
    
    def __init__(self):
        self.plate_solve_config = config.get_plate_solve_config()
        
        # PlateSolve 2 settings
        self.executable_path = self.plate_solve_config.get('platesolve2_path', '')
        self.working_directory = self.plate_solve_config.get('working_directory', '')
        self.timeout = self.plate_solve_config.get('timeout', 60)
        self.verbose = self.plate_solve_config.get('verbose', False)
        
        # Plate-solving parameters
        self.number_of_regions = self.plate_solve_config.get('number_of_regions', 1)
        self.search_radius = self.plate_solve_config.get('search_radius', 15)  # degrees
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Process tracking
        self.current_process = None
    
    def solve(self, image_path: str, ra_deg: Optional[float] = None, 
              dec_deg: Optional[float] = None, fov_width_deg: Optional[float] = None, 
              fov_height_deg: Optional[float] = None) -> Dict[str, Any]:
        """
        Solve plate using PlateSolve 2 with correct command line format.
        Now parses the .apm result file for output.
        """
        result = {
            'success': False,
            'ra_center': None,
            'dec_center': None,
            'fov_width': None,
            'fov_height': None,
            'confidence': None,
            'stars_detected': None,
            'pixel_scale': None,
            'position_angle': None,
            'flipped': None,
            'error_message': None,
            'solving_time': 0,
            'method_used': 'platesolve2_automated_apm'
        }
        
        if not self._is_available():
            result['error_message'] = "PlateSolve 2 not available"
            return result
        
        if not os.path.exists(image_path):
            result['error_message'] = f"Image file not found: {image_path}"
            return result
        
        start_time = time.time()
        apm_path = os.path.splitext(image_path)[0] + '.apm'
        
        try:
            # Remove old .apm file if it exists
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
                result['error_message'] = f"No .apm result file found after {apm_timeout}s"
                return result
            
            # Parse .apm file
            result = self._parse_apm_file(apm_path, result)
            
        except Exception as e:
            result['error_message'] = f"Automation error: {str(e)}"
            self.logger.error(f"PlateSolve 2 automation error: {e}")
        finally:
            result['solving_time'] = time.time() - start_time
            self._cleanup()
        
        return result
    
    def _is_available(self) -> bool:
        """Check if PlateSolve 2 is available."""
        if not self.executable_path:
            self.logger.warning("PlateSolve 2 path not configured")
            return False
        
        executable = Path(self.executable_path)
        if not executable.exists():
            self.logger.warning(f"PlateSolve 2 executable not found: {self.executable_path}")
            return False
        
        return True
    
    def _prepare_parameters(self, ra_deg: Optional[float], dec_deg: Optional[float],
                           fov_width_deg: Optional[float], fov_height_deg: Optional[float]) -> Tuple[float, float, float, float]:
        """Prepare parameters for PlateSolve 2 command."""
        
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
        telescope_config = config.get_telescope_config()
        camera_config = config.get_camera_config()
        video_config = config.get_video_config()
        
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
    
    def _parse_apm_file(self, apm_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the .apm result file from PlateSolve 2."""
        import math
        try:
            with open(apm_path, 'r') as f:
                lines = [line.strip() for line in f.readlines()]
            if len(lines) < 3:
                result['error_message'] = f".apm file has too few lines: {lines}"
                return result
            # Line 1: RA,Dec,Code_1 (all floats in radians, Code_1 is int)
            ra_rad, dec_rad, code_1 = lines[0].split(',')
            ra_rad = float(ra_rad)
            dec_rad = float(dec_rad)
            # Convert to degrees
            ra_deg = ra_rad * 180.0 / math.pi
            dec_deg = dec_rad * 180.0 / math.pi
            result['ra_center'] = ra_deg
            result['dec_center'] = dec_deg
            # Line 2: Pixel_scale,Position_angle,If_Flipped,Code_2,Code_3,N_stars
            parts2 = lines[1].split(',')
            pixel_scale = float(parts2[0])
            position_angle = float(parts2[1])
            if_flipped = int(parts2[2])
            n_stars = int(parts2[5])
            # If flipped, add 180°
            if if_flipped >= 1:
                position_angle = (position_angle + 180.0) % 360.0
            result['pixel_scale'] = pixel_scale
            result['position_angle'] = position_angle
            result['flipped'] = if_flipped
            result['stars_detected'] = n_stars
            # Line 3: Valid plate solution?
            valid_line = lines[2].lower()
            if 'valid' in valid_line:
                result['success'] = True
                result['confidence'] = 0.99
            else:
                result['success'] = False
                result['error_message'] = f"PlateSolve 2 did not find a valid solution: {lines[2]}"
            return result
        except Exception as e:
            result['error_message'] = f"Error parsing .apm file: {str(e)}"
            return result
    
    def _cleanup(self):
        """Clean up resources."""
        try:
            if self.current_process and self.current_process.poll() is None:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        
        self.current_process = None

def main():
    """Test function for automated PlateSolve 2."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test automated PlateSolve 2")
    parser.add_argument("image", help="Image file to solve")
    parser.add_argument("--ra", type=float, help="Right Ascension in degrees")
    parser.add_argument("--dec", type=float, help="Declination in degrees")
    parser.add_argument("--fov-width", type=float, help="Field of view width in degrees")
    parser.add_argument("--fov-height", type=float, help="Field of view height in degrees")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    solver = PlateSolve2Automated()
    if args.verbose:
        solver.verbose = True
    
    print(f"Testing automated PlateSolve 2 with: {args.image}")
    result = solver.solve(
        args.image, 
        ra_deg=args.ra, 
        dec_deg=args.dec,
        fov_width_deg=args.fov_width,
        fov_height_deg=args.fov_height
    )
    
    print(f"Result: {result}")

if __name__ == "__main__":
    main() 