#!/usr/bin/env python3
"""
Video processor module for telescope streaming system.
Coordinates video capture and plate-solving operations.
"""

import time
import threading
import logging
from typing import Optional, Callable, Dict, Any
from pathlib import Path
from datetime import datetime

# Import local modules
from video_capture import VideoCapture
from plate_solver import PlateSolverFactory, PlateSolveResult

from exceptions import VideoProcessingError, FileError
from status import VideoProcessingStatus, success_status, error_status, warning_status

class VideoProcessor:
    """Koordiniert Videoaufnahme und Plate-Solving-Operationen."""
    def __init__(self, config=None, logger=None) -> None:
        """Initialisiert den VideoProcessor."""
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
        self.video_capture: Optional[VideoCapture] = None
        self.plate_solver: Optional[object] = None
        self.is_running: bool = False
        self.processing_thread: Optional[threading.Thread] = None
        
        # Load configuration
        self.video_config: dict[str, Any] = self.config.get_video_config()
        self.plate_solve_config: dict[str, Any] = self.config.get_plate_solve_config()
        
        # Video processing settings
        self.video_enabled: bool = self.video_config.get('video_enabled', True)
        self.capture_interval: int = self.config.get_plate_solve_config().get('min_solve_interval', 60)
        self.save_frames: bool = self.video_config.get('save_plate_solve_frames', True)
        self.frame_dir: Path = Path(self.video_config.get('plate_solve_dir', 'plate_solve_frames'))
        
        # Timestamp settings for frame filenames
        self.use_timestamps: bool = self.video_config.get('use_timestamps', False)
        self.timestamp_format: str = self.video_config.get('timestamp_format', '%Y%m%d_%H%M%S')
        self.use_capture_count: bool = self.video_config.get('use_capture_count', True)
        self.file_format: str = self.video_config.get('file_format', 'png')
        
        # Plate-solving settings
        self.solver_type: str = self.plate_solve_config.get('default_solver', 'platesolve2')
        self.auto_solve: bool = self.plate_solve_config.get('auto_solve', True)
        self.min_solve_interval: int = self.plate_solve_config.get('min_solve_interval', 30)
        
        # State tracking
        self.last_capture_time: float = 0
        self.last_solve_time: float = 0
        self.last_solve_result: Optional[PlateSolveResult] = None
        self.capture_count: int = 0
        self.solve_count: int = 0
        self.successful_solves: int = 0
        
        # Callbacks
        self.on_solve_result: Optional[Callable[[PlateSolveResult], None]] = None
        self.on_capture_frame: Optional[Callable[[Any, Any], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # Setup logging
        # self.logger = logging.getLogger(__name__) # This line is now redundant as logger is passed to __init__
        
        # Ensure frame directory exists
        if self.save_frames:
            try:
                self.frame_dir.mkdir(exist_ok=True)
                self.logger.info(f"Frame directory: {self.frame_dir.absolute()}")
            except Exception as e:
                self.logger.error(f"Failed to create frame directory: {e}")
                # Fallback to current directory
                self.frame_dir = Path(".")
                self.logger.warning(f"Using current directory for frame storage: {self.frame_dir.absolute()}")
    
    def initialize(self) -> bool:
        """Initialisiert Videoaufnahme und Plate-Solver.
        Returns:
            bool: True, wenn erfolgreich initialisiert, sonst False.
        """
        success = True
        
        # Initialize video capture
        if self.video_enabled:
            try:
                self.video_capture = VideoCapture(config=self.config, logger=self.logger)
                if self.video_capture.connect():
                    self.logger.info("Video capture initialized")
                else:
                    self.logger.error("Failed to connect to video camera")
                    success = False
            except Exception as e:
                self.logger.error(f"Error initializing video capture: {e}")
                success = False
        
        # Initialize plate solver
        if self.auto_solve:
            try:
                self.plate_solver = PlateSolverFactory.create_solver(self.solver_type, config=self.config, logger=self.logger)
                if self.plate_solver and self.plate_solver.is_available():
                    self.logger.info(f"Plate solver initialized: {self.plate_solver.get_name()}")
                else:
                    self.logger.warning(f"Plate solver not available: {self.solver_type}")
                    self.plate_solver = None
            except Exception as e:
                self.logger.error(f"Error initializing plate solver: {e}")
                self.plate_solver = None
        
        return success
    
    def start(self) -> VideoProcessingStatus:
        """Startet die Videoverarbeitung.
        Returns:
            VideoProcessingStatus: Status-Objekt mit Startinformation oder Fehler.
        """
        if not self.initialize():
            return error_status("Initialization failed", details={'video_enabled': self.video_enabled})
        if not self.video_capture:
            self.logger.error("Video capture not available")
            return error_status("Video capture not available", details={'video_enabled': self.video_enabled})
        capture_status = self.video_capture.start_capture()
        if not capture_status.is_success:
            self.logger.error("Failed to start video capture")
            return error_status("Failed to start video capture", details={'video_enabled': self.video_enabled})
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        self.logger.info("Video processor started")
        return success_status("Video processor started", details={'video_enabled': self.video_enabled, 'is_running': True})
    
    def stop(self) -> VideoProcessingStatus:
        """Stoppt die Videoverarbeitung.
        Returns:
            VideoProcessingStatus: Status-Objekt mit Stopinformation.
        """
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        if self.video_capture:
            self.video_capture.stop_capture()
            self.video_capture.disconnect()
        self.logger.info("Video processor stopped")
        return success_status("Video processor stopped", details={'is_running': False})
    
    def _processing_loop(self) -> None:
        """Hauptverarbeitungsschleife."""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Check if it's time for a new capture/solve cycle
                if current_time - self.last_capture_time >= self.capture_interval:
                    self._capture_and_solve()
                    self.last_capture_time = current_time
                
                # Sleep briefly to avoid busy waiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                if self.on_error:
                    self.on_error(e)
                time.sleep(5)  # Wait before retrying
    
    def _capture_and_solve(self) -> None:
        """Nimmt ein Frame auf und führt ggf. Plate-Solving durch."""
        if not self.video_capture:
            return
        
        try:
            # Capture frame
            frame = self.video_capture.get_current_frame()
            if frame is None:
                self.logger.warning("No frame available for capture")
                return
            
            self.capture_count += 1
            
            # Save frame if enabled
            frame_filename = None
            if self.save_frames:
                # Generate filename with configurable timestamp and capture count
                filename_parts = ["capture"]
                
                if self.use_timestamps:
                    timestamp = datetime.now().strftime(self.timestamp_format)
                    filename_parts.append(timestamp)
                
                if self.use_capture_count:
                    filename_parts.append(f"{self.capture_count:04d}")
                
                frame_filename = self.frame_dir / f"{'_'.join(filename_parts)}.{self.file_format}"
                
                # For ASCOM cameras, get original data for FITS files
                if (self.video_capture.camera_type == 'ascom' and 
                    self.video_capture.ascom_camera and 
                    self.file_format.lower() in ['fit', 'fits']):
                    # Get settings from config
                    ascom_config = self.video_config.get('ascom', {})
                    exposure_time = ascom_config.get('exposure_time', 1.0)
                    gain = ascom_config.get('gain', None)
                    binning = ascom_config.get('binning', 1)
                    
                    # Get original ASCOM data
                    ascom_status = self.video_capture.capture_single_frame_ascom(
                        exposure_time_s=exposure_time,
                        gain=gain,
                        binning=binning
                    )
                    if ascom_status.is_success:
                        save_status = self.video_capture.save_frame(ascom_status, str(frame_filename))
                    else:
                        self.logger.warning(f"Failed to capture ASCOM frame: {ascom_status.message}")
                        save_status = None
                else:
                    # Use current frame (converted for display)
                    save_status = self.video_capture.save_frame(frame, str(frame_filename))
                
                if save_status and save_status.is_success:
                    self.logger.info(f"Frame saved: {frame_filename}")
                else:
                    self.logger.warning(f"Failed to save frame: {save_status.message if save_status else 'No status'}")
                    frame_filename = None
            
            # Trigger capture callback
            if self.on_capture_frame:
                self.on_capture_frame(frame, frame_filename)
            
            # Plate-solve if enabled and enough time has passed
            if (self.plate_solver and self.auto_solve and 
                time.time() - self.last_solve_time >= self.min_solve_interval):
                
                if frame_filename and frame_filename.exists():
                    self._solve_frame(str(frame_filename))
                else:
                    self.logger.warning("No frame file available for plate-solving")
            
        except Exception as e:
            self.logger.error(f"Error in capture and solve: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _status_to_result(self, status) -> Optional[PlateSolveResult]:
        """Convert PlateSolveStatus to PlateSolveResult."""
        if not status or not status.is_success:
            return None
        
        # Create PlateSolveResult from status data
        result = PlateSolveResult(success=True)
        
        # Extract data from status
        data = status.data if hasattr(status, 'data') else {}
        
        # Map status data to result fields
        result.ra_center = data.get('ra_center')
        result.dec_center = data.get('dec_center')
        result.fov_width = data.get('fov_width')
        result.fov_height = data.get('fov_height')
        result.position_angle = data.get('position_angle')
        result.image_size = data.get('image_size')
        result.confidence = data.get('confidence')
        result.stars_detected = data.get('stars_detected')
        result.solving_time = data.get('solving_time')
        result.solver_used = data.get('solver_used')
        
        return result

    def _solve_frame(self, frame_path: str) -> Optional[PlateSolveResult]:
        """Führt Plate-Solving für ein bestimmtes Frame durch.
        Args:
            frame_path: Pfad zum Bild
        Returns:
            Optional[PlateSolveResult]: Ergebnisobjekt oder None
        """
        if not self.plate_solver:
            return None
        
        try:
            self.logger.info(f"Plate-solving frame: {frame_path}")
            
            status = self.plate_solver.solve(frame_path)
            self.solve_count += 1
            
            # Convert status to result
            result = self._status_to_result(status)
            
            if result and result.success:
                self.successful_solves += 1
                self.last_solve_result = result
                self.logger.info(f"Plate-solving successful: {result}")
                
                # Trigger solve callback
                if self.on_solve_result:
                    self.on_solve_result(result)
            else:
                error_msg = status.error_message if hasattr(status, 'error_message') else 'Unknown error'
                self.logger.warning(f"Plate-solving failed: {error_msg}")
            
            self.last_solve_time = time.time()
            return result
            
        except Exception as e:
            self.logger.error(f"Error in plate-solving: {e}")
            if self.on_error:
                self.on_error(e)
            return None
    
    def solve_frame(self, frame_path: str) -> VideoProcessingStatus:
        """Manuelles Plate-Solving für ein bestimmtes Frame.
        Args:
            frame_path: Pfad zum Bild
        Returns:
            VideoProcessingStatus: Status-Objekt mit Ergebnis oder Fehler.
        """
        if not self.plate_solver:
            self.logger.error("No plate solver available")
            return error_status("No plate solver available")
        try:
            result = self._solve_frame(frame_path)
            if result and result.success:
                return success_status("Plate-solving successful", data=result.__dict__)
            else:
                return error_status(f"Plate-solving failed: {result.error_message if result else 'Unknown error'}")
        except Exception as e:
            self.logger.error(f"Error in plate-solving: {e}")
            return error_status(f"Error in plate-solving: {e}")
    
    def get_current_frame(self) -> Optional[Any]:
        """Gibt das aktuellste aufgenommene Frame zurück."""
        if self.video_capture:
            return self.video_capture.get_current_frame()
        return None
    
    def get_statistics(self) -> VideoProcessingStatus:
        """Gibt Statistiken zur Videoverarbeitung zurück.
        Returns:
            VideoProcessingStatus: Status-Objekt mit Statistikdaten.
        """
        stats = {
            'capture_count': self.capture_count,
            'solve_count': self.solve_count,
            'successful_solves': self.successful_solves,
            'last_solve_result': str(self.last_solve_result) if self.last_solve_result else None,
            'is_running': self.is_running
        }
        return success_status("Video processor statistics", data=stats)
    
    def set_callbacks(self, on_solve_result: Optional[Callable[[PlateSolveResult], None]] = None, on_capture_frame: Optional[Callable[[Any, Any], None]] = None, on_error: Optional[Callable[[Exception], None]] = None) -> None:
        """Setzt Callback-Funktionen für Ergebnisse, Frame-Capture und Fehler."""
        self.on_solve_result = on_solve_result
        self.on_capture_frame = on_capture_frame
        self.on_error = on_error 