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


from exceptions import PlateSolveError, FileError
from status import PlateSolveStatus, success_status, error_status, warning_status

class PlateSolveResult:
    """Container für Plate-Solving-Ergebnisse."""
    def __init__(self, success: bool = False) -> None:
        self.success: bool = success
        self.ra_center: Optional[float] = None
        self.dec_center: Optional[float] = None
        self.fov_width: Optional[float] = None
        self.fov_height: Optional[float] = None
        self.position_angle: Optional[float] = None  # Position angle in degrees
        self.image_size: Optional[Tuple[int, int]] = None  # (width, height) in pixels
        self.confidence: Optional[float] = None
        self.stars_detected: Optional[int] = None
        self.solving_time: Optional[float] = None
        self.error_message: Optional[str] = None
        self.solver_used: Optional[str] = None
    def __str__(self) -> str:
        if self.success:
            return (f"PlateSolveResult(success=True, "
                   f"RA={self.ra_center:.4f}°, Dec={self.dec_center:.4f}°, "
                   f"FOV={self.fov_width:.3f}°x{self.fov_height:.3f}°, "
                   f"confidence={self.confidence:.2f}, stars={self.stars_detected})")
        else:
            return f"PlateSolveResult(success=False, error='{self.error_message}')"

class PlateSolver(ABC):
    """Abstrakte Basisklasse für Plate-Solving-Engines."""
    def __init__(self, config=None, logger=None):
        from config_manager import ConfigManager
        default_config = ConfigManager()
        import logging
        self.config = config or default_config
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    @abstractmethod
    def solve(self, image_path: str) -> PlateSolveStatus:
        """Plate-Solving für das gegebene Bild ausführen."""
        pass
    @abstractmethod
    def is_available(self) -> bool:
        """Prüft, ob der Solver verfügbar und konfiguriert ist."""
        pass
    @abstractmethod
    def get_name(self) -> str:
        """Gibt den Namen des Solvers zurück."""
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
            self.automated_solver = PlateSolve2Automated()
            self.automated_available: bool = True
            self.logger.info("Automated PlateSolve 2 solver available")
        except ImportError:
            self.automated_solver = None
            self.automated_available: bool = False
            self.logger.info("Automated PlateSolve 2 solver not available, using manual mode")
    def get_name(self) -> str:
        """Gibt den Namen des Solvers zurück."""
        return "PlateSolve 2"
    def is_available(self) -> bool:
        """Prüft, ob PlateSolve 2 verfügbar ist."""
        return bool(self.executable_path)
    def solve(self, image_path: str) -> PlateSolveStatus:
        """Führt Plate-Solving für das gegebene Bild aus.
        Returns:
            PlateSolveStatus: Status-Objekt mit Ergebnis oder Fehler.
        """
        if not self.is_available():
            return error_status("PlateSolve 2 not available")
        if not os.path.exists(image_path):
            return error_status(f"Image file not found: {image_path}")
        start_time = time.time()
        try:
            # Try automated solving first if available
            if self.automated_available and self.automated_solver:
                self.logger.info("Attempting automated PlateSolve 2 solving")
                automated_result = self.automated_solver.solve(image_path)
                if automated_result['success']:
                    return success_status(
                        "Automated solving successful",
                        data=automated_result,
                        details={'method': 'automated', 'solving_time': automated_result.get('solving_time')}
                    )
                else:
                    self.logger.warning(f"Automated solving failed: {automated_result['error_message']}")
                    self.logger.info("Falling back to GUI mode")
            
            # Fall back to GUI mode (CLI mode removed as it doesn't work)
            return self._solve_with_gui(image_path)
            
        except Exception as e:
            self.logger.error(f"PlateSolve 2 exception: {e}")
            return error_status(f"PlateSolve 2 error: {str(e)}")
    
    def _solve_with_gui(self, image_path: str) -> PlateSolveStatus:
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
                return warning_status(
                    "PlateSolve 2 GUI opened - manual solving required",
                    details={'method': 'gui'}
                )
                
            else:
                # Process finished (possibly an error)
                stdout, stderr = process.communicate()
                if stderr:
                    return error_status(f"PlateSolve 2 error: {stderr.strip()}")
                else:
                    return error_status("PlateSolve 2 process finished unexpectedly")
            
        except Exception as e:
            return error_status(f"GUI mode error: {str(e)}")
    


class AstrometryNetSolver(PlateSolver):
    """Astrometry.net API Integration (Platzhalter)."""
    def __init__(self, config=None, logger=None):
        super().__init__(config=config, logger=logger)
        self.api_key: str = self.config.get_plate_solve_config().get('astrometry', {}).get('api_key', '')
        self.api_url: str = "http://nova.astrometry.net/api/"
    def get_name(self) -> str:
        """Gibt den Namen des Solvers zurück."""
        return "Astrometry.net"
    def is_available(self) -> bool:
        """Prüft, ob Astrometry.net verfügbar ist."""
        return bool(self.api_key)
    def solve(self, image_path: str) -> PlateSolveStatus:
        """Führt Plate-Solving mit Astrometry.net aus (Platzhalter)."""
        result = PlateSolveResult()
        result.solver_used = self.get_name()
        result.error_message = "Astrometry.net solver not yet implemented"
        return error_status("Astrometry.net solver not yet implemented")

class PlateSolverFactory:
    """Factory für Plate-Solver-Instanzen."""
    @staticmethod
    def create_solver(solver_type: Optional[str] = None) -> Optional[PlateSolver]:
        """Erzeugt eine PlateSolver-Instanz."""
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
        """Gibt eine Liste verfügbarer Solver zurück."""
        solvers = {
            'platesolve2': PlateSolve2Solver(),
            'astrometry': AstrometryNetSolver(),
        }
        return {name: solver.is_available() for name, solver in solvers.items()} 