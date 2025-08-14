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

from datetime import datetime
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Optional

# Import local modules
from capture.controller import VideoCapture
from overlay.generator import OverlayGenerator
from PIL import Image
from platesolve.solver import PlateSolveResult, PlateSolverFactory
from services.frame_writer import FrameWriter
from status import VideoProcessingStatus, error_status, success_status
from utils.status_utils import unwrap_status


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

        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        self.video_capture: Optional[VideoCapture] = None
        self.frame_writer: Optional[FrameWriter] = None
        self.plate_solver: Optional[Any] = None
        self.mount: Optional[Any] = None  # ASCOM mount for slewing detection
        self.is_running: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        # Load configuration sections
        self.frame_config: dict[str, Any] = self.config.get_frame_processing_config()
        self.plate_solve_config: dict[str, Any] = self.config.get_plate_solve_config()

        # Frame processing settings
        self.frame_enabled: bool = self.frame_config.get("enabled", True)
        self.capture_interval: int = self.config.get_plate_solve_config().get(
            "min_solve_interval", 60
        )
        self.save_frames: bool = self.frame_config.get("save_plate_solve_frames", True)
        self.frame_dir: Path = Path(self.frame_config.get("plate_solve_dir", "plate_solve_frames"))

        # Timestamp settings for frame filenames
        self.use_timestamps: bool = self.frame_config.get("use_timestamps", False)
        self.timestamp_format: str = self.frame_config.get("timestamp_format", "%Y%m%d_%H%M%S")
        self.use_capture_count: bool = self.frame_config.get("use_capture_count", True)
        self.file_format: str = self.frame_config.get("file_format", "PNG")

        # Plate-solving settings
        self.solver_type: str = self.plate_solve_config.get("default_solver", "platesolve2")
        self.auto_solve: bool = self.plate_solve_config.get("auto_solve", True)
        self.plate_solve_enabled: bool = self.auto_solve  # Alias for consistency
        self.min_solve_interval: int = self.plate_solve_config.get("min_solve_interval", 30)

        # Slewing detection settings
        # These settings control how the system handles mount movement during imaging
        mount_config = self.config.get_mount_config()
        slewing_config = mount_config.get("slewing_detection", {})
        self.slewing_detection_enabled: bool = slewing_config.get("enabled", True)
        self.slewing_check_before_capture: bool = slewing_config.get("check_before_capture", True)
        self.slewing_wait_for_completion: bool = slewing_config.get("wait_for_completion", False)
        self.slewing_wait_timeout: float = slewing_config.get("wait_timeout", 300.0)
        self.slewing_check_interval: float = slewing_config.get("check_interval", 1.0)

        # State tracking for statistics and timing
        self.last_capture_time: float = time.monotonic()
        self.last_solve_time: float = time.monotonic()
        self.last_solve_result: Optional[PlateSolveResult] = None
        self.capture_count: int = 0
        self.solve_count: int = 0
        self.successful_solves: int = 0
        self.last_frame_metadata: Optional[dict[str, Any]] = None
        # Scheduling condition for efficient sleeps and external wake-ups
        self._condition = threading.Condition()

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
                self.logger.warning(
                    f"Using current directory for frame storage: {self.frame_dir.absolute()}"
                )

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
        if self.frame_enabled:
            try:
                self.video_capture = VideoCapture(
                    config=self.config, logger=self.logger, return_frame_objects=True
                )
                self.logger.info("Video capture initialized")
                # Initialize FrameWriter now that we have camera and type
                self.frame_writer = FrameWriter(
                    config=self.config,
                    logger=self.logger,
                    camera=self.video_capture.camera,
                    camera_type=self.video_capture.camera_type,
                )
                # Initialize CoolingService and kick off status monitoring if enabled
                try:
                    from services.cooling.service import CoolingService

                    self.cooling_service = CoolingService(self.config, logger=self.logger)
                    if self.video_capture and self.video_capture.camera:
                        self.cooling_service.initialize(self.video_capture.camera)
                    cooling_cfg = self.config.get_camera_config().get("cooling", {})
                    if cooling_cfg.get("enable_cooling", False):
                        interval = cooling_cfg.get("status_interval", 30)
                        self.cooling_service.start_status_monitor(interval)
                except Exception as e:
                    self.logger.debug(f"CoolingService not started: {e}")
                # Make overlay generator aware of processor for cooling info
                try:
                    self.overlay_generator = OverlayGenerator(self.config, self.logger)
                    # Inject a reference for optional cooling information access
                    self.overlay_generator.video_processor = self
                except Exception as e:
                    self.logger.debug(f"OverlayGenerator not initialized: {e}")
            except Exception as e:
                self.logger.error(f"Error initializing video capture: {e}")
                success = False

        # Initialize plate solver
        if self.auto_solve:
            try:
                self.plate_solver = PlateSolverFactory.create_solver(
                    self.solver_type, config=self.config, logger=self.logger
                )
                if (
                    self.plate_solver
                    and hasattr(self.plate_solver, "is_available")
                    and self.plate_solver.is_available()
                ):
                    name = (
                        self.plate_solver.get_name()
                        if hasattr(self.plate_solver, "get_name")
                        else str(self.plate_solver)
                    )
                    self.logger.info(f"Plate solver initialized: {name}")
                else:
                    self.logger.warning(f"Plate solver not available: {self.solver_type}")
                    self.plate_solver = None
            except Exception as e:
                self.logger.error(f"Error initializing plate solver: {e}")
                self.plate_solver = None

        # Initialize mount for slewing detection (optional)
        try:
            from drivers.ascom.mount import ASCOMMount

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
        # Skip initialization if already done in start_observation_session
        if not self.video_capture:
            if not self.initialize():
                return error_status(
                    "Initialization failed", details={"frame_enabled": self.frame_enabled}
                )

        if not self.video_capture:
            self.logger.error("Video capture not available")
            return error_status(
                "Video capture not available", details={"frame_enabled": self.frame_enabled}
            )

        # Video capture is already started in start_observation_session
        # Just start the processing loop
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        self.logger.info("Video processing loop started")
        return success_status(
            "Video processing loop started",
            details={"frame_enabled": self.frame_enabled, "is_running": True},
        )

    def stop(self) -> VideoProcessingStatus:
        """Stoppt die Videoverarbeitung.
        Returns:
            VideoProcessingStatus: Status-Objekt mit Stopinformation.
        """
        self.is_running = False
        try:
            with self._condition:
                self._condition.notify_all()
        except Exception:
            pass
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        if self.video_capture:
            self.video_capture.stop_capture()
            self.video_capture.disconnect()
        self.logger.info("Video processor stopped")
        return success_status("Video processor stopped", details={"is_running": False})

    def stop_processing_only(self) -> VideoProcessingStatus:
        """Stoppt nur die Verarbeitung, lässt aber die Kamera-Verbindung offen.

        This method stops the processing loop and capture operations but keeps
        the camera connection alive for cooling operations.

        Returns:
            VideoProcessingStatus: Status-Objekt mit Stopinformation.
        """
        self.is_running = False
        try:
            with self._condition:
                self._condition.notify_all()
        except Exception:
            pass
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        if self.video_capture:
            self.video_capture.stop_capture()
        self.logger.info("Video processor processing stopped (camera connection maintained)")
        return success_status("Video processor processing stopped", details={"is_running": False})

    def disconnect_camera(self) -> VideoProcessingStatus:
        """Disconnect the camera after warmup is complete.

        This method should be called after warmup is complete to properly
        disconnect the camera.

        Returns:
            VideoProcessingStatus: Status-Objekt mit Disconnect-Information.
        """
        if self.video_capture:
            self.video_capture.disconnect()
            self.logger.info("Camera disconnected")
        return success_status("Camera disconnected")

    def _obtain_frame(self):
        """Obtain a frame via one-shot (ASCOM/Alpaca) or current frame (OpenCV)."""
        if not self.video_capture:
            return None
        try:
            cam_type = getattr(self.video_capture, "camera_type", "opencv")
            if cam_type in ["alpaca", "ascom"]:
                status = self.video_capture.capture_single_frame()
                if not status or not getattr(status, "is_success", False):
                    msg = getattr(status, "message", "unknown error")
                    self.logger.warning(f"Single-frame capture failed: {msg}")
                    return None
                return status
            return self.video_capture.get_current_frame()
        except Exception as e:
            self.logger.warning(f"Failed to obtain frame: {e}")
            return None

    def _save_outputs(self, frame) -> tuple[Optional[Path], Optional[Path]]:
        """Save display image and FITS; return their paths (may be None)."""
        frame_filename: Optional[Path] = None
        fits_filename: Optional[Path] = None
        if not self.save_frames:
            return frame_filename, fits_filename
        # Build base filename
        filename_parts = ["capture"]
        if self.use_timestamps:
            timestamp = datetime.now().strftime(self.timestamp_format)
            filename_parts.append(timestamp)
        if self.use_capture_count:
            filename_parts.append(f"{self.capture_count:04d}")
        base = "_".join(filename_parts)

        # Ensure writer exists
        if not self.frame_writer and self.video_capture:
            self.frame_writer = FrameWriter(
                config=self.config,
                logger=self.logger,
                camera=self.video_capture.camera,
                camera_type=self.video_capture.camera_type,
            )

        # Extract details and attach capture_id
        try:
            _, details = unwrap_status(frame)
            if not isinstance(details, dict):
                details = {}
        except Exception:
            details = {}
        details_with_id = {**details, "capture_id": self.capture_count}

        # Save display image (measure duration)
        frame_filename = self.frame_dir / f"{base}.{self.file_format}"
        t0 = time.monotonic()
        img_status = (
            self.frame_writer.save(frame, str(frame_filename)) if self.frame_writer else None
        )
        img_ms = (time.monotonic() - t0) * 1000.0
        if not (img_status and getattr(img_status, "is_success", False)):
            self.logger.warning(
                f"Failed to save frame: {getattr(img_status, 'message', 'No status')}"
            )
            frame_filename = None
        else:
            self.logger.info(f"Frame saved: {frame_filename} save_ms={img_ms:.1f}")

        # Save FITS with metadata (measure duration)
        fits_filename = self.frame_dir / f"{base}.fits"
        t1 = time.monotonic()
        fits_status = (
            self.frame_writer.save(frame, str(fits_filename), metadata=details_with_id)
            if self.frame_writer
            else None
        )
        fits_ms = (time.monotonic() - t1) * 1000.0
        if not (fits_status and getattr(fits_status, "is_success", False)):
            self.logger.warning(
                f"Failed to save FITS frame: {getattr(fits_status, 'message', 'No status')}"
            )
            fits_filename = None
        else:
            self.logger.info(f"FITS frame saved: {fits_filename} save_ms={fits_ms:.1f}")

        return frame_filename, fits_filename

    def _maybe_plate_solve(
        self, fits_filename: Optional[Path], frame_filename: Optional[Path]
    ) -> None:
        """Run plate-solving if enabled and interval elapsed; prefer FITS."""
        if not (self.plate_solver and self.auto_solve):
            return
        if (time.monotonic() - self.last_solve_time) < self.min_solve_interval:
            return
        candidate: Optional[Path] = None
        if fits_filename and fits_filename.exists():
            candidate = fits_filename
            self.logger.info(f"Using FITS file for plate-solving: {candidate}")
        elif frame_filename and frame_filename.exists():
            candidate = frame_filename
            self.logger.warning(
                f"FITS not available, using display image for plate-solving: {candidate}"
            )
            self.logger.warning("This may not be supported by some solvers")
        else:
            self.logger.error("No suitable file to plate-solve")
            return
        self._solve_frame(str(candidate))
        self.last_solve_time = time.monotonic()

    def start_observation_session(self) -> VideoProcessingStatus:
        """Start an observation session with cooling initialization.

        This method initializes the video processor for a complete observation session,
        including camera cooling if enabled. It's called by the OverlayRunner when
        starting a new observation session.

        Returns:
            VideoProcessingStatus: Status object with session start information or error.
        """
        try:
            self.logger.info("Starting observation session...")

            # Initialize the video processor if not already done
            if not self.initialize():
                return error_status("Failed to initialize video processor for observation session")

            # Start video capture (but not the processing loop yet)
            if not self.video_capture:
                self.logger.error("Video capture not available")
                return error_status(
                    "Video capture not available", details={"frame_enabled": self.frame_enabled}
                )

            capture_status = self.video_capture.start_capture()
            if not capture_status.is_success:
                self.logger.error("Failed to start video capture")
                return error_status(
                    "Failed to start video capture", details={"frame_enabled": self.frame_enabled}
                )

            # Initialize and (optionally) wait for camera cooling if enabled in config
            try:
                cooling_cfg = self.config.get_camera_config().get("cooling", {})
                if cooling_cfg.get("enable_cooling", False) and hasattr(self, "cooling_service"):
                    target_temp = float(cooling_cfg.get("target_temperature", -10.0))
                    wait_for = bool(cooling_cfg.get("wait_for_cooling", True))
                    timeout_s = float(cooling_cfg.get("cooling_timeout", 300))
                    init_cool = self.cooling_service.initialize_and_stabilize(
                        target_temp, wait_for, timeout_s
                    )
                    if not init_cool.is_success:
                        self.logger.warning(f"Cooling initialization: {init_cool.message}")
            except Exception as e:
                self.logger.debug(f"Cooling initialization skipped: {e}")

            self.logger.info("Observation session initialized successfully")
            return success_status(
                "Observation session initialized successfully",
                details={
                    "frame_enabled": self.frame_enabled,
                    "is_running": False,  # Processing loop not started yet
                    "capture_interval": self.capture_interval,
                    "plate_solve_enabled": self.plate_solve_enabled,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to start observation session: {e}")
            return error_status(f"Failed to start observation session: {e}")

    def end_observation_session(self) -> VideoProcessingStatus:
        """End an observation session with proper cleanup.

        This method properly stops the video processor and performs any necessary
        cleanup for the observation session. It's called by the OverlayRunner when
        ending an observation session.

        Returns:
            VideoProcessingStatus: Status object with session end information or error.
        """
        try:
            self.logger.info("Ending observation session...")

            # Stop the video processor
            stop_status = self.stop()
            if not stop_status.is_success:
                self.logger.warning(f"Video processor stop warning: {stop_status.message}")

            self.logger.info("Observation session ended successfully")
            return success_status(
                "Observation session ended successfully",
                details={
                    "is_running": self.is_running,
                    "capture_count": getattr(self, "capture_count", 0),
                    "solve_count": getattr(self, "solve_count", 0),
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to end observation session: {e}")
            return error_status(f"Failed to end observation session: {e}")

    def _processing_loop(self) -> None:
        """Main processing loop using monotonic clock and a condition for timing."""
        while self.is_running:
            try:
                now = time.monotonic()
                elapsed = now - self.last_capture_time
                if elapsed >= self.capture_interval:
                    self._capture_and_solve()
                    self.last_capture_time = time.monotonic()
                    continue
                # Efficient wait for the remaining interval or external wake-up
                timeout = max(0.05, self.capture_interval - elapsed)
                with self._condition:
                    self._condition.wait(timeout=timeout)
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                if self.on_error:
                    self.on_error(e)
                # Short backoff before retrying
                try:
                    with self._condition:
                        self._condition.wait(timeout=0.5)
                except Exception:
                    time.sleep(0.5)

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
            if hasattr(self, "mount") and self.mount and self.slewing_detection_enabled:
                slewing_status = self.mount.is_slewing()
                if slewing_status.is_success and slewing_status.data:
                    if self.slewing_wait_for_completion:
                        self.logger.info("Mount is slewing, waiting for completion...")
                        wait_status = self.mount.wait_for_slewing_complete(
                            timeout=self.slewing_wait_timeout,
                            check_interval=self.slewing_check_interval,
                        )
                        if wait_status.is_success and wait_status.data:
                            self.logger.info("Slewing completed, proceeding with capture")
                        else:
                            self.logger.warning(
                                f"Slewing wait failed or timed out: {wait_status.message}"
                            )
                            if not wait_status.data:
                                self.logger.info("Skipping capture due to slewing timeout")
                                return
                            else:
                                self.logger.warning("Continuing with capture despite slewing error")
                    else:
                        self.logger.debug("Mount is slewing, skipping capture")
                        return
                elif not slewing_status.is_success:
                    self.logger.warning(f"Could not check slewing status: {slewing_status.message}")

            # Obtain frame (one-shot for long exposures, current for OpenCV) and time it
            t_capture_start = time.monotonic()
            frame = self._obtain_frame()
            if frame is None:
                self.logger.warning("No frame available for capture")
                return
            capture_ms = (time.monotonic() - t_capture_start) * 1000.0
            # Increment capture counter once per cycle
            self.capture_count += 1
            # Capture and store frame metadata for downstream consumers; attach capture_id
            try:
                _, details = unwrap_status(frame)
                if isinstance(details, dict) and details:
                    # assign a capture_id for correlation
                    details = {**details, "capture_id": self.capture_count}
                    self.last_frame_metadata = details
                    # Structured log for capture
                    exp = details.get("exposure_time_s") or details.get("exposure_time")
                    gain = details.get("gain")
                    off = details.get("offset")
                    readout = details.get("readout_mode")
                    dims = details.get("dimensions")
                    self.logger.info(
                        "capture_id=%s exp=%s gain=%s offset=%s readout=%s dims=%s",
                        self.capture_count,
                        exp,
                        gain,
                        off,
                        readout,
                        dims,
                    )
            except Exception:
                pass

            # Save frames if enabled
            frame_filename: Optional[Path] = None
            fits_filename: Optional[Path] = None
            if self.save_frames:
                t_save_start = time.monotonic()
                frame_filename, fits_filename = self._save_outputs(frame)
                total_save_ms = (time.monotonic() - t_save_start) * 1000.0
            else:
                total_save_ms = 0.0

            # Trigger capture callback
            if self.on_capture_frame:
                self.on_capture_frame(frame, frame_filename)

            # Plate-solve if enabled and interval elapsed
            t_solve_start = time.monotonic()
            self._maybe_plate_solve(fits_filename, frame_filename)
            solve_ms = (time.monotonic() - t_solve_start) * 1000.0

            # Aggregate and log timings
            self.logger.info(
                "capture_id=%s timings_ms capture=%.1f save=%.1f solve=%.1f",
                self.capture_count,
                capture_ms,
                total_save_ms,
                solve_ms,
            )

        except Exception as e:
            self.logger.error(f"Error in capture and solve: {e}")
            if self.on_error:
                self.on_error(e)

    def _status_to_result(self, status) -> Optional[PlateSolveResult]:
        """Convert PlateSolveStatus to PlateSolveResult.

        Converts the status-based result from plate-solving into the
        standardized PlateSolveResult object for compatibility with
        existing callback systems.

        Args:
            status: PlateSolveStatus object from plate solver

        Returns:
            Optional[PlateSolveResult]: Converted result or None if failed
        """
        if not status or not status.is_success:
            return None

        # Extract data from status
        data = status.data if hasattr(status, "data") else {}
        details = status.details if hasattr(status, "details") else {}

        # Get required parameters with defaults and ensure they are valid numbers
        def safe_float(value, default=0.0):
            """Safely convert value to float, returning default if conversion fails."""
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        ra_center = safe_float(data.get("ra_center"), 0.0)
        dec_center = safe_float(data.get("dec_center"), 0.0)
        fov_width = safe_float(data.get("fov_width"), 1.0)
        fov_height = safe_float(data.get("fov_height"), 1.0)
        solving_time = safe_float(details.get("solving_time"), 0.0)
        method = details.get("method", "unknown")
        confidence = (
            safe_float(data.get("confidence")) if data.get("confidence") is not None else None
        )
        position_angle = (
            safe_float(data.get("position_angle"))
            if data.get("position_angle") is not None
            else None
        )
        image_size = data.get("image_size")  # Keep as tuple, no conversion needed
        # Normalize flip information: PlateSolve2 compatibility (only values > 0 mean flipped)
        raw_flip = data.get("flipped", False)
        is_flipped = False
        try:
            if isinstance(raw_flip, (int, float)):
                is_flipped = float(raw_flip) > 0
            elif isinstance(raw_flip, str):
                is_flipped = raw_flip.strip().lower() in ("1", "true", "yes", "flipped")
            else:
                is_flipped = bool(raw_flip)
        except Exception:
            is_flipped = False

        # Create PlateSolveResult with new API
        result = PlateSolveResult(
            ra_center=ra_center,
            dec_center=dec_center,
            fov_width=fov_width,
            fov_height=fov_height,
            solving_time=solving_time,
            method=method,
            confidence=confidence,
            position_angle=position_angle,
            image_size=image_size,
            is_flipped=is_flipped,
        )

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

            if result:
                self.successful_solves += 1
                self.last_solve_result = result
                self.logger.info(
                    "Plate-solving successful: RA=%.4f°, Dec=%.4f°, FOV=%.3f°x%.3f°",
                    result.ra_center,
                    result.dec_center,
                    result.fov_width,
                    result.fov_height,
                )

                # Trigger solve callback
                if self.on_solve_result:
                    self.on_solve_result(result)
            else:
                # Plate-solving failed - this is normal for poor conditions
                error_msg = status.message if hasattr(status, "message") else "Unknown error"
                details = status.details if hasattr(status, "details") else {}
                solving_time = details.get("solving_time", 0)

                self.logger.warning(f"Plate-solving failed after {solving_time:.2f}s: {error_msg}")
                self.logger.info(
                    "Continuing with next exposure - conditions may improve for next attempt"
                )

                # Check if this is a "no stars" or "poor conditions" failure
                if "no_stars" in error_msg.lower() or "poor_conditions" in str(details).lower():
                    self.logger.info(
                        "Failure likely due to poor seeing or cloud cover",
                    )
                    self.logger.info("This is normal for astronomical imaging")

            self.last_solve_time = time.time()
            return result

        except Exception as e:
            self.logger.error(f"Error in plate-solving: {e}")
            if self.on_error:
                self.on_error(e)
            return None

    def combine_overlay_with_image(
        self, image_path, overlay_path, output_path: Optional[str] = None
    ) -> VideoProcessingStatus:
        """Combine an overlay with a captured image.

        Merges the astronomical overlay with the captured telescope image
        and saves the combined result. The overlay is applied with transparency
        to show both the original image and the astronomical annotations.

        Args:
            image_path: Path to the captured telescope image (string or Status object)
            overlay_path: Path to the generated overlay image (string or Status object)
            output_path: Optional output path for the combined image

        Returns:
            Status: Success or error status with details

        Note:
            This method creates a composite image that shows both the
            original telescope view and the astronomical overlay annotations.
        """
        try:
            # Handle Status objects for image_path
            if hasattr(image_path, "data") and image_path.data:
                image_path = image_path.data
            elif (
                hasattr(image_path, "is_success")
                and image_path.is_success
                and hasattr(image_path, "data")
            ):
                image_path = image_path.data

            # Handle Status objects for overlay_path
            if hasattr(overlay_path, "data") and overlay_path.data:
                overlay_path = overlay_path.data
            elif (
                hasattr(overlay_path, "is_success")
                and overlay_path.is_success
                and hasattr(overlay_path, "data")
            ):
                overlay_path = overlay_path.data

            # Validate that we have string paths
            if not isinstance(image_path, str):
                return error_status(f"Invalid image_path type: {type(image_path)}, expected string")
            if not isinstance(overlay_path, str):
                return error_status(
                    f"Invalid overlay_path type: {type(overlay_path)}, expected string"
                )

            # Validate input files
            if not os.path.exists(image_path):
                return error_status(f"Image file not found: {image_path}")
            if not os.path.exists(overlay_path):
                return error_status(f"Overlay file not found: {overlay_path}")

            # Generate output path if not provided
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                output_path = f"{base_name}_with_overlay.png"

            # Load images
            try:
                base_image = Image.open(image_path).convert("RGBA")
                overlay_image = Image.open(overlay_path).convert("RGBA")
            except Exception as e:
                return error_status(f"Error loading images: {e}")

            # Resize overlay to match base image if sizes differ
            if base_image.size != overlay_image.size:
                self.logger.info(f"Resizing overlay from {overlay_image.size} to {base_image.size}")
                overlay_image = overlay_image.resize(base_image.size, Image.Resampling.LANCZOS)

            # Create composite image
            try:
                composite = base_image.copy()
                composite = Image.alpha_composite(composite, overlay_image)
                composite_rgb = composite.convert("RGB")
                composite_rgb.save(output_path, "PNG", quality=95)
                self.logger.info(f"Combined image saved: {output_path}")
                return success_status(
                    f"Image combined successfully: {output_path}",
                    data=output_path,
                    details={
                        "base_image": image_path,
                        "overlay_image": overlay_path,
                        "output_image": output_path,
                        "image_size": base_image.size,
                        "overlay_size": overlay_image.size,
                    },
                )
            except Exception as e:
                return error_status(f"Error creating composite image: {e}")

        except Exception as e:
            self.logger.error(f"Error in combine_overlay_with_image: {e}")
            return error_status(f"Error combining overlay with image: {e}")

    def get_latest_frame_path(self) -> Optional[str]:
        """Get the path to the most recently captured frame.

        Returns the file path of the last frame that was captured
        by the video capture system.

        Returns:
            Optional[str]: Path to the latest frame file, or None if not available

        Note:
            This method provides access to the most recent captured frame
            for use in overlay combination or other processing tasks.
        """
        try:
            if not self.video_capture:
                return None

            # Try to get the latest frame path from video capture
            if hasattr(self.video_capture, "get_latest_frame_path"):
                result = self.video_capture.get_latest_frame_path()

                # Handle both string and Status object returns
                if isinstance(result, str):
                    return result
                if hasattr(result, "data"):
                    data = result.data
                    if isinstance(data, str):
                        return data
                if hasattr(result, "is_success") and result.is_success and hasattr(result, "data"):
                    data = result.data
                    if isinstance(data, str):
                        return data
                else:
                    self.logger.debug("Video capture get_latest_frame_path returned no valid path")

            # Get the plate solve directory from config
            plate_solve_dir = self.frame_config.get("plate_solve_dir", "plate_solve_frames")

            # Get the configured image format from frame config
            image_format = self.frame_config.get("file_format", "PNG").lower()
            if image_format.startswith("."):  # Remove leading dot if present
                image_format = image_format[1:]

            # Check if timestamps are used
            use_timestamps = bool(self.config.get_overlay_config().get("use_timestamps", False))

            if not use_timestamps:
                capture_file = os.path.join(plate_solve_dir, f"capture.{image_format}")
                if os.path.exists(capture_file):
                    self.logger.debug(f"Found capture file: {capture_file}")
                    return capture_file
                else:
                    self.logger.debug(f"Capture file not found: {capture_file}")
                    return None
            else:
                if not os.path.exists(plate_solve_dir):
                    self.logger.debug(f"Plate solve directory does not exist: {plate_solve_dir}")
                    return None

                latest_file: Optional[str] = None
                latest_time: float = 0.0

                for filename in os.listdir(plate_solve_dir):
                    if filename.lower().endswith(f".{image_format}"):
                        file_path = os.path.join(plate_solve_dir, filename)
                        try:
                            file_time = os.path.getmtime(file_path)
                            if file_time > latest_time:
                                latest_time = file_time
                                latest_file = file_path
                        except OSError as e:
                            self.logger.debug(
                                f"Could not get modification time for {file_path}: {e}"
                            )
                            continue

                if latest_file:
                    self.logger.debug(f"Found latest timestamped frame: {latest_file}")
                else:
                    self.logger.debug(f"No {image_format} files found in {plate_solve_dir}")

                return latest_file

        except Exception as e:
            self.logger.error(f"Error getting latest frame path: {e}")
            return None

    def capture_and_combine_with_overlay(
        self, overlay_path: str, output_path: Optional[str] = None
    ) -> VideoProcessingStatus:
        """Capture a frame and combine it with an overlay.

        Captures a single frame from the video stream, combines it with
        the provided overlay, and saves the result. This is useful for
        creating annotated images for documentation or analysis.

        Args:
            overlay_path: Path to the overlay image to combine
            output_path: Optional output path for the combined image

        Returns:
            Status: Success or error status with details

        Note:
            This method is a convenience function that combines frame
            capture with overlay combination in a single operation.
        """
        try:
            if not self.video_capture:
                return error_status("No video capture available")

            capture_status = (
                self.video_capture.start_capture()
            )  # Assuming start_capture returns a status
            if not capture_status.is_success:
                return error_status(f"Failed to capture frame: {capture_status.message}")

            image_path = capture_status.data  # May need adaptation if API differs

            return self.combine_overlay_with_image(image_path, overlay_path, output_path)

        except Exception as e:
            self.logger.error(f"Error in capture_and_combine_with_overlay: {e}")
            return error_status(f"Error capturing and combining with overlay: {e}")

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
            if result:
                result_data = {
                    "ra_center": result.ra_center,
                    "dec_center": result.dec_center,
                    "fov_width": result.fov_width,
                    "fov_height": result.fov_height,
                    "solving_time": result.solving_time,
                    "method": result.method,
                    "confidence": result.confidence,
                    "position_angle": result.position_angle,
                    "image_size": result.image_size,
                }
                return success_status("Plate-solving successful", data=result_data)
            else:
                return error_status("Plate-solving failed: No result returned")
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
            "capture_count": self.capture_count,
            "solve_count": self.solve_count,
            "successful_solves": self.successful_solves,
            "last_capture_time": self.last_capture_time,
            "last_solve_time": self.last_solve_time,
            "is_running": self.is_running,
        }

        return success_status(
            f"Statistics: {self.capture_count} captures, "
            f"{self.successful_solves} successful solves",
            data=stats,
            details=stats,
        )

    def set_callbacks(
        self,
        on_solve_result: Optional[Callable[[PlateSolveResult], None]] = None,
        on_capture_frame: Optional[Callable[[Any, Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
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
