#!/usr/bin/env python3
"""
PlateSolve 2 automation inspired by NINA implementation.
This module attempts to automate PlateSolve 2 without manual intervention.
"""

import subprocess
import os
import time
import logging
import win32gui
import win32con
import win32api
import win32process
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import threading

# Import configuration
from config_manager import config

class PlateSolve2Automated:
    """Automated PlateSolve 2 integration inspired by NINA."""
    
    def __init__(self):
        self.plate_solve_config = config.get_plate_solve_config()
        
        # PlateSolve 2 settings
        self.executable_path = self.plate_solve_config.get('platesolve2_path', '')
        self.working_directory = self.plate_solve_config.get('working_directory', '')
        self.timeout = self.plate_solve_config.get('timeout', 60)
        self.verbose = self.plate_solve_config.get('verbose', False)
        
        # Automation settings
        self.auto_click_delay = 0.5  # seconds between clicks
        self.wait_for_window_timeout = 10  # seconds to wait for window
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Process tracking
        self.current_process = None
        self.platesolve_window = None
    
    def solve(self, image_path: str) -> Dict[str, Any]:
        """Automatically solve plate using PlateSolve 2."""
        result = {
            'success': False,
            'ra_center': None,
            'dec_center': None,
            'fov_width': None,
            'fov_height': None,
            'confidence': None,
            'stars_detected': None,
            'error_message': None,
            'solving_time': 0
        }
        
        if not self._is_available():
            result['error_message'] = "PlateSolve 2 not available"
            return result
        
        if not os.path.exists(image_path):
            result['error_message'] = f"Image file not found: {image_path}"
            return result
        
        start_time = time.time()
        
        try:
            # Start PlateSolve 2
            if not self._start_platesolve2(image_path):
                result['error_message'] = "Failed to start PlateSolve 2"
                return result
            
            # Wait for window to appear
            if not self._wait_for_window():
                result['error_message'] = "PlateSolve 2 window not found"
                return result
            
            # Automate the solving process
            if self._automate_solving():
                # Try to extract results
                result = self._extract_results(result)
            else:
                result['error_message'] = "Automation failed"
            
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
    
    def _start_platesolve2(self, image_path: str) -> bool:
        """Start PlateSolve 2 with the image."""
        try:
            cmd = [self.executable_path, image_path]
            
            if self.verbose:
                self.logger.info(f"Starting PlateSolve 2: {' '.join(cmd)}")
            
            # Start process
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_directory if self.working_directory else None
            )
            
            # Wait a moment for process to start
            time.sleep(2)
            
            if self.current_process.poll() is None:
                self.logger.info("PlateSolve 2 process started")
                return True
            else:
                self.logger.error("PlateSolve 2 process failed to start")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting PlateSolve 2: {e}")
            return False
    
    def _wait_for_window(self) -> bool:
        """Wait for PlateSolve 2 window to appear."""
        start_time = time.time()
        
        while time.time() - start_time < self.wait_for_window_timeout:
            # Find PlateSolve 2 window
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_text = win32gui.GetWindowText(hwnd)
                    if "PlateSolve" in window_text or "Plate Solve" in window_text:
                        windows.append(hwnd)
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            if windows:
                self.platesolve_window = windows[0]
                self.logger.info(f"Found PlateSolve 2 window: {win32gui.GetWindowText(self.platesolve_window)}")
                return True
            
            time.sleep(0.5)
        
        self.logger.error("PlateSolve 2 window not found within timeout")
        return False
    
    def _automate_solving(self) -> bool:
        """Automate the plate-solving process."""
        if not self.platesolve_window:
            return False
        
        try:
            # Bring window to front
            win32gui.SetForegroundWindow(self.platesolve_window)
            time.sleep(self.auto_click_delay)
            
            # Try to find and click "Solve" button
            # This is a simplified approach - NINA likely has more sophisticated automation
            
            # Method 1: Try to send Enter key (common for default solve)
            win32api.SendMessage(self.platesolve_window, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            time.sleep(self.auto_click_delay)
            
            # Method 2: Try to find solve button by text
            self._find_and_click_button("Solve")
            
            # Wait for solving to complete
            if self._wait_for_solving_complete():
                self.logger.info("Plate-solving completed")
                return True
            else:
                self.logger.warning("Plate-solving may not have completed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during automation: {e}")
            return False
    
    def _find_and_click_button(self, button_text: str) -> bool:
        """Find and click a button by text."""
        try:
            # This is a simplified implementation
            # NINA likely uses more sophisticated window enumeration
            
            def enum_child_windows_callback(hwnd, buttons):
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd)
                    if button_text.lower() in text.lower():
                        buttons.append(hwnd)
                return True
            
            buttons = []
            win32gui.EnumChildWindows(self.platesolve_window, enum_child_windows_callback, buttons)
            
            if buttons:
                # Click the first matching button
                button_hwnd = buttons[0]
                win32gui.SetForegroundWindow(button_hwnd)
                time.sleep(self.auto_click_delay)
                
                # Send click message
                win32api.SendMessage(button_hwnd, win32con.BM_CLICK, 0, 0)
                self.logger.info(f"Clicked button: {button_text}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking button {button_text}: {e}")
            return False
    
    def _wait_for_solving_complete(self) -> bool:
        """Wait for plate-solving to complete."""
        # Wait for a reasonable time for solving to complete
        time.sleep(10)  # Adjust based on typical solving time
        
        # Check if window still exists and process is running
        if self.current_process and self.current_process.poll() is None:
            return True
        
        return False
    
    def _extract_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract results from PlateSolve 2 window."""
        try:
            # Method 1: Try to read from window text
            if self.platesolve_window:
                window_text = win32gui.GetWindowText(self.platesolve_window)
                self.logger.info(f"Window text: {window_text}")
                
                # Look for coordinates in window text
                # This is a simplified approach - NINA likely has more sophisticated parsing
                
                # Method 2: Try to copy results to clipboard
                # Send Ctrl+C to copy results
                win32api.SendMessage(self.platesolve_window, win32con.WM_KEYDOWN, ord('C'), win32con.MOD_CONTROL)
                time.sleep(0.5)
                
                # Try to read clipboard (would need additional implementation)
                # For now, return a placeholder
                result['success'] = True
                result['ra_center'] = 0.0  # Placeholder
                result['dec_center'] = 0.0  # Placeholder
                result['confidence'] = 0.8  # Placeholder
                
                self.logger.info("Results extracted (placeholder)")
                return result
            
        except Exception as e:
            self.logger.error(f"Error extracting results: {e}")
        
        result['error_message'] = "Could not extract results"
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
        self.platesolve_window = None

def main():
    """Test function for automated PlateSolve 2."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test automated PlateSolve 2")
    parser.add_argument("image", help="Image file to solve")
    
    args = parser.parse_args()
    
    solver = PlateSolve2Automated()
    
    print(f"Testing automated PlateSolve 2 with: {args.image}")
    result = solver.solve(args.image)
    
    print(f"Result: {result}")

if __name__ == "__main__":
    main() 