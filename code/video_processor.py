#!/usr/bin/env python3
"""
Video Processor Module for Telescope Streaming System

This module coordinates video capture and plate-solving operations for astronomical imaging.
It provides a high-level interface for managing continuous image capture, slewing detection,
and automated plate-solving with configurable behavior.

Key Features:
- Continuous video capture with configurable intervals
- Intelligent slewing detection to prevent captures during mount movement
- Dual-format saving (FITS for plate-solving, PNG/JPG for display)
- Automated plate-solving with robust error handling
- Configurable capture and solving intervals
- Callback system for external integration
- Comprehensive status tracking and statistics

Architecture:
- Uses lazy loading for configuration to prevent double loading
- Threaded processing loop for non-blocking operation
- Status-based error handling for robust operation
- Modular design with separate video capture and plate-solving components

Dependencies:
- video_capture: For camera interface and image capture
- plate_solver: For astronomical plate-solving
- ascom_mount: For slewing detection (optional)
- config_manager: For configuration management
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
    """
    Coordinates video capture and plate-solving operations.
    
    This class manages the complete imaging pipeline from camera capture to
    plate-solving, including intelligent slewing detection to ensure only
    high-quality, stationary images are processed.
    
    The processor operates in two main modes:
    1. Skip Mode: Skips captures during mount movement (default)
    2. Wait Mode: Waits for slewing to complete before capturing
    
    Key Design Decisions:
    - Lazy configuration loading prevents double loading when config is passed from tests
    - Threaded processing ensures non-blocking operation
    - Status-based error handling provides robust operation
    - Dual-format saving ensures compatibility with both plate-solving and display
    """
    def __init__(self, config=None, logger=None) -> None:
        """Initialize the VideoProcessor.
        
        Sets up the video processor with configuration, logging, and initializes
        all necessary components for video capture and plate-solving.
        
        Args:
            config: Optional ConfigManager instance. If None, creates default config.
            logger: Optional logger instance. If None, creates module logger.
            
        Note:
            Uses lazy loading for configuration to prevent automatic loading of config.yaml
            when config is passed from test scripts. This ensures only one config file
            is loaded even when --config option is used.
        """
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
        self.mount: Optional[object] = None  # ASCOM mount for slewing detection
        self.is_running: bool = False
        self.processing_thread: Optional[threading.Thread] = None
        
        # Load configuration sections
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
        
        # Slewing detection settings
        # These settings control how the system handles mount movement during imaging
        mount_config = self.config.get_mount_config()
        slewing_config = mount_config.get('slewing_detection', {})
        self.slewing_detection_enabled: bool = slewing_config.get('enabled', True)
        self.slewing_check_before_capture: bool = slewing_config.get('check_before_capture', True)
        self.slewing_wait_for_completion: bool = slewing_config.get('wait_for_completion', False)
        self.slewing_wait_timeout: float = slewing_config.get('wait_timeout', 300.0)
        self.slewing_check_interval: float = slewing_config.get('check_interval', 1.0)
        
        # State tracking for statistics and timing
        self.last_capture_time: float = 0
        self.last_solve_time: float = 0
        self.last_solve_result: Optional[PlateSolveResult] = None
        self.capture_count: int = 0
        self.solve_count: int = 0
        self.successful_solves: int = 0
        
        # Callbacks for external integration
        self.on_solve_result: Optional[Callable[[PlateSolveResult], None]] = None
        self.on_capture_frame: Optional[Callable[[Any, Any], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # Ensure frame directory exists
        # This prevents file saving errors during operation
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
        """Initialize video capture and plate solver.
        
        Sets up all necessary components for video processing, including
        video capture, plate solver, and mount for slewing detection.
        
        Returns:
            bool: True if successfully initialized, False otherwise.
            
        Note:
            Mount initialization is optional - if it fails, slewing detection
            will be disabled but other functionality continues to work.
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
        
        # Initialize mount for slewing detection
        # This is optional - if it fails, slewing detection is disabled
        try:
            from ascom_mount import ASCOMMount
            self.mount = ASCOMMount(config=self.config, logger=self.logger)
            self.logger.info("Mount initialized for slewing detection")
        except Exception as e:
            self.logger.warning(f"Could not initialize mount for slewing detection: {e}")
            self.mount = None
        
        return success
    
    def start(self) -> VideoProcessingStatus:
        """Start video processing.
        
        Begins the continuous video capture and plate-solving loop in a separate thread.
        This method is non-blocking and returns immediately.
        
        Returns:
            VideoProcessingStatus: Status object with start information or error.
            
        Note:
            The processing loop runs in a separate thread to ensure the main
            application remains responsive during continuous operation.
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
        """Capture a frame and perform plate-solving if enabled.
        
        This is the core method that handles the complete imaging pipeline:
        1. Slewing detection to ensure only stationary images are captured
        2. Frame capture from the camera
        3. Dual-format saving (FITS for plate-solving, PNG/JPG for display)
        4. Automated plate-solving with robust error handling
        
        The method implements intelligent slewing detection with two modes:
        - Skip Mode: Skips captures during mount movement (default)
        - Wait Mode: Waits for slewing to complete before capturing
        
        Note:
            This method is called from the processing loop and handles all
            the complexity of ensuring high-quality astronomical imaging.
        """
        if not self.video_capture:
            return
        
        try:
            # CRITICAL: Check if mount is slewing before capturing
            # This prevents blurred images and improves plate-solving success
            if hasattr(self, 'mount') and self.mount and self.slewing_detection_enabled:
                slewing_status = self.mount.is_slewing()
                if slewing_status.is_success and slewing_status.data:
                    if self.slewing_wait_for_completion:
                        # Wait Mode: Wait for slewing to complete before capturing
                        # This ensures we get every possible frame for critical imaging
                        self.logger.info("Mount is slewing, waiting for completion...")
                        wait_status = self.mount.wait_for_slewing_complete(
                            timeout=self.slewing_wait_timeout,
                            check_interval=self.slewing_check_interval
                        )
                        if wait_status.is_success and wait_status.data:
                            self.logger.info("Slewing completed, proceeding with capture")
                        else:
                            self.logger.warning(f"Slewing wait failed or timed out: {wait_status.message}")
                            if not wait_status.data:  # Timeout
                                self.logger.info("Skipping capture due to slewing timeout")
                                return
                            else:  # Error
                                self.logger.warning("Continuing with capture despite slewing error")
                    else:
                        # Skip Mode: Skip capture if slewing (default behavior)
                        # This maximizes capture opportunities for high-frequency imaging
                        self.logger.debug("Mount is slewing, skipping capture")
                        return
                elif not slewing_status.is_success:
                    self.logger.warning(f"Could not check slewing status: {slewing_status.message}")
                    # Continue with capture if we can't check slewing status
                    # This ensures operation continues even if slewing detection fails
            
            # Capture frame from camera
            frame = self.video_capture.get_current_frame()
            if frame is None:
                self.logger.warning("No frame available for capture")
                return
            
            self.capture_count += 1
            
            # Save frames if enabled
            frame_filename = None
            fits_filename = None
            
            if self.save_frames:
                # Generate base filename with configurable timestamp and capture count
                # This provides flexible naming for different use cases
                filename_parts = ["capture"]
                
                if self.use_timestamps:
                    timestamp = datetime.now().strftime(self.timestamp_format)
                    filename_parts.append(timestamp)
                
                if self.use_capture_count:
                    filename_parts.append(f"{self.capture_count:04d}")
                
                base_filename = '_'.join(filename_parts)
                
                # DUAL-FORMAT SAVING: For ASCOM cameras, save both FITS and display format
                # This ensures compatibility with both plate-solving and display applications
                if (self.video_capture.camera_type == 'ascom' and 
                    self.video_capture.ascom_camera):
                    
                    # Get settings from config for ASCOM camera
                    ascom_config = self.video_config.get('ascom', {})
                    exposure_time = ascom_config.get('exposure_time', 1.0)
                    gain = ascom_config.get('gain', None)
                    binning = ascom_config.get('binning', 1)
                    
                    # 1. Always save FITS for plate-solving and processing
                    # FITS format preserves all astronomical data and is required for plate-solving
                    fits_filename = self.frame_dir / f"{base_filename}.fits"
                    ascom_status = self.video_capture.capture_single_frame_ascom(
                        exposure_time_s=exposure_time,
                        gain=gain,
                        binning=binning
                    )
                    if ascom_status.is_success:
                        fits_save_status = self.video_capture.save_frame(ascom_status, str(fits_filename))
                        if fits_save_status and fits_save_status.is_success:
                            self.logger.info(f"FITS frame saved: {fits_filename}")
                        else:
                            self.logger.warning(f"Failed to save FITS frame: {fits_save_status.message if fits_save_status else 'No status'}")
                    else:
                        self.logger.warning(f"Failed to capture ASCOM frame: {ascom_status.message}")
                    
                    # 2. Save display format (PNG/JPG) if different from FITS
                    # This provides user-friendly images for display and sharing
                    if self.file_format.lower() not in ['fit', 'fits']:
                        frame_filename = self.frame_dir / f"{base_filename}.{self.file_format}"
                        # Use current frame (converted for display)
                        display_save_status = self.video_capture.save_frame(frame, str(frame_filename))
                        if display_save_status and display_save_status.is_success:
                            self.logger.info(f"Display frame saved: {frame_filename}")
                        else:
                            self.logger.warning(f"Failed to save display frame: {display_save_status.message if display_save_status else 'No status'}")
                            frame_filename = None
                    else:
                        # If FITS is the display format, use FITS file for both
                        frame_filename = fits_filename
                
                else:
                    # For non-ASCOM cameras: Save only the configured format
                    # Non-ASCOM cameras don't need dual-format saving
                    frame_filename = self.frame_dir / f"{base_filename}.{self.file_format}"
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
                
                # Use FITS file for ASCOM cameras, otherwise use display format
                solve_filename = fits_filename if fits_filename and fits_filename.exists() else frame_filename
                
                if solve_filename and solve_filename.exists():
                    self.logger.info(f"Plate-solving frame: {solve_filename}")
                    self._solve_frame(str(solve_filename))
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
        """Execute plate-solving for a specific frame.
        
        Performs plate-solving on the specified frame file using the
        configured plate solver. This method handles the solving process
        and returns the results in a standardized format.
        
        Args:
            frame_path: Path to the frame file to solve
            
        Returns:
            Optional[PlateSolveResult]: Solving result or None if failed
            
        Note:
            This method is called automatically during the capture cycle
            when auto-solving is enabled and enough time has passed since
            the last solve.
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
                # Plate-solving failed - this is normal for poor conditions
                error_msg = status.message if hasattr(status, 'message') else 'Unknown error'
                details = status.details if hasattr(status, 'details') else {}
                solving_time = details.get('solving_time', 0)
                
                self.logger.warning(f"Plate-solving failed after {solving_time:.2f}s: {error_msg}")
                self.logger.info("Continuing with next exposure - conditions may improve for next attempt")
                
                # Check if this is a "no stars" or "poor conditions" failure
                if 'no_stars' in error_msg.lower() or 'poor_conditions' in str(details).lower():
                    self.logger.info("Failure likely due to poor seeing or cloud cover - normal for astronomical imaging")
            
            self.last_solve_time = time.time()
            return result
            
        except Exception as e:
            self.logger.error(f"Error in plate-solving: {e}")
            if self.on_error:
                self.on_error(e)
            return None
    
    def solve_frame(self, frame_path: str) -> VideoProcessingStatus:
        """Manual plate-solving for a specific frame.
        
        Allows manual triggering of plate-solving for a specific frame file.
        This is useful for testing or when you want to solve a frame outside
        of the normal capture cycle.
        
        Args:
            frame_path: Path to the frame file to solve
            
        Returns:
            VideoProcessingStatus: Status object with solving results
            
        Note:
            This method can be called independently of the capture cycle
            and is useful for debugging or manual processing.
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
        """Get the most recently captured frame.
        
        Returns the current frame from the video capture system.
        This is useful for external applications that need access
        to the latest captured image.
        
        Returns:
            Optional[Any]: The current frame or None if not available.
        """
        if self.video_capture:
            return self.video_capture.get_current_frame()
        return None
    
    def get_statistics(self) -> VideoProcessingStatus:
        """Get processing statistics.
        
        Returns comprehensive statistics about the video processing
        operation, including capture counts, solve counts, and timing
        information.
        
        Returns:
            VideoProcessingStatus: Status object with statistics data.
        """
        stats = {
            'capture_count': self.capture_count,
            'solve_count': self.solve_count,
            'successful_solves': self.successful_solves,
            'last_capture_time': self.last_capture_time,
            'last_solve_time': self.last_solve_time,
            'is_running': self.is_running
        }
        
        return success_status(
            f"Statistics: {self.capture_count} captures, {self.successful_solves} successful solves",
            data=stats,
            details=stats
        )
    
    def set_callbacks(self, on_solve_result: Optional[Callable[[PlateSolveResult], None]] = None, on_capture_frame: Optional[Callable[[Any, Any], None]] = None, on_error: Optional[Callable[[Exception], None]] = None) -> None:
        """Set callback functions for results, frame capture, and errors.
        
        Allows external applications to receive notifications about
        processing events through callback functions.
        
        Args:
            on_solve_result: Callback for plate-solving results
            on_capture_frame: Callback for frame capture events
            on_error: Callback for error conditions
            
        Note:
            Callbacks are called from the processing thread, so they
            should be thread-safe and not block for extended periods.
        """
        self.on_solve_result = on_solve_result
        self.on_capture_frame = on_capture_frame
        self.on_error = on_error 