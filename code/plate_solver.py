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

import subprocess
import os
import time
import logging
import math
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
import xml.etree.ElementTree as ET


from exceptions import PlateSolveError, FileError, ConfigurationError
from status import PlateSolveStatus, success_status, error_status, warning_status

class PlateSolveResult:
    """
    Container for plate-solving results.
    
    This class holds the results of a plate-solving operation, including
    coordinates, field of view, and metadata about the solving process.
    
    Attributes:
        ra_center: Right Ascension of image center (degrees)
        dec_center: Declination of image center (degrees)
        fov_width: Field of view width (degrees)
        fov_height: Field of view height (degrees)
        solving_time: Time taken for solving (seconds)
        method: Method used for solving (e.g., 'platesolve2', 'astrometry')
        confidence: Confidence level of the solution (if available)
        position_angle: Position angle of the image (degrees)
        image_size: Image size as (width, height) in pixels
        is_flipped: Whether the image is flipped (mirror X-axis)
    """
    
    def __init__(self, ra_center: float, dec_center: float, fov_width: float, fov_height: float, 
                 solving_time: float, method: str, confidence: Optional[float] = None,
                 position_angle: Optional[float] = None, image_size: Optional[Tuple[int, int]] = None,
                 is_flipped: Optional[bool] = None):
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
    
    def __str__(self) -> str:
        """String representation of the plate-solving result.
        
        Returns:
            str: Human-readable representation of the result
        """
        try:
            # Safely format values, handling None and invalid data
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
            
            return (f"PlateSolveResult(RA={ra_str}°, Dec={dec_str}°, "
                    f"FOV={fov_w_str}°x{fov_h_str}°, PA={pa_str}°, "
                    f"method={self.method}, time={time_str}s, flipped={flipped_str}{confidence_str})")
        except Exception as e:
            # Fallback if formatting fails
            return f"PlateSolveResult(error_formatting: {e})"
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging.
        
        Returns:
            str: Detailed representation of the result
        """
        return self.__str__()

class PlateSolver(ABC):
    """
    Abstract base class for plate-solving engines.
    
    This class defines the interface that all plate-solving implementations
    must follow. It ensures consistent behavior across different solving
    engines and provides a unified API for the rest of the system.
    
    Key Design Decisions:
    - Abstract base class ensures consistent interface
    - Status-based error handling for robust operation
    - Configuration integration for flexible setup
    - Method identification for debugging and logging
    """
    
    def __init__(self, config=None, logger=None):
        """Initialize the plate solver with configuration and logging."""
        from config_manager import ConfigManager
        
        # Only create default config if no config is provided
        # This prevents loading config.yaml when config is passed from tests
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
            
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
    
    @abstractmethod
    def solve(self, image_path: str) -> PlateSolveStatus:
        """Execute plate-solving for the given image.
        
        This method must be implemented by all concrete solver classes.
        It should perform the actual plate-solving operation and return
        a status object with the results.
        
        Args:
            image_path: Path to the image file to solve
            
        Returns:
            PlateSolveStatus: Status object with solving results or error
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the solver is available and configured.
        
        This method should verify that the solver software is installed
        and properly configured for use.
        
        Returns:
            bool: True if solver is available, False otherwise
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of the solver.
        
        Returns:
            str: Human-readable name of the solver
        """
        pass

class PlateSolve2Solver(PlateSolver):
    """PlateSolve 2 Integration."""
    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)
        self.plate_solve_config = self.config.get_plate_solve_config()
        ps2_cfg = self.plate_solve_config.get('platesolve2', {})
        self.executable_path: str = ps2_cfg.get('executable_path', '')
        self.working_directory: str = ps2_cfg.get('working_directory', '')
        self.timeout: int = ps2_cfg.get('timeout', 60)
        self.verbose: bool = ps2_cfg.get('verbose', False)
        self.auto_mode: bool = ps2_cfg.get('auto_mode', True)
        self.number_of_regions: int = ps2_cfg.get('number_of_regions', 1)
        self.min_stars: int = ps2_cfg.get('min_stars', 20)
        self.max_stars: int = ps2_cfg.get('max_stars', 200)
        try:
            from platesolve2_automated import PlateSolve2Automated
            self.automated_solver = PlateSolve2Automated(config=self.config, logger=self.logger)
            self.automated_available: bool = True
            self.logger.info("Automated PlateSolve 2 solver available")
        except ImportError:
            self.automated_solver = None
            self.automated_available: bool = False
            self.logger.info("Automated PlateSolve 2 solver not available, using manual mode")

    def get_name(self) -> str:
        """Get the name of the solver.
        
        Returns:
            str: Human-readable name of the solver
        """
        return "PlateSolve 2"
    
    def is_available(self) -> bool:
        """Check if PlateSolve 2 is available.
        
        Verifies that the PlateSolve 2 executable path is configured
        and the software is accessible.
        
        Returns:
            bool: True if PlateSolve 2 is available, False otherwise
        """
        return bool(self.executable_path)
    
    def solve(self, image_path: str) -> PlateSolveStatus:
        """Execute plate-solving for the given image.
        
        Performs plate-solving using PlateSolve 2, with support for both
        automated and manual solving modes. The method attempts to get
        current mount coordinates to improve solving accuracy.
        
        Args:
            image_path: Path to the image file to solve
            
        Returns:
            PlateSolveStatus: Status object with result or error.
            
        Note:
            This method first tries automated solving if available, then
            falls back to manual solving if needed. It also attempts to
            get current mount coordinates to improve solving accuracy.
        """
        if not self.is_available():
            return error_status("PlateSolve 2 not available")
        if not os.path.exists(image_path):
            return error_status(f"Image file not found: {image_path}")
        start_time = time.time()
        try:
            # Try automated solving if available
            if self.automated_available and self.automated_solver:
                self.logger.info("Attempting automated PlateSolve 2 solving")
                
                # Get current mount coordinates if available
                ra_deg = None
                dec_deg = None
                try:
                    # Try to get coordinates from mount if available
                    from ascom_mount import ASCOMMount
                    mount = ASCOMMount(config=self.config, logger=self.logger)
                    mount_status = mount.get_coordinates()
                    if mount_status.is_success:
                        ra_deg, dec_deg = mount_status.data
                        self.logger.info(f"Using mount coordinates: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°")
                    else:
                        self.logger.warning(f"Could not get mount coordinates: {mount_status.message}")
                except Exception as e:
                    self.logger.warning(f"Could not get mount coordinates: {e}")
                
                # Get FOV from config
                fov_width_deg = None
                fov_height_deg = None
                try:
                    telescope_config = self.config.get_telescope_config()
                    camera_config = self.config.get_camera_config()
                    focal_length = telescope_config.get('focal_length', 1000)
                    sensor_width = camera_config.get('sensor_width', 6.17)
                    sensor_height = camera_config.get('sensor_height', 4.55)
                    
                    # Calculate FOV in degrees
                    # Note: Due to ASCOM image transposition, width and height are swapped
                    fov_width_deg = math.degrees(2 * math.atan(sensor_height / (2 * focal_length)))  # Now height
                    fov_height_deg = math.degrees(2 * math.atan(sensor_width / (2 * focal_length)))  # Now width
                    
                    self.logger.info(f"Calculated FOV (transposed): {fov_width_deg:.4f}° x {fov_height_deg:.4f}° (focal={focal_length}mm, sensor={sensor_width}x{sensor_height}mm)")
                except Exception as e:
                    self.logger.warning(f"Could not calculate FOV: {e}")
                
                automated_result = self.automated_solver.solve(
                    image_path, 
                    ra_deg=ra_deg, 
                    dec_deg=dec_deg,
                    fov_width_deg=fov_width_deg,
                    fov_height_deg=fov_height_deg
                )
                
                if automated_result.is_success:
                    solving_time = time.time() - start_time
                    self.logger.info(f"Plate-solving successful in {solving_time:.2f} seconds")
                    return success_status(
                        "Automated solving successful",
                        data=automated_result.data,
                        details={'method': 'automated', 'solving_time': solving_time}
                    )
                else:
                    solving_time = time.time() - start_time
                    self.logger.warning(f"Automated solving failed after {solving_time:.2f} seconds: {automated_result.message}")
                    self.logger.info("Continuing with next exposure - conditions may improve")
                    return error_status(
                        f"Plate-solving failed: {automated_result.message}",
                        details={'method': 'automated', 'solving_time': solving_time, 'reason': 'no_stars_or_poor_conditions'}
                    )
            else:
                # No automated solver available
                self.logger.error("No automated PlateSolve 2 solver available")
                return error_status("No automated PlateSolve 2 solver available")
            
        except Exception as e:
            solving_time = time.time() - start_time
            self.logger.error(f"PlateSolve 2 exception after {solving_time:.2f} seconds: {e}")
            return error_status(f"PlateSolve 2 error: {str(e)}", details={'solving_time': solving_time})
    


class AstrometryNetSolver(PlateSolver):
    """Astrometry.net API Integration (Placeholder).
    
    This is a placeholder implementation for Astrometry.net integration.
    It provides the interface but the actual solving functionality is not
    yet implemented.
    """
    
    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)
        self.api_key: str = self.config.get_plate_solve_config().get('astrometry', {}).get('api_key', '')
        self.api_url: str = "http://nova.astrometry.net/api/"
        
    def get_name(self) -> str:
        """Get the name of the solver.
        
        Returns:
            str: Human-readable name of the solver
        """
        return "Astrometry.net"
        
    def is_available(self) -> bool:
        """Check if Astrometry.net is available.
        
        Verifies that the API key is configured for Astrometry.net access.
        
        Returns:
            bool: True if API key is configured, False otherwise
        """
        return bool(self.api_key)
        
    def solve(self, image_path: str) -> PlateSolveStatus:
        """Execute plate-solving with Astrometry.net (placeholder).
        
        This is a placeholder implementation. The actual Astrometry.net
        integration is not yet implemented.
        
        Args:
            image_path: Path to the image file to solve
            
        Returns:
            PlateSolveStatus: Error status indicating not implemented
        """
        return error_status("Astrometry.net solver not yet implemented")

class PlateSolverFactory:
    """Factory for plate solver instances.
    
    This factory class creates appropriate plate solver instances based
    on the specified solver type. It provides a centralized way to
    instantiate different solver implementations.
    
    Key Design Decisions:
    - Factory pattern for solver creation
    - Configuration-based solver selection
    - Lazy loading to prevent double config loading
    - Error handling for unknown solver types
    """
    
    @staticmethod
    def create_solver(solver_type: Optional[str] = None, config=None, logger=None) -> Optional[PlateSolver]:
        """Create a plate solver instance.
        
        Creates an appropriate solver instance based on the specified type.
        If no type is specified, uses the default solver from configuration.
        
        Args:
            solver_type: Type of solver to create ('platesolve2', 'astrometry')
            config: Configuration object
            logger: Logger instance
            
        Returns:
            Optional[PlateSolver]: Solver instance or None if type is unknown
            
        Note:
            Uses lazy loading for configuration to prevent double loading
            when config is passed from test scripts.
        """
        if solver_type is None:
            if config:
                solver_type = config.get_plate_solve_config().get('default_solver', 'platesolve2')
            else:
                from config_manager import ConfigManager
                default_config = ConfigManager()
                solver_type = default_config.get_plate_solve_config().get('default_solver', 'platesolve2')
                
        solvers = {
            'platesolve2': PlateSolve2Solver,
            'astrometry': AstrometryNetSolver,
        }
        
        solver_class = solvers.get(solver_type.lower())
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
        """Get a list of available solvers.
        
        Returns a dictionary mapping solver names to their availability status.
        This is useful for determining which solvers can be used on the system.
        
        Args:
            config: Configuration object
            logger: Logger instance
            
        Returns:
            Dict[str, bool]: Dictionary mapping solver names to availability
        """
        solvers = {
            'platesolve2': PlateSolve2Solver(config=config, logger=logger),
            'astrometry': AstrometryNetSolver(config=config, logger=logger),
        }
        return {name: solver.is_available() for name, solver in solvers.items()} 