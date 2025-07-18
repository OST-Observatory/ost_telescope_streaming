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
        
        # Test if executable is runnable
        try:
            result = subprocess.run(
                [str(executable), "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
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
            # Create results filename
            image_path_obj = Path(image_path)
            results_filename = f"{image_path_obj.stem}_results.txt"
            results_path = image_path_obj.parent / results_filename
            
            # Build command
            cmd = [
                self.executable_path,
                "--image", image_path,
                "--results", str(results_path),
                "--search-radius", str(self.search_radius),
                "--min-stars", str(self.min_stars),
                "--max-stars", str(self.max_stars)
            ]
            
            if self.verbose:
                cmd.append("--verbose")
            
            # Set working directory
            cwd = self.working_directory if self.working_directory else None
            
            self.logger.info(f"Running PlateSolve 2: {' '.join(cmd)}")
            
            # Execute PlateSolve 2
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd
            )
            
            result.solving_time = time.time() - start_time
            
            if process.returncode == 0:
                # Parse results
                result = self._parse_results(results_path, result)
            else:
                result.error_message = f"PlateSolve 2 failed: {process.stderr.strip()}"
                self.logger.error(f"PlateSolve 2 error: {process.stderr}")
            
        except subprocess.TimeoutExpired:
            result.error_message = f"PlateSolve 2 timeout after {self.timeout} seconds"
            self.logger.error("PlateSolve 2 timeout")
        except Exception as e:
            result.error_message = f"PlateSolve 2 error: {str(e)}"
            self.logger.error(f"PlateSolve 2 exception: {e}")
        
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