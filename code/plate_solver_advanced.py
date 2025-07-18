#!/usr/bin/env python3
"""
Advanced PlateSolve 2 automation with multiple approaches.
Inspired by NINA's implementation but adapted for our needs.
"""

import subprocess
import os
import time
import logging
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import threading
import glob

# Import configuration
from config_manager import config

class PlateSolve2Advanced:
    """Advanced PlateSolve 2 automation with multiple fallback methods."""
    
    def __init__(self):
        self.plate_solve_config = config.get_plate_solve_config()
        
        # PlateSolve 2 settings
        self.executable_path = self.plate_solve_config.get('platesolve2_path', '')
        self.working_directory = self.plate_solve_config.get('working_directory', '')
        self.timeout = self.plate_solve_config.get('timeout', 60)
        self.verbose = self.plate_solve_config.get('verbose', False)
        
        # Advanced settings
        self.auto_mode = self.plate_solve_config.get('auto_mode', True)
        self.silent_mode = self.plate_solve_config.get('silent_mode', True)
        self.result_file_pattern = self.plate_solve_config.get('result_file_pattern', '*.txt')
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Process tracking
        self.current_process = None
        self.result_files_before = set()
    
    def solve(self, image_path: str) -> Dict[str, Any]:
        """Solve plate using advanced PlateSolve 2 automation."""
        result = {
            'success': False,
            'ra_center': None,
            'dec_center': None,
            'fov_width': None,
            'fov_height': None,
            'confidence': None,
            'stars_detected': None,
            'error_message': None,
            'solving_time': 0,
            'method_used': None
        }
        
        if not self._is_available():
            result['error_message'] = "PlateSolve 2 not available"
            return result
        
        if not os.path.exists(image_path):
            result['error_message'] = f"Image file not found: {image_path}"
            return result
        
        start_time = time.time()
        
        try:
            # Method 1: Try command line automation
            result = self._try_command_line_automation(image_path, result)
            
            # Method 2: Try batch file approach
            if not result['success']:
                result = self._try_batch_file_approach(image_path, result)
            
            # Method 3: Try result file monitoring
            if not result['success']:
                result = self._try_result_file_monitoring(image_path, result)
            
            # Method 4: Try configuration file approach
            if not result['success']:
                result = self._try_config_file_approach(image_path, result)
            
        except Exception as e:
            result['error_message'] = f"Advanced automation error: {str(e)}"
            self.logger.error(f"PlateSolve 2 advanced automation error: {e}")
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
    
    def _try_command_line_automation(self, image_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Try command line automation with various parameters."""
        self.logger.info("Trying command line automation...")
        
        # Test different command line approaches
        command_variations = [
            # Basic command
            [self.executable_path, image_path],
            
            # With silent flag
            [self.executable_path, image_path, "/silent"],
            [self.executable_path, image_path, "-silent"],
            [self.executable_path, image_path, "--silent"],
            
            # With batch flag
            [self.executable_path, image_path, "/batch"],
            [self.executable_path, image_path, "-batch"],
            [self.executable_path, image_path, "--batch"],
            
            # With auto flag
            [self.executable_path, image_path, "/auto"],
            [self.executable_path, image_path, "-auto"],
            [self.executable_path, image_path, "--auto"],
            
            # With output file
            [self.executable_path, image_path, "/out", "result.txt"],
            [self.executable_path, image_path, "-out", "result.txt"],
            [self.executable_path, image_path, "--out", "result.txt"],
        ]
        
        for i, cmd in enumerate(command_variations):
            try:
                self.logger.info(f"Trying command variation {i+1}: {' '.join(cmd)}")
                
                # Record files before
                self.result_files_before = self._get_result_files()
                
                # Run command
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.working_directory if self.working_directory else None
                )
                
                # Check for new result files
                new_files = self._get_result_files() - self.result_files_before
                if new_files:
                    result_file = list(new_files)[0]
                    result = self._parse_result_file(result_file, result)
                    if result['success']:
                        result['method_used'] = f"command_line_variation_{i+1}"
                        return result
                
                # Check stdout/stderr for results
                if process.stdout:
                    result = self._parse_output(process.stdout, result)
                    if result['success']:
                        result['method_used'] = f"command_line_stdout_{i+1}"
                        return result
                
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Command variation {i+1} timed out")
            except Exception as e:
                self.logger.warning(f"Command variation {i+1} failed: {e}")
        
        result['error_message'] = "Command line automation failed"
        return result
    
    def _try_batch_file_approach(self, image_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Try using a batch file to automate PlateSolve 2."""
        self.logger.info("Trying batch file approach...")
        
        try:
            # Create a batch file with automation commands
            batch_content = f'''@echo off
cd /d "{self.working_directory}"
"{self.executable_path}" "{image_path}" /silent /batch
if exist result.txt (
    type result.txt
    del result.txt
)
'''
            
            batch_file = Path(self.working_directory) / "platesolve_auto.bat"
            with open(batch_file, 'w') as f:
                f.write(batch_content)
            
            # Run batch file
            process = subprocess.run(
                [str(batch_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_directory
            )
            
            # Parse output
            if process.stdout:
                result = self._parse_output(process.stdout, result)
                if result['success']:
                    result['method_used'] = "batch_file"
                    return result
            
            # Clean up
            if batch_file.exists():
                batch_file.unlink()
                
        except Exception as e:
            self.logger.warning(f"Batch file approach failed: {e}")
        
        result['error_message'] = "Batch file approach failed"
        return result
    
    def _try_result_file_monitoring(self, image_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Try monitoring for result files created by PlateSolve 2."""
        self.logger.info("Trying result file monitoring...")
        
        try:
            # Record existing files
            self.result_files_before = self._get_result_files()
            
            # Start PlateSolve 2
            cmd = [self.executable_path, image_path]
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_directory if self.working_directory else None
            )
            
            # Monitor for new files
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                new_files = self._get_result_files() - self.result_files_before
                if new_files:
                    result_file = list(new_files)[0]
                    result = self._parse_result_file(result_file, result)
                    if result['success']:
                        result['method_used'] = "result_file_monitoring"
                        return result
                
                time.sleep(1)
            
            # Check if process is still running
            if self.current_process.poll() is None:
                self.current_process.terminate()
                
        except Exception as e:
            self.logger.warning(f"Result file monitoring failed: {e}")
        
        result['error_message'] = "Result file monitoring failed"
        return result
    
    def _try_config_file_approach(self, image_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Try using a configuration file to automate PlateSolve 2."""
        self.logger.info("Trying configuration file approach...")
        
        try:
            # Create a configuration file
            config_content = f"""
[PlateSolve2]
ImageFile={image_path}
OutputFile=result.txt
AutoSolve=1
SilentMode=1
"""
            
            config_file = Path(self.working_directory) / "platesolve_config.ini"
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            # Run with config file
            cmd = [self.executable_path, "/config", str(config_file)]
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_directory
            )
            
            # Check for result file
            result_file = Path(self.working_directory) / "result.txt"
            if result_file.exists():
                result = self._parse_result_file(str(result_file), result)
                if result['success']:
                    result['method_used'] = "config_file"
                    return result
            
            # Clean up
            if config_file.exists():
                config_file.unlink()
            if result_file.exists():
                result_file.unlink()
                
        except Exception as e:
            self.logger.warning(f"Config file approach failed: {e}")
        
        result['error_message'] = "Config file approach failed"
        return result
    
    def _get_result_files(self) -> set:
        """Get current result files in working directory."""
        if not self.working_directory:
            return set()
        
        pattern = Path(self.working_directory) / self.result_file_pattern
        return set(glob.glob(str(pattern)))
    
    def _parse_result_file(self, result_file: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a result file from PlateSolve 2."""
        try:
            with open(result_file, 'r') as f:
                content = f.read()
            
            return self._parse_output(content, result)
            
        except Exception as e:
            self.logger.warning(f"Error parsing result file {result_file}: {e}")
            return result
    
    def _parse_output(self, output: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse output for coordinates and other results."""
        try:
            # Look for RA/Dec patterns
            ra_pattern = r'RA[:\s]*([0-9]+\.?[0-9]*)'
            dec_pattern = r'Dec[:\s]*([+-]?[0-9]+\.?[0-9]*)'
            
            ra_match = re.search(ra_pattern, output, re.IGNORECASE)
            dec_match = re.search(dec_pattern, output, re.IGNORECASE)
            
            if ra_match and dec_match:
                result['success'] = True
                result['ra_center'] = float(ra_match.group(1))
                result['dec_center'] = float(dec_match.group(1))
                result['confidence'] = 0.8  # Default confidence
                
                # Look for FOV information
                fov_pattern = r'FOV[:\s]*([0-9]+\.?[0-9]*)'
                fov_match = re.search(fov_pattern, output, re.IGNORECASE)
                if fov_match:
                    result['fov_width'] = float(fov_match.group(1))
                    result['fov_height'] = float(fov_match.group(1))
                
                self.logger.info(f"Parsed results: RA={result['ra_center']}, Dec={result['dec_center']}")
                return result
            
        except Exception as e:
            self.logger.warning(f"Error parsing output: {e}")
        
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
    """Test function for advanced PlateSolve 2 automation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test advanced PlateSolve 2 automation")
    parser.add_argument("image", help="Image file to solve")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    solver = PlateSolve2Advanced()
    if args.verbose:
        solver.verbose = True
    
    print(f"Testing advanced PlateSolve 2 automation with: {args.image}")
    result = solver.solve(args.image)
    
    print(f"Result: {result}")

if __name__ == "__main__":
    main() 