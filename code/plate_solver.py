#!/usr/bin/env python3
"""
Plate solving module for telescope streaming system.
Provides abstract interface for different plate-solving engines.
"""

import subprocess
import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import xml.etree.ElementTree as ET

# Import configuration
from config_manager import config

class PlateSolveResult:
    """Container for plate-solving results."""
    
    def __init__(self, success: bool = False):
        self.success = success
        self.ra_center = None  # degrees
        self.dec_center = None  # degrees
        self.fov_width = None  # degrees
        self.fov_height = None  # degrees
        self.confidence = None  # 0-1
        self.stars_detected = None
        self.solving_time = None  # seconds
        self.error_message = None
        self.solver_used = None
    
    def __str__(self) -> str:
        if self.success:
            return (f"PlateSolveResult(success=True, "
                   f"RA={self.ra_center:.4f}°, Dec={self.dec_center:.4f}°, "
                   f"FOV={self.fov_width:.3f}°x{self.fov_height:.3f}°, "
                   f"confidence={self.confidence:.2f}, stars={self.stars_detected})")
        else:
            return f"PlateSolveResult(success=False, error='{self.error_message}')"

class PlateSolver(ABC):
    """Abstract base class for plate-solving engines."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def solve(self, image_path: str) -> PlateSolveResult:
        """Solve plate for the given image file."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the solver is available and properly configured."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this solver."""
        pass

class PlateSolve2Solver(PlateSolver):
    """PlateSolve 2 integration."""
    
    def __init__(self):
        super().__init__()
        self.plate_solve_config = config.get_plate_solve_config()
        
        # PlateSolve 2 settings
        self.executable_path = self.plate_solve_config.get('platesolve2_path', '')
        self.working_directory = self.plate_solve_config.get('working_directory', '')
        self.timeout = self.plate_solve_config.get('timeout', 60)
        self.verbose = self.plate_solve_config.get('verbose', False)
        
        # Default search settings
        self.search_radius = self.plate_solve_config.get('search_radius', 15)  # degrees
        self.min_stars = self.plate_solve_config.get('min_stars', 20)
        self.max_stars = self.plate_solve_config.get('max_stars', 200)
        
        # Results file
        self.results_file = None
        
        # GUI mode flag
        self.use_gui_mode = self.plate_solve_config.get('use_gui_mode', True)
    
    def get_name(self) -> str:
        return "PlateSolve 2"
    
    def is_available(self) -> bool:
        """Check if PlateSolve 2 is available."""
        if not self.executable_path:
            self.logger.warning("PlateSolve 2 path not configured")
            return False
        
        executable = Path(self.executable_path)
        if not executable.exists():
            self.logger.warning(f"PlateSolve 2 executable not found: {self.executable_path}")
            return False
        
        # PlateSolve 2 is a GUI application, so we can't test it with --help
        # Just check if the executable exists and is accessible
        try:
            # Try to start the process without arguments to see if it's runnable
            result = subprocess.run(
                [str(executable)],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Even if it fails, the executable is available if it exists
            return True
        except Exception as e:
            self.logger.warning(f"PlateSolve 2 test failed: {e}")
            return False
    
    def solve(self, image_path: str) -> PlateSolveResult:
        """Solve plate using PlateSolve 2."""
        result = PlateSolveResult()
        result.solver_used = self.get_name()
        
        if not self.is_available():
            result.error_message = "PlateSolve 2 not available"
            return result
        
        if not os.path.exists(image_path):
            result.error_message = f"Image file not found: {image_path}"
            return result
        
        start_time = time.time()
        
        try:
            if self.use_gui_mode:
                result = self._solve_with_gui(image_path, result)
            else:
                result = self._solve_with_cli(image_path, result)
            
            result.solving_time = time.time() - start_time
            
        except Exception as e:
            result.error_message = f"PlateSolve 2 error: {str(e)}"
            self.logger.error(f"PlateSolve 2 exception: {e}")
        
        return result
    
    def _solve_with_gui(self, image_path: str, result: PlateSolveResult) -> PlateSolveResult:
        """Solve using PlateSolve 2 GUI mode."""
        try:
            # Open PlateSolve 2 with the image file
            cmd = [self.executable_path, image_path]
            
            if self.verbose:
                self.logger.info(f"Opening PlateSolve 2 GUI: {' '.join(cmd)}")
            
            # Start PlateSolve 2 GUI
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for the process to start
            time.sleep(2)
            
            # Check if process is running
            if process.poll() is None:
                self.logger.info("PlateSolve 2 GUI opened successfully")
                self.logger.info("Please solve the image manually in PlateSolve 2")
                self.logger.info("You can save results or copy coordinates from the GUI")
                
                # For now, return a result indicating GUI is open
                result.error_message = "PlateSolve 2 GUI opened - manual solving required"
                result.success = False
                
                # TODO: In the future, we could:
                # 1. Monitor for result files created by PlateSolve 2
                # 2. Use Windows API to read GUI content
                # 3. Implement clipboard monitoring for copied coordinates
                
            else:
                # Process finished (possibly an error)
                stdout, stderr = process.communicate()
                if stderr:
                    result.error_message = f"PlateSolve 2 error: {stderr.strip()}"
                else:
                    result.error_message = "PlateSolve 2 process finished unexpectedly"
                self.logger.error(f"PlateSolve 2 process error: {result.error_message}")
            
            return result
            
        except Exception as e:
            result.error_message = f"GUI mode error: {str(e)}"
            return result
    
    def _solve_with_cli(self, image_path: str, result: PlateSolveResult) -> PlateSolveResult:
        """Solve using PlateSolve 2 command line mode."""
        try:
            # Build command for PlateSolve 2
            # Based on successful test: PlateSolve2.exe image_path
            cmd = [
                self.executable_path,
                image_path  # Direct image path as first argument
            ]
            
            if self.verbose:
                self.logger.info(f"PlateSolve 2 CLI command: {' '.join(cmd)}")
            
            # Set working directory
            cwd = self.working_directory if self.working_directory else None
            
            self.logger.info(f"Running PlateSolve 2 CLI: {' '.join(cmd)}")
            
            # Execute PlateSolve 2 - this will open the GUI
            # We use Popen instead of run because it's a GUI application
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )
            
            # Wait for the process to start and GUI to open
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                self.logger.info("PlateSolve 2 GUI opened successfully")
                result.error_message = "PlateSolve 2 GUI opened - manual intervention required"
                result.success = False
            else:
                # Process finished (possibly an error)
                stdout, stderr = process.communicate()
                if stderr:
                    result.error_message = f"PlateSolve 2 error: {stderr.strip()}"
                else:
                    result.error_message = "PlateSolve 2 process finished unexpectedly"
                self.logger.error(f"PlateSolve 2 process error: {result.error_message}")
            
        except subprocess.TimeoutExpired:
            result.error_message = f"PlateSolve 2 CLI timeout after {self.timeout} seconds"
            self.logger.error("PlateSolve 2 CLI timeout")
        except Exception as e:
            result.error_message = f"PlateSolve 2 CLI error: {str(e)}"
            self.logger.error(f"PlateSolve 2 CLI exception: {e}")
        
        return result
    
    def _parse_results(self, results_path: Path, result: PlateSolveResult) -> PlateSolveResult:
        """Parse PlateSolve 2 results file."""
        try:
            if not results_path.exists():
                result.error_message = f"Results file not found: {results_path}"
                return result
            
            with open(results_path, 'r') as f:
                content = f.read()
            
            # Parse the results (format depends on PlateSolve 2 version)
            # This is a basic parser - may need adjustment for specific versions
            
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Try to parse key-value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    try:
                        if key in ['ra', 'right_ascension']:
                            result.ra_center = float(value)
                        elif key in ['dec', 'declination']:
                            result.dec_center = float(value)
                        elif key in ['fov_width', 'width']:
                            result.fov_width = float(value)
                        elif key in ['fov_height', 'height']:
                            result.fov_height = float(value)
                        elif key in ['confidence', 'conf']:
                            result.confidence = float(value)
                        elif key in ['stars', 'stars_detected']:
                            result.stars_detected = int(value)
                    except (ValueError, TypeError):
                        continue
            
            # Check if we got the essential data
            if (result.ra_center is not None and 
                result.dec_center is not None and
                result.fov_width is not None and
                result.fov_height is not None):
                
                result.success = True
                self.logger.info(f"Plate-solving successful: RA={result.ra_center:.4f}°, "
                               f"Dec={result.dec_center:.4f}°, FOV={result.fov_width:.3f}°x{result.fov_height:.3f}°")
            else:
                result.error_message = "Incomplete results from PlateSolve 2"
                self.logger.warning("Incomplete PlateSolve 2 results")
            
        except Exception as e:
            result.error_message = f"Error parsing results: {str(e)}"
            self.logger.error(f"Results parsing error: {e}")
        
        return result

class AstrometryNetSolver(PlateSolver):
    """Astrometry.net API integration (placeholder for future implementation)."""
    
    def __init__(self):
        super().__init__()
        self.api_key = config.get_plate_solve_config().get('astrometry_api_key', '')
        self.api_url = "http://nova.astrometry.net/api/"
    
    def get_name(self) -> str:
        return "Astrometry.net"
    
    def is_available(self) -> bool:
        """Check if Astrometry.net is available."""
        return bool(self.api_key)
    
    def solve(self, image_path: str) -> PlateSolveResult:
        """Solve plate using Astrometry.net API (placeholder)."""
        result = PlateSolveResult()
        result.solver_used = self.get_name()
        result.error_message = "Astrometry.net solver not yet implemented"
        return result

class PlateSolverFactory:
    """Factory for creating plate solvers."""
    
    @staticmethod
    def create_solver(solver_type: str = None) -> Optional[PlateSolver]:
        """Create a plate solver instance."""
        if solver_type is None:
            solver_type = config.get_plate_solve_config().get('default_solver', 'platesolve2')
        
        solvers = {
            'platesolve2': PlateSolve2Solver,
            'astrometry': AstrometryNetSolver,
        }
        
        solver_class = solvers.get(solver_type.lower())
        if solver_class:
            return solver_class()
        else:
            logging.error(f"Unknown solver type: {solver_type}")
            return None
    
    @staticmethod
    def get_available_solvers() -> Dict[str, bool]:
        """Get list of available solvers."""
        solvers = {
            'platesolve2': PlateSolve2Solver(),
            'astrometry': AstrometryNetSolver(),
        }
        
        return {name: solver.is_available() for name, solver in solvers.items()}

def main():
    """Test function for plate solver."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test plate solver")
    parser.add_argument("image", help="Image file to solve")
    parser.add_argument("--solver", default="platesolve2", help="Solver to use")
    parser.add_argument("--list", action="store_true", help="List available solvers")
    
    args = parser.parse_args()
    
    if args.list:
        print("Available solvers:")
        available = PlateSolverFactory.get_available_solvers()
        for name, is_available in available.items():
            status = "✓" if is_available else "✗"
            print(f"  {status} {name}")
        return
    
    solver = PlateSolverFactory.create_solver(args.solver)
    if not solver:
        print(f"Failed to create solver: {args.solver}")
        return
    
    if not solver.is_available():
        print(f"Solver {args.solver} is not available")
        return
    
    print(f"Solving {args.image} with {solver.get_name()}...")
    result = solver.solve(args.image)
    
    print(f"Result: {result}")
    if result.success:
        print(f"  RA: {result.ra_center:.4f}°")
        print(f"  Dec: {result.dec_center:.4f}°")
        print(f"  FOV: {result.fov_width:.3f}° x {result.fov_height:.3f}°")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Stars detected: {result.stars_detected}")
        print(f"  Solving time: {result.solving_time:.1f}s")

if __name__ == "__main__":
    main() 