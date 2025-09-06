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
        # Raw FITS archival options
        self.save_raw_fits: bool = bool(self.frame_config.get("save_raw_fits", False))
        self.raw_fits_dir: Path = Path(self.frame_config.get("raw_fits_dir", "raw_fits"))

        # Capture gating (slew/tracking) from overlay config (robust to minimal test configs)
        try:
            overlay_cfg = (
                self.config.get_overlay_config()
                if hasattr(self.config, "get_overlay_config")
                else {}
            )
            if not isinstance(overlay_cfg, dict):
                overlay_cfg = {}
        except Exception:
            overlay_cfg = {}
        gating_cfg = overlay_cfg.get("capture_gating", {}) if isinstance(overlay_cfg, dict) else {}
        self.gating_block_during_slew: bool = bool(gating_cfg.get("block_during_slew", True))
        self.gating_require_tracking: bool = bool(gating_cfg.get("require_tracking", False))

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
        # Adaptive exposure override (seconds) set between captures
        self.next_exposure_time_override: Optional[float] = None
        # Window during which bright-target short exposure may cause poor star detection;
        # fallback to last successful solve within this window on solve failure
        self.solar_bright_override_until: Optional[float] = None
        # Last discard information (e.g., slewing/tracking off)
        self.last_discard_message: Optional[str] = None
        self.last_discard_time: Optional[float] = None

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
                except Exception as e:
                    self.logger.debug(f"CoolingService not started: {e}")
                # Make overlay generator aware of processor for cooling info
                try:
                    self.overlay_generator = OverlayGenerator(self.config, self.logger)
                    # Inject a reference for optional cooling information access
                    self.overlay_generator.video_processor = self
                    # Provide camera name to overlay (for info panel) if available
                    try:
                        camera_name = None
                        cam = getattr(self.video_capture, "camera", None)
                        if cam is not None:
                            get_info = getattr(cam, "get_camera_info", None)
                            if callable(get_info):
                                info_status = get_info()
                                if getattr(info_status, "is_success", False):
                                    data = getattr(info_status, "data", {}) or {}
                                    if isinstance(data, dict):
                                        camera_name = (
                                            data.get("camera_model")
                                            or data.get("name")
                                            or data.get("model")
                                            or data.get("driver_name")
                                        )
                            if not camera_name:
                                camera_name = getattr(cam, "model", None) or getattr(
                                    cam, "name", None
                                )
                        if camera_name:
                            self.overlay_generator.camera_name = str(camera_name)
                    except Exception:
                        pass
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

    def refresh_plate_solve_settings(self) -> None:
        """Refresh plate-solve related settings after a config reload.

        Updates solver type, auto_solve flag, and intervals. If the solver type
        changed or settings likely require re-initialization, recreate the solver instance.
        """
        try:
            new_cfg = self.config.get_plate_solve_config()
            new_solver_type = str(new_cfg.get("default_solver", self.solver_type))
            new_auto_solve = bool(new_cfg.get("auto_solve", self.auto_solve))
            new_min_interval = int(new_cfg.get("min_solve_interval", self.min_solve_interval))
            new_capture_interval = int(new_cfg.get("min_solve_interval", self.capture_interval))

            solver_type_changed = new_solver_type.lower() != str(self.solver_type).lower()
            interval_changed = (
                new_min_interval != self.min_solve_interval
                or new_capture_interval != self.capture_interval
            )
            auto_changed = new_auto_solve != self.auto_solve

            # Apply new values
            self.solver_type = new_solver_type
            self.auto_solve = new_auto_solve
            self.min_solve_interval = new_min_interval
            self.capture_interval = new_capture_interval

            # Recreate solver to pick up new settings if autosolve enabled
            if self.auto_solve:
                if solver_type_changed or auto_changed or True:
                    try:
                        solver = PlateSolverFactory.create_solver(
                            self.solver_type, config=self.config, logger=self.logger
                        )
                        if solver and hasattr(solver, "is_available") and solver.is_available():
                            self.plate_solver = solver
                            name = solver.get_name() if hasattr(solver, "get_name") else str(solver)
                            self.logger.info(
                                "Plate solver reinitialized: %s (auto_solve=%s)",
                                name,
                                self.auto_solve,
                            )
                        else:
                            self.logger.warning(
                                "Plate solver not available after reload: %s",
                                self.solver_type,
                            )
                            self.plate_solver = None
                    except Exception as e:
                        self.logger.error(f"Error reinitializing plate solver: {e}")
                        self.plate_solver = None
            else:
                if self.plate_solver is not None:
                    self.logger.info("Auto-solve disabled; releasing plate solver instance")
                self.plate_solver = None

            if interval_changed:
                self.logger.info(
                    "Updated solve/capture interval: min_solve_interval=%ss, capture_interval=%ss",
                    self.min_solve_interval,
                    self.capture_interval,
                )
        except Exception as e:
            try:
                self.logger.debug(f"Failed to refresh plate-solve settings: {e}")
            except Exception:
                pass

    def refresh_frame_processing_settings(self) -> None:
        """Refresh frame-processing options (hot-reload).

        Updates timestamping, file format, and RAW FITS archival options and
        recreates the FrameWriter to pick up orientation/normalization updates.
        """
        try:
            self.frame_config = self.config.get_frame_processing_config()
            self.use_timestamps = bool(self.frame_config.get("use_timestamps", self.use_timestamps))
            self.timestamp_format = str(
                self.frame_config.get("timestamp_format", self.timestamp_format)
            )
            self.use_capture_count = bool(
                self.frame_config.get("use_capture_count", self.use_capture_count)
            )
            self.file_format = str(self.frame_config.get("file_format", self.file_format))
            self.save_raw_fits = bool(
                self.frame_config.get("save_raw_fits", getattr(self, "save_raw_fits", False))
            )
            self.raw_fits_dir = Path(
                self.frame_config.get(
                    "raw_fits_dir", str(getattr(self, "raw_fits_dir", "raw_fits"))
                )
            )

            # Recreate FrameWriter to pick up orientation/normalization changes
            try:
                self.frame_writer = FrameWriter(
                    config=self.config,
                    logger=self.logger,
                    camera=self.video_capture.camera if self.video_capture else None,
                    camera_type=self.video_capture.camera_type if self.video_capture else "opencv",
                )
            except Exception as e:
                try:
                    self.logger.debug(f"Could not recreate FrameWriter on reload: {e}")
                except Exception:
                    pass

            self.logger.info(
                "Frame-processing settings reloaded (timestamps=%s, format=%s, raw_fits=%s)",
                str(self.use_timestamps),
                self.file_format,
                str(self.save_raw_fits),
            )
        except Exception as e:
            try:
                self.logger.debug(f"Failed to refresh frame-processing settings: {e}")
            except Exception:
                pass

    def _obtain_frame(self):
        """Obtain a frame via one-shot (ASCOM/Alpaca) or current frame (OpenCV)."""
        if not self.video_capture:
            return None
        try:
            cam_type = getattr(self.video_capture, "camera_type", "opencv")
            if cam_type in ["alpaca", "ascom"]:
                # Pass adaptive exposure override to capture controller (if set)
                try:
                    if self.next_exposure_time_override is not None:
                        self.video_capture.next_exposure_time_override = float(
                            self.next_exposure_time_override
                        )
                    else:
                        # Clear previous override
                        if hasattr(self.video_capture, "next_exposure_time_override"):
                            self.video_capture.next_exposure_time_override = None
                except Exception:
                    pass

                status = self.video_capture.capture_single_frame()
                # One-shot override; clear after use
                try:
                    self.next_exposure_time_override = None
                except Exception:
                    pass
                if not status or not getattr(status, "is_success", False):
                    msg = getattr(status, "message", "unknown error")
                    self.logger.warning(f"Single-frame capture failed: {msg}")
                    return None
                return status
            return self.video_capture.get_current_frame()
        except Exception as e:
            self.logger.warning(f"Failed to obtain frame: {e}")
            return None

    def _mount_is_slewing(self) -> bool:
        try:
            if not hasattr(self, "mount") or self.mount is None:
                return False
            st = self.mount.is_slewing()
            return bool(getattr(st, "data", False)) if getattr(st, "is_success", False) else False
        except Exception:
            return False

    def _mount_is_tracking(self) -> Optional[bool]:
        try:
            if not hasattr(self, "mount") or self.mount is None:
                return None
            trk = getattr(self.mount, "is_tracking", None)
            if callable(trk):
                res = trk()
                if hasattr(res, "is_success"):
                    return bool(getattr(res, "data", False)) if res.is_success else None
                return bool(res)
            if trk is not None:
                return bool(trk)
            return None
        except Exception:
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
        # If a mount is available, add current RA/Dec (degrees) to metadata for FITS headers
        try:
            if hasattr(self, "mount") and self.mount is not None:
                mstat = self.mount.get_coordinates()
                if (
                    getattr(mstat, "is_success", False)
                    and isinstance(getattr(mstat, "data", None), (list, tuple))
                    and len(mstat.data) == 2
                ):
                    ra_m, dec_m = float(mstat.data[0]), float(mstat.data[1])
                    # Convert RA hours to degrees if needed
                    if 0.0 <= ra_m <= 24.0:
                        ra_m *= 15.0
                    details_with_id.setdefault("RA", ra_m)
                    details_with_id.setdefault("DEC", dec_m)
        except Exception:
            pass

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

        # Optionally save RAW (non-debayered) FITS with timestamp to separate directory
        try:
            if self.save_raw_fits and self.frame_writer is not None:
                # Extract original undebayered mosaic from Frame wherever available
                image_data, details = unwrap_status(frame)
                raw_data = None
                frame_obj = None
                try:
                    from capture.frame import Frame as _Frame
                except Exception:
                    _Frame = None

                # Try direct Frame
                if _Frame is not None and isinstance(frame, _Frame):
                    frame_obj = frame
                # Try Status-like .data holding Frame
                if frame_obj is None and hasattr(frame, "data"):
                    try:
                        cand = frame.data
                        if _Frame is not None and isinstance(cand, _Frame):
                            frame_obj = cand
                    except Exception:
                        pass
                # Try unwrap result holding Frame
                if frame_obj is None and _Frame is not None and isinstance(image_data, _Frame):
                    frame_obj = image_data

                if frame_obj is not None:
                    try:
                        raw_data = getattr(frame_obj, "raw_data", None)
                    except Exception:
                        raw_data = None
                    if raw_data is None:
                        try:
                            raw_data = getattr(frame_obj, "data", None)
                        except Exception:
                            raw_data = None
                else:
                    # Last resort: use unwrapped image_data directly
                    raw_data = image_data

                # Debug hints
                try:
                    self.logger.debug(
                        "raw save: frame_obj=%s raw_data_shape=%s",
                        type(frame_obj).__name__ if frame_obj is not None else "None",
                        str(getattr(raw_data, "shape", None)),
                    )
                except Exception:
                    pass
                if raw_data is not None:
                    ts = datetime.now().strftime(self.timestamp_format)
                    raw_name_parts = ["raw", ts]
                    if self.use_capture_count:
                        raw_name_parts.append(f"{self.capture_count:04d}")
                    raw_base = "_".join(raw_name_parts)
                    raw_path = self.raw_fits_dir / f"{raw_base}.fits"
                    os.makedirs(self.raw_fits_dir, exist_ok=True)
                    raw_status = self.frame_writer.save_raw_fits(
                        raw_data, str(raw_path), metadata=details_with_id
                    )
                    if getattr(raw_status, "is_success", False):
                        self.logger.info(f"RAW FITS saved: {raw_path}")
                    else:
                        self.logger.warning(
                            "RAW FITS save failed: %s",
                            getattr(raw_status, "message", "No status"),
                        )
        except Exception as e:
            self.logger.debug(f"RAW FITS archival skipped: {e}")

        return frame_filename, fits_filename

    def _maybe_plate_solve(
        self, fits_filename: Optional[Path], frame_filename: Optional[Path]
    ) -> Optional[PlateSolveResult]:
        """Run plate-solving if enabled and interval elapsed; prefer FITS."""
        if not (self.plate_solver and self.auto_solve):
            return None
        if (time.monotonic() - self.last_solve_time) < self.min_solve_interval:
            return None
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
            return None
        # Pre-check: if the Moon is predicted to be inside the FOV (from mount pointing
        # or last plate-solve center + FOV from camera/telescope), skip solving entirely
        # and let the runner render a minimal overlay for this iteration.
        try:
            self.moon_in_fov_predicted = False  # default
            # Compute pointing center
            center_ra_dec = None
            if hasattr(self, "mount") and self.mount is not None:
                try:
                    mstat = self.mount.get_coordinates()
                    if (
                        getattr(mstat, "is_success", False)
                        and isinstance(getattr(mstat, "data", None), (list, tuple))
                        and len(mstat.data) == 2
                    ):
                        ra_val = float(mstat.data[0])
                        dec_val = float(mstat.data[1])
                        # Heuristic: convert RA hours to degrees if it looks like hours
                        if 0.0 <= ra_val <= 24.0:
                            self.logger.debug(
                                "Assuming mount RA is in hours; converting to degrees"
                            )
                            ra_val *= 15.0
                        center_ra_dec = (ra_val, dec_val)
                except Exception:
                    center_ra_dec = None
            if (
                center_ra_dec is None
                and self.last_solve_result is not None
                and isinstance(self.last_solve_result, PlateSolveResult)
            ):
                center_ra_dec = (
                    float(self.last_solve_result.ra_center or 0.0),
                    float(self.last_solve_result.dec_center or 0.0),
                )
            # Fallback: read RA/Dec from FITS header if available
            if center_ra_dec is None and isinstance(fits_filename, Path) and fits_filename.exists():
                try:
                    import astropy.io.fits as _fits

                    with _fits.open(str(fits_filename)) as _hdul:
                        _hdr = _hdul[0].header
                        ra_deg_hdr = _hdr.get("RA")
                        dec_deg_hdr = _hdr.get("DEC")

                        def _parse_sexagesimal(val: str, is_ra: bool) -> float | None:
                            try:
                                txt = str(val).strip().replace(" ", ":").replace("::", ":")
                                parts = [p for p in txt.split(":") if p != ""]
                                if not parts:
                                    return None
                                parts_f = [float(p) for p in parts]
                                if is_ra:
                                    hours = parts_f[0]
                                    minutes = parts_f[1] if len(parts_f) > 1 else 0.0
                                    seconds = parts_f[2] if len(parts_f) > 2 else 0.0
                                    sign = -1.0 if str(val).lstrip().startswith("-") else 1.0
                                    hours_total = sign * (
                                        abs(hours) + minutes / 60.0 + seconds / 3600.0
                                    )
                                    return hours_total * 15.0
                                else:
                                    deg = parts_f[0]
                                    minutes = parts_f[1] if len(parts_f) > 1 else 0.0
                                    seconds = parts_f[2] if len(parts_f) > 2 else 0.0
                                    sign = -1.0 if str(val).lstrip().startswith("-") else 1.0
                                    return sign * (abs(deg) + minutes / 60.0 + seconds / 3600.0)
                            except Exception:
                                return None

                        if ra_deg_hdr is None:
                            ra_txt = _hdr.get("OBJCTRA") or _hdr.get("RA_OBJ") or _hdr.get("TELRA")
                            if isinstance(ra_txt, str):
                                ra_deg_hdr = _parse_sexagesimal(ra_txt, True)
                        if dec_deg_hdr is None:
                            dec_txt = (
                                _hdr.get("OBJCTDEC") or _hdr.get("DEC_OBJ") or _hdr.get("TELDEC")
                            )
                            if isinstance(dec_txt, str):
                                dec_deg_hdr = _parse_sexagesimal(dec_txt, False)
                        # Heuristic: RA header may be hours
                        if (
                            isinstance(ra_deg_hdr, (int, float))
                            and 0.0 <= float(ra_deg_hdr) <= 24.0
                        ):
                            ra_deg_hdr = float(ra_deg_hdr) * 15.0
                        if isinstance(ra_deg_hdr, (int, float)) and isinstance(
                            dec_deg_hdr, (int, float)
                        ):
                            center_ra_dec = (float(ra_deg_hdr), float(dec_deg_hdr))
                            try:
                                self.logger.debug(
                                    "Moon precheck using FITS header center RA=%.5f Dec=%.5f",
                                    center_ra_dec[0],
                                    center_ra_dec[1],
                                )
                            except Exception:
                                pass
                except Exception:
                    pass
            # Compute half diagonal FOV from config
            half_diag_deg = 0.0
            try:
                tel_cfg = self.config.get_telescope_config()
                cam_cfg = self.config.get_camera_config()
                focal_length_mm = float(tel_cfg.get("focal_length", 1000.0))
                sensor_w_mm = float(cam_cfg.get("sensor_width", 13.2))
                sensor_h_mm = float(cam_cfg.get("sensor_height", 8.8))
                import math as _math

                fov_w = 2.0 * _math.degrees(_math.atan((sensor_w_mm / 2.0) / focal_length_mm))
                fov_h = 2.0 * _math.degrees(_math.atan((sensor_h_mm / 2.0) / focal_length_mm))
                half_diag_deg = ((_math.pow(fov_w, 2) + _math.pow(fov_h, 2)) ** 0.5) / 2.0
            except Exception:
                half_diag_deg = 0.0
            if center_ra_dec is not None and half_diag_deg > 0.0:
                try:
                    from astropy.coordinates import (
                        EarthLocation,
                        SkyCoord,
                        get_body,
                        solar_system_ephemeris,
                    )
                    from astropy.time import Time
                    import astropy.units as u
                except Exception:
                    pass
                else:
                    # Observation time
                    try:
                        ts = None
                        if isinstance(self.last_frame_metadata, dict):
                            ts = (
                                self.last_frame_metadata.get("date_obs")
                                or self.last_frame_metadata.get("DATE-OBS")
                                or self.last_frame_metadata.get("capture_started_at")
                            )
                        obstime = Time(ts) if ts else Time.now()
                    except Exception:
                        obstime = Time.now()
                    # Location
                    try:
                        site_cfg = None
                        if hasattr(self.config, "get_site_config"):
                            site_cfg = self.config.get_site_config()
                        if not site_cfg:
                            ovl = (
                                self.config.get_overlay_config()
                                if hasattr(self.config, "get_overlay_config")
                                else {}
                            )
                            site_cfg = ovl.get("site", {}) if isinstance(ovl, dict) else {}
                        lat_raw = site_cfg.get("latitude")
                        lon_raw = site_cfg.get("longitude")
                        elev_raw = site_cfg.get("elevation_m", 0.0)
                        lat = float(lat_raw) if lat_raw is not None else 0.0
                        lon = float(lon_raw) if lon_raw is not None else 0.0
                        elev = float(elev_raw) if elev_raw is not None else 0.0
                        location = EarthLocation(
                            lat=lat * u.deg, lon=lon * u.deg, height=elev * u.m
                        )
                    except Exception:
                        location = None
                    # Center coordinate
                    center = SkyCoord(
                        ra=center_ra_dec[0] * u.deg, dec=center_ra_dec[1] * u.deg, frame="icrs"
                    )
                    try:
                        solar_system_ephemeris.set("de432s")
                    except Exception:
                        pass
                    try:
                        moon_coord = get_body("moon", obstime, location=location)
                        sep = moon_coord.icrs.separation(center).degree
                        if sep <= half_diag_deg:
                            self.moon_in_fov_predicted = True
                            try:
                                self.logger.info(
                                    "Moon predicted in FOV (sep=%.3f°) center=(%.4f,%.4f)",
                                    sep,
                                    center_ra_dec[0],
                                    center_ra_dec[1],
                                )
                            except Exception:
                                pass
                        else:
                            try:
                                self.logger.debug(
                                    "Moon OUT of FOV (sep=%.3f°) halfdiag=%.3f° center=(%.4f,%.4f)",
                                    sep,
                                    half_diag_deg,
                                    center_ra_dec[0],
                                    center_ra_dec[1],
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
            # If Moon predicted in FOV, skip solving now
            if getattr(self, "moon_in_fov_predicted", False):
                self.logger.info("Moon predicted in FOV; skipping plate-solve for this frame")
                self.last_solve_time = time.monotonic()
                return None
        except Exception as _e:
            self.logger.debug(f"Moon pre-check failed: {_e}")

        # Always proceed to solving. If using astrometry_local and a FITS exists,
        # optionally write a masked copy with the central region set to zero to
        # avoid planets being detected as stars. Masking is applied only if a
        # solar-system object is predicted to be inside the FOV (based on the
        # mount pointing or the last successful solution center + FOV).
        try:
            if candidate and candidate.suffix.lower() in {".fits", ".fit", ".fts"}:
                ps_cfg = self.config.get_plate_solve_config()
                ast_local_cfg = (
                    ps_cfg.get("astrometry_local", {}) if isinstance(ps_cfg, dict) else {}
                )
                if str(getattr(self, "solver_type", "")).lower() == "astrometry_local" and bool(
                    ast_local_cfg.get("mask_center_on_solve", False)
                ):
                    should_mask = False
                    # Predict presence of SS object near pointing center using mount
                    try:
                        from astropy.coordinates import (
                            EarthLocation,
                            SkyCoord,
                            get_body,
                            solar_system_ephemeris,
                        )
                        from astropy.time import Time
                        import astropy.units as u
                    except Exception:
                        should_mask = False
                    else:
                        center = None
                        half_diag = 0.0
                        # 1) Mount coordinates if available
                        try:
                            if hasattr(self, "mount") and self.mount is not None:
                                mstat = self.mount.get_coordinates()
                                if (
                                    getattr(mstat, "is_success", False)
                                    and isinstance(getattr(mstat, "data", None), (list, tuple))
                                    and len(mstat.data) == 2
                                ):
                                    ra_deg, dec_deg = float(mstat.data[0]), float(mstat.data[1])
                                    center = SkyCoord(
                                        ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs"
                                    )
                        except Exception:
                            center = None
                        # Compute FOV from telescope and camera config
                        try:
                            tel_cfg = self.config.get_telescope_config()
                            focal_length_mm = float(tel_cfg.get("focal_length", 1000.0))
                            cam_cfg = self.config.get_camera_config()
                            sensor_w_mm = float(cam_cfg.get("sensor_width", 13.2))
                            sensor_h_mm = float(cam_cfg.get("sensor_height", 8.8))
                            import math as _math

                            fov_w = 2.0 * _math.degrees(
                                _math.atan((sensor_w_mm / 2.0) / focal_length_mm)
                            )
                            fov_h = 2.0 * _math.degrees(
                                _math.atan((sensor_h_mm / 2.0) / focal_length_mm)
                            )
                            half_diag = ((_math.pow(fov_w, 2) + _math.pow(fov_h, 2)) ** 0.5) / 2.0
                        except Exception:
                            half_diag = 0.0
                        # 2) Fallback to last plate-solve if mount not available
                        if (
                            center is None
                            and self.last_solve_result is not None
                            and isinstance(self.last_solve_result, PlateSolveResult)
                        ):
                            center = SkyCoord(
                                ra=(self.last_solve_result.ra_center or 0.0) * u.deg,
                                dec=(self.last_solve_result.dec_center or 0.0) * u.deg,
                                frame="icrs",
                            )
                            if half_diag <= 0.0:
                                half_diag = (
                                    ((self.last_solve_result.fov_width or 0.0) ** 2)
                                    + ((self.last_solve_result.fov_height or 0.0) ** 2)
                                ) ** 0.5 / 2.0
                        if center is not None and half_diag > 0.0:
                            # Observation time from metadata or now
                            try:
                                ts = None
                                if isinstance(self.last_frame_metadata, dict):
                                    ts = (
                                        self.last_frame_metadata.get("date_obs")
                                        or self.last_frame_metadata.get("DATE-OBS")
                                        or self.last_frame_metadata.get("capture_started_at")
                                    )
                                obstime = Time(ts) if ts else Time.now()
                            except Exception:
                                obstime = Time.now()
                            # Location from config (fallback geocenter)
                            try:
                                site_cfg = None
                                if hasattr(self.config, "get_site_config"):
                                    site_cfg = self.config.get_site_config()
                                if not site_cfg:
                                    ovl = (
                                        self.config.get_overlay_config()
                                        if hasattr(self.config, "get_overlay_config")
                                        else {}
                                    )
                                    site_cfg = ovl.get("site", {}) if isinstance(ovl, dict) else {}
                                lat_raw = site_cfg.get("latitude")
                                lon_raw = site_cfg.get("longitude")
                                elev_raw = site_cfg.get("elevation_m", 0.0)
                                lat = float(lat_raw) if lat_raw is not None else 0.0
                                lon = float(lon_raw) if lon_raw is not None else 0.0
                                elev = float(elev_raw) if elev_raw is not None else 0.0
                                location = EarthLocation(
                                    lat=lat * u.deg, lon=lon * u.deg, height=elev * u.m
                                )
                            except Exception:
                                location = None
                            # Bodies to check
                            bodies = [
                                "moon",
                                "mercury",
                                "venus",
                                "mars",
                                "jupiter",
                                "saturn",
                                "uranus",
                                "neptune",
                            ]
                            try:
                                solar_system_ephemeris.set("de432s")
                            except Exception:
                                pass
                            mask_body: Optional[str] = None
                            mask_sep: Optional[float] = None
                            for b in bodies:
                                try:
                                    coord = (
                                        get_body("moon", obstime, location=location)
                                        if b == "moon"
                                        else get_body(b, obstime, location=location)
                                    )
                                    sep = coord.icrs.separation(center).degree
                                    if sep <= half_diag:
                                        should_mask = True
                                        mask_body = b
                                        mask_sep = float(sep)
                                        break
                                except Exception:
                                    continue
                    if should_mask:
                        masked = self._create_center_masked_fits(candidate, ast_local_cfg)
                        if masked is not None:
                            try:
                                if mask_body is not None and mask_sep is not None:
                                    self.logger.info(
                                        "Center-masking due to bright SS body: %s (sep=%.3f°)",
                                        mask_body,
                                        mask_sep,
                                    )
                            except Exception:
                                pass
                            self.logger.info(f"Using center-masked FITS for solving: {masked}")
                            candidate = masked
        except Exception as _e:
            # Proceed without masking on any error
            self.logger.debug(f"Center-masking skipped due to error: {_e}")

        result = self._solve_frame(str(candidate))
        # Update last_solve_time only after the attempt completes
        self.last_solve_time = time.monotonic()
        # Adaptive exposure heuristic for bright solar system targets (Moon/planets)
        try:
            if result and isinstance(result, PlateSolveResult):
                # Use astropy to check whether a bright SS object is in FOV
                try:
                    from astropy.coordinates import (
                        EarthLocation,
                        SkyCoord,
                        get_body,
                        solar_system_ephemeris,
                    )
                    from astropy.time import Time
                    import astropy.units as u
                except Exception:
                    solar_present = False
                else:
                    # Observation time
                    try:
                        ts = None
                        if isinstance(self.last_frame_metadata, dict):
                            ts = (
                                self.last_frame_metadata.get("date_obs")
                                or self.last_frame_metadata.get("DATE-OBS")
                                or self.last_frame_metadata.get("capture_started_at")
                            )
                        obstime = Time(ts) if ts else Time.now()
                    except Exception:
                        obstime = Time.now()

                    # Location (fallback to geocenter if not configured)
                    try:
                        # Allow both get_site_config() or overlay.site
                        site_cfg = None
                        if hasattr(self.config, "get_site_config"):
                            site_cfg = self.config.get_site_config()
                        if not site_cfg:
                            ovl = (
                                self.config.get_overlay_config()
                                if hasattr(self.config, "get_overlay_config")
                                else {}
                            )
                            site_cfg = ovl.get("site", {}) if isinstance(ovl, dict) else {}
                        lat_raw = site_cfg.get("latitude")
                        lon_raw = site_cfg.get("longitude")
                        elev_raw = site_cfg.get("elevation_m", 0.0)
                        lat = float(lat_raw) if lat_raw is not None else 0.0
                        lon = float(lon_raw) if lon_raw is not None else 0.0
                        elev = float(elev_raw) if elev_raw is not None else 0.0
                        location = EarthLocation(
                            lat=lat * u.deg, lon=lon * u.deg, height=elev * u.m
                        )
                    except Exception:
                        location = None

                    # FOV half-diagonal
                    half_diag = (
                        (result.fov_width or 0.0) ** 2 + (result.fov_height or 0.0) ** 2
                    ) ** 0.5 / 2.0
                    center = SkyCoord(
                        ra=(result.ra_center or 0.0) * u.deg,
                        dec=(result.dec_center or 0.0) * u.deg,
                        frame="icrs",
                    )

                    # Check common bright bodies
                    solar_present = False
                    detected_body: Optional[str] = None
                    detected_sep: Optional[float] = None
                    bodies = [
                        "moon",
                        "mercury",
                        "venus",
                        "mars",
                        "jupiter",
                        "saturn",
                        "uranus",
                        "neptune",
                    ]
                    try:
                        solar_system_ephemeris.set("de432s")
                    except Exception:
                        pass
                    for b in bodies:
                        try:
                            coord = (
                                get_body("moon", obstime, location=location)
                                if b == "moon"
                                else get_body(b, obstime, location=location)
                            )
                            sep = coord.icrs.separation(center).degree
                            if sep <= half_diag:
                                solar_present = True
                                detected_body = b
                                detected_sep = float(sep)
                                break
                        except Exception:
                            continue

                if solar_present:
                    try:
                        if detected_body is not None and detected_sep is not None:
                            self.logger.info(
                                "Bright solar-system body in FOV: %s (sep=%.3f°)",
                                detected_body,
                                detected_sep,
                            )
                    except Exception:
                        pass
                    # Use conservative cap of 0.01s unless already shorter
                    try:
                        ovl = (
                            self.config.get_overlay_config()
                            if hasattr(self.config, "get_overlay_config")
                            else {}
                        )
                        solar_cfg = ovl.get("solar_system", {}) if isinstance(ovl, dict) else {}
                        cap_s = float(solar_cfg.get("bright_exposure_cap_s", 0.01))
                    except Exception:
                        cap_s = 0.01
                    # Only apply if current was longer than cap
                    if isinstance(self.last_frame_metadata, dict):
                        cur_exp = self.last_frame_metadata.get(
                            "exposure_time_s"
                        ) or self.last_frame_metadata.get("exposure_time")
                        try:
                            cur_exp_f = float(cur_exp) if cur_exp is not None else None
                        except Exception:
                            cur_exp_f = None
                    else:
                        cur_exp_f = None
                    if cur_exp_f is None or cur_exp_f > cap_s:
                        self.next_exposure_time_override = cap_s
                        # Define a fallback window to reuse last good solve if
                        # subsequent solves fail
                        try:
                            ovl = (
                                self.config.get_overlay_config()
                                if hasattr(self.config, "get_overlay_config")
                                else {}
                            )
                            solar_cfg = ovl.get("solar_system", {}) if isinstance(ovl, dict) else {}
                            window_s = float(solar_cfg.get("bright_override_window_s", 120.0))
                        except Exception:
                            window_s = 120.0
                        try:
                            self.solar_bright_override_until = time.monotonic() + float(window_s)
                        except Exception:
                            self.solar_bright_override_until = time.monotonic() + 120.0
                        self.logger.info(
                            "Adaptive exposure: applying bright target cap to %.4fs (was %s)",
                            cap_s,
                            str(cur_exp_f),
                        )
        except Exception:
            pass
        # If we have a callback, it will be triggered in _solve_frame on success
        return result

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

            # Additional gating: require tracking ON if configured
            if self.gating_require_tracking:
                tracking = self._mount_is_tracking()
                if tracking is False:
                    self.logger.info("Tracking is OFF; skipping capture per configuration")
                    return

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

            # Post-capture gating: discard if mount started slewing or lost tracking
            try:
                should_discard = False
                if self.gating_block_during_slew and self._mount_is_slewing():
                    self.logger.info("Discarding capture due to slewing detected post-capture")
                    should_discard = True
                if self.gating_require_tracking:
                    tracking = self._mount_is_tracking()
                    if tracking is False:
                        self.logger.info("Discarding capture due to tracking OFF post-capture")
                        should_discard = True
                if should_discard:
                    try:
                        if frame_filename and frame_filename.exists():
                            # Python 3.8+: missing_ok available; otherwise fallback below
                            try:
                                frame_filename.unlink(missing_ok=True)
                            except TypeError:
                                os.remove(frame_filename)
                    except TypeError:
                        # Python <3.8 without missing_ok
                        try:
                            if frame_filename and frame_filename.exists():
                                os.remove(frame_filename)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    try:
                        if fits_filename and fits_filename.exists():
                            try:
                                fits_filename.unlink(missing_ok=True)
                            except TypeError:
                                os.remove(fits_filename)
                    except TypeError:
                        try:
                            if fits_filename and fits_filename.exists():
                                os.remove(fits_filename)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Record discard reason for runner to annotate status
                    try:
                        reason = "Discarding capture due to slewing detected post-capture"
                        if self.gating_require_tracking and tracking is False:
                            reason = "Discarding capture due to tracking OFF post-capture"
                        self.last_discard_message = reason
                        self.last_discard_time = time.time()
                    except Exception:
                        pass
                    # Skip plate solving for discarded capture
                    return
            except Exception:
                pass

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

        # Extract data from status with robust defaults
        raw_data = status.data if hasattr(status, "data") else None
        data = raw_data if isinstance(raw_data, dict) else {}
        raw_details = status.details if hasattr(status, "details") else None
        details = raw_details if isinstance(raw_details, dict) else {}

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
        method = details.get("method", "unknown") if isinstance(details, dict) else "unknown"
        confidence = (
            safe_float(data.get("confidence")) if data.get("confidence") is not None else None
        )
        position_angle = (
            safe_float(data.get("position_angle"))
            if data.get("position_angle") is not None
            else None
        )
        image_size = data.get("image_size")  # Keep as tuple, no conversion needed
        # Optional WCS path for downstream WCS-based projection
        try:
            wcs_path = str(data.get("wcs_path")) if data.get("wcs_path") else None
        except Exception:
            wcs_path = None
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
            wcs_path=wcs_path,
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
                raw_details = status.details if hasattr(status, "details") else None
                details = raw_details if isinstance(raw_details, dict) else {}
                solving_time = details.get("solving_time", 0)

                self.logger.warning(f"Plate-solving failed after {solving_time:.2f}s: {error_msg}")
                self.logger.info(
                    "Continuing with next exposure - conditions may improve for next attempt"
                )

                # Check if this is a "no stars" or "poor conditions" failure and within
                # bright-target short-exposure window; if so, fall back to last good solve
                no_stars = "no_stars" in error_msg.lower() or "no stars" in error_msg.lower()
                poor_cond = "poor_conditions" in str(details).lower()
                within_bright_window = False
                try:
                    within_bright_window = (
                        self.solar_bright_override_until is not None
                        and time.monotonic() <= float(self.solar_bright_override_until)
                    )
                except Exception:
                    within_bright_window = False

                if (no_stars or poor_cond) and within_bright_window and self.last_solve_result:
                    self.logger.info(
                        "Using last successful plate-solve result due to short exposure"
                    )
                    result = self.last_solve_result
                else:
                    if no_stars or poor_cond:
                        self.logger.info(
                            "Failure likely due to poor seeing/short exposure; will retry later",
                        )

            self.last_solve_time = time.time()
            return result

        except Exception as e:
            self.logger.error(f"Error in plate-solving: {e}")
            if self.on_error:
                self.on_error(e)
            return None

    def _create_center_masked_fits(
        self, fits_path: Path, astrometry_cfg: dict[str, Any]
    ) -> Optional[Path]:
        """Create a temporary FITS with central region zeroed for astrometry.

        The central rectangle size is defined by fraction parameters; defaults to 0.2 (20%).
        The masked file is written next to the original with suffix `_masked.fits`.
        """
        try:
            from astropy.io import fits as _fits
            import numpy as _np
        except Exception:
            return None

        try:
            frac = float(astrometry_cfg.get("mask_center_fraction", 0.2))
            frac = max(0.0, min(frac, 0.9))
        except Exception:
            frac = 0.2

        try:
            with _fits.open(str(fits_path), mode="readonly") as hdul:
                # Assume primary HDU contains image
                hdu = None
                for cand in hdul:
                    if getattr(cand, "data", None) is not None:
                        hdu = cand
                        break
                if hdu is None:
                    return None
                data = _np.array(hdu.data, copy=True)
                if data.ndim == 3:
                    # If stacked cube, mask the middle slice only to
                    # preserve edges; else mask all planes
                    try:
                        mid = data.shape[0] // 2
                        planes = [mid]
                    except Exception:
                        planes = list(range(data.shape[0]))
                    for p in planes:
                        self._mask_center_inplace(data[p], frac)
                elif data.ndim == 2:
                    self._mask_center_inplace(data, frac)
                else:
                    return None
                # Write masked file
                out_path = fits_path.with_name(f"{fits_path.stem}_masked.fits")
                hdu_out = _fits.PrimaryHDU(data=data, header=hdu.header)
                hdul_out = _fits.HDUList([hdu_out])
                # Avoid overwriting original
                hdul_out.writeto(str(out_path), overwrite=True)
                return out_path
        except Exception as e:
            self.logger.debug(f"Center masking failed: {e}")
            return None

    def _mask_center_inplace(self, arr: Any, fraction: float) -> None:
        """Zero the central rectangle of the given 2D array in-place.

        fraction defines the width/height of the mask relative to image size.
        """
        try:
            pass
        except Exception:
            return
        if not hasattr(arr, "shape") or len(arr.shape) != 2:
            return
        height, width = int(arr.shape[0]), int(arr.shape[1])
        if height <= 0 or width <= 0:
            return
        mask_w = max(1, int(width * fraction))
        mask_h = max(1, int(height * fraction))
        x0 = (width - mask_w) // 2
        y0 = (height - mask_h) // 2
        arr[y0 : y0 + mask_h, x0 : x0 + mask_w] = 0

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

                # Optional: resize final combined image per overlay config
                try:
                    ov_cfg = (
                        self.config.get_overlay_config()
                        if hasattr(self.config, "get_overlay_config")
                        else {}
                    )
                    combined_cfg = (
                        ov_cfg.get("combined_output", {}) if isinstance(ov_cfg, dict) else {}
                    )
                    if bool(combined_cfg.get("enabled", False)):
                        target = combined_cfg.get("resolution", [1920, 1080])
                        if isinstance(target, (list, tuple)) and len(target) == 2:
                            target_w = int(target[0])
                            target_h = int(target[1])
                            mode = str(combined_cfg.get("mode", "letterbox")).lower()
                            resample_name = str(combined_cfg.get("resample", "lanczos")).lower()
                            bg = combined_cfg.get("background_color", [0, 0, 0])
                            try:
                                bg_tuple = (
                                    int(bg[0]),
                                    int(bg[1]),
                                    int(bg[2]),
                                )
                            except Exception:
                                bg_tuple = (0, 0, 0)

                            # Map resample names
                            from PIL import Image as _PILImage

                            resample_map = {
                                "nearest": _PILImage.Resampling.NEAREST,
                                "bilinear": _PILImage.Resampling.BILINEAR,
                                "bicubic": _PILImage.Resampling.BICUBIC,
                                "lanczos": _PILImage.Resampling.LANCZOS,
                            }
                            resample_filter = resample_map.get(
                                resample_name, _PILImage.Resampling.LANCZOS
                            )

                            src_w, src_h = composite_rgb.size
                            if (
                                target_w > 0
                                and target_h > 0
                                and (src_w != target_w or src_h != target_h)
                            ):
                                if mode == "stretch":
                                    composite_rgb = composite_rgb.resize(
                                        (target_w, target_h), resample=resample_filter
                                    )
                                elif mode == "crop":
                                    # Scale to cover, then center-crop to target
                                    scale = max(target_w / src_w, target_h / src_h)
                                    new_w = max(1, int(round(src_w * scale)))
                                    new_h = max(1, int(round(src_h * scale)))
                                    tmp = composite_rgb.resize(
                                        (new_w, new_h), resample=resample_filter
                                    )
                                    left = max(0, (new_w - target_w) // 2)
                                    top = max(0, (new_h - target_h) // 2)
                                    composite_rgb = tmp.crop(
                                        (left, top, left + target_w, top + target_h)
                                    )
                                else:
                                    # letterbox: fit inside and pad with bg
                                    scale = min(target_w / src_w, target_h / src_h)
                                    new_w = max(1, int(round(src_w * scale)))
                                    new_h = max(1, int(round(src_h * scale)))
                                    tmp = composite_rgb.resize(
                                        (new_w, new_h), resample=resample_filter
                                    )
                                    canvas = _PILImage.new(
                                        "RGB", (target_w, target_h), color=bg_tuple
                                    )
                                    off_x = (target_w - new_w) // 2
                                    off_y = (target_h - new_h) // 2
                                    canvas.paste(tmp, (off_x, off_y))
                                    composite_rgb = canvas
                except Exception as _resize_e:
                    # Keep original size if anything goes wrong
                    self.logger.debug(f"Combined resize skipped: {_resize_e}")

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

            # Check timestamps preference (overlay config may override)
            use_timestamps = bool(self.frame_config.get("use_timestamps", False))
            try:
                ov_cfg = (
                    self.config.get_overlay_config()
                    if hasattr(self.config, "get_overlay_config")
                    else {}
                )
                if isinstance(ov_cfg, dict):
                    use_timestamps = bool(ov_cfg.get("use_timestamps", use_timestamps))
            except Exception:
                pass

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
