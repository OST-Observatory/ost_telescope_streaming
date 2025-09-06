#!/usr/bin/env python3
"""
Video capture module for telescope streaming system.
Handles video capture, frame processing, calibration metadata, and cooling lifecycle.
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional

from calibration_applier import CalibrationApplier
from capture.adapters import AlpacaCameraAdapter, AscomCameraAdapter, OpenCVCameraAdapter
from capture.frame import Frame
from capture.settings import CameraSettings
from status import CameraStatus, error_status, success_status, warning_status
from utils.status_utils import unwrap_status


class VideoCapture:
    """Video capture class for telescope streaming."""

    def __init__(
        self,
        config,
        logger: Optional[logging.Logger] = None,
        enable_calibration: bool = True,
        return_frame_objects: bool = False,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Camera/config state
        frame_config = config.get_frame_processing_config()
        camera_cfg = config.get_camera_config()
        self.camera_type = camera_cfg.get("camera_type", "opencv")
        self.camera_index = camera_cfg.get("opencv", {}).get("camera_index", 0)
        self.exposure_time = camera_cfg.get("opencv", {}).get("exposure_time", 1.0)
        self.gain = camera_cfg.get("ascom", {}).get("gain", 100.0)
        self.offset = camera_cfg.get("ascom", {}).get("offset", 50.0)
        self.readout_mode = camera_cfg.get("ascom", {}).get("readout_mode", 0)
        self.binning = camera_cfg.get("ascom", {}).get("binning", 1)
        self.frame_rate = camera_cfg.get("opencv", {}).get("fps", 30)
        self.resolution = camera_cfg.get("opencv", {}).get("resolution", [1920, 1080])
        self.frame_enabled = frame_config.get("enabled", True)

        # Cooling configuration
        cooling_config = camera_cfg.get("cooling", {})
        self.enable_cooling = cooling_config.get("enable_cooling", False)
        self.wait_for_cooling = cooling_config.get("wait_for_cooling", True)
        self.cooling_timeout = cooling_config.get("cooling_timeout", 300)

        # Runtime camera handles
        self.camera: Any = None
        self.cap: Any = None
        self.cooling_manager: Any = None

        # Threading and state
        self.is_capturing = False
        self.capture_thread: Optional[threading.Thread] = None
        self.current_frame: Optional[Any] = None
        self.frame_lock = threading.Lock()

        # Calibration
        self.enable_calibration = enable_calibration
        self.return_frame_objects = return_frame_objects
        if enable_calibration:
            self.calibration_applier = CalibrationApplier(config, logger)
        else:
            self.calibration_applier = None
            self.logger.info("Calibration disabled for this session")

        # Setup
        self._ensure_directories()
        init_status = self._initialize_camera()
        if not init_status.is_success:
            self.logger.warning(f"Camera initialization: {init_status.message}")
        # Reusable writer instance
        try:
            from services.frame_writer import FrameWriter

            self._frame_writer = FrameWriter(
                self.config, logger=self.logger, camera=self.camera, camera_type=self.camera_type
            )
        except Exception:
            self._frame_writer = None
        if self.enable_cooling:
            try:
                from services.cooling.service import CoolingService

                self.cooling_service = CoolingService(self.config, logger=self.logger)
                camera_obj: Optional[Any] = self.camera
                if camera_obj is not None:
                    self.cooling_service.initialize(camera_obj)
            except Exception as e:
                self.logger.warning(f"Cooling service unavailable: {e}")

    def _ensure_directories(self) -> None:
        try:
            output_dir = Path(
                self.config.get_frame_processing_config().get("output_dir", "captured_frames")
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            cache_dir = Path("cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.warning(f"Failed to create output directories: {e}")

    def _initialize_camera(self) -> CameraStatus:
        if self.camera_type == "opencv":
            try:
                import cv2 as _cv2  # local import to avoid hard dependency at import time
            except Exception:
                return error_status("OpenCV (cv2) not available")
            self.cap = _cv2.VideoCapture(self.camera_index)
            if self.cap is None or not self.cap.isOpened():
                return error_status(
                    f"Failed to open camera {self.camera_index}",
                    details={"camera_index": self.camera_index},
                )
            self.cap.set(_cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(_cv2.CAP_PROP_FPS, self.frame_rate)
            if not self.enable_cooling:
                self.cap.set(_cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                exposure_cv = int(self.exposure_time * 1_000_000)
                self.cap.set(_cv2.CAP_PROP_EXPOSURE, exposure_cv)
            if hasattr(_cv2, "CAP_PROP_GAIN"):
                try:
                    self.cap.set(_cv2.CAP_PROP_GAIN, float(self.gain))
                except Exception:
                    pass
            # Wrap in unified adapter for OpenCV
            self.camera = OpenCVCameraAdapter(self.cap)
            return success_status("Camera connected", details={"camera_index": self.camera_index})

        elif self.camera_type == "ascom":
            cam_cfg = self.config.get_camera_config()
            self.ascom_driver = cam_cfg.get("ascom_driver", None)
            if not self.ascom_driver:
                return error_status("ASCOM driver ID not configured")
            # Lazy import to avoid import-time dependency in environments without ASCOM
            from drivers.ascom.camera import ASCOMCamera

            cam = ASCOMCamera(driver_id=self.ascom_driver, config=self.config, logger=self.logger)
            status = cam.connect()
            if status.is_success:
                # Preconfigure subframe on the underlying ASCOM camera
                try:
                    native_width = cam.camera.CameraXSize
                    native_height = cam.camera.CameraYSize
                    ascom_config = self.config.get_camera_config().get("ascom", {})
                    binning = ascom_config.get("binning", 1)
                    self.resolution[0] = native_width // binning
                    self.resolution[1] = native_height // binning
                    cam.camera.NumX = self.resolution[0]
                    cam.camera.NumY = self.resolution[1]
                    cam.camera.StartX = 0
                    cam.camera.StartY = 0
                except Exception as e:
                    self.logger.warning(f"Could not get camera dimensions: {e}, using defaults")
                    self.resolution[0] = 1920
                    self.resolution[1] = 1080
                # Wrap in unified adapter
                self.camera = AscomCameraAdapter(cam)
                return success_status(
                    "ASCOM camera connected", details={"driver": self.ascom_driver}
                )
            else:
                self.camera = None
                return error_status(
                    f"ASCOM camera connection failed: {status.message}",
                    details={"driver": self.ascom_driver},
                )

        elif self.camera_type == "alpaca":
            cam_cfg = self.config.get_camera_config()
            self.alpaca_host = cam_cfg.get("alpaca_host", "localhost")
            self.alpaca_port = cam_cfg.get("alpaca_port", 11111)
            self.alpaca_device_id = cam_cfg.get("alpaca_device_id", 0)
            self.alpaca_camera_name = cam_cfg.get("alpaca_camera_name", "Unknown")
            # Lazy import to avoid import-time dependency if alpaca lib is not installed
            from drivers.alpaca.camera import AlpycaCameraWrapper

            cam = AlpycaCameraWrapper(
                self.alpaca_host, self.alpaca_port, self.alpaca_device_id, self.config, self.logger
            )
            status = cam.connect()
            if status.is_success:
                self.camera = AlpacaCameraAdapter(cam)
                return success_status(
                    "Alpaca camera connected",
                    details={
                        "host": self.alpaca_host,
                        "port": self.alpaca_port,
                        "camera_name": self.alpaca_camera_name,
                    },
                )
            else:
                self.camera = None
                return error_status(
                    f"Alpaca camera connection failed: {status.message}",
                    details={
                        "host": self.alpaca_host,
                        "port": self.alpaca_port,
                        "camera_name": self.alpaca_camera_name,
                    },
                )
        else:
            return error_status(f"Unsupported camera type: {self.camera_type}")

    def _initialize_cooling(self) -> CameraStatus:
        if not self.enable_cooling:
            return success_status("Cooling not enabled")
        if not self.cooling_manager:
            return error_status("Cooling manager not initialized")
        try:
            target_temp = (
                self.config.get_camera_config().get("cooling", {}).get("target_temperature", -10.0)
            )
            status = self.cooling_manager.set_target_temperature(target_temp)
            if not status.is_success:
                return status
            if self.wait_for_cooling:
                stabilization_status = self.cooling_manager.wait_for_stabilization(
                    timeout=self.cooling_timeout
                )
                if not stabilization_status.is_success:
                    msg = (
                        "Cooling initialized but stabilization failed: "
                        f"{stabilization_status.message}"
                    )
                    return warning_status(msg)
            return success_status("Cooling initialized successfully")
        except Exception as e:
            return error_status(f"Failed to initialize cooling: {e}")

    def start_observation_session(self) -> CameraStatus:
        try:
            if self.enable_cooling:
                try:
                    from services.cooling.service import CoolingService

                    # Ensure service exists and initialized
                    if not hasattr(self, "cooling_service") or self.cooling_service is None:
                        self.cooling_service = CoolingService(self.config, logger=self.logger)
                        if self.camera:
                            self.cooling_service.initialize(self.camera)
                    target_temp = (
                        self.config.get_camera_config()
                        .get("cooling", {})
                        .get("target_temperature", -10.0)
                    )
                    status = self.cooling_service.initialize_and_stabilize(
                        target_temp=target_temp,
                        wait_for_cooling=self.wait_for_cooling,
                        timeout_s=self.cooling_timeout,
                    )
                    if not status.is_success:
                        return status
                except Exception as e:
                    return error_status(f"Cooling initialization failed: {e}")
            if self.enable_calibration and self.calibration_applier:
                calibration_status = self.calibration_applier.load_master_frames()
                if not calibration_status.is_success:
                    self.logger.warning(f"Calibration initialization: {calibration_status.message}")
            else:
                self.logger.info("Calibration skipped (disabled for this session)")
            return success_status("Observation session started successfully")
        except Exception as e:
            return error_status(f"Failed to start observation session: {e}")

    def end_observation_session(self) -> CameraStatus:
        try:
            if (
                hasattr(self, "cooling_service")
                and getattr(self, "cooling_service", None)
                and self.cooling_service.is_cooling
            ):
                warmup_status = self.cooling_service.start_warmup()
                if not warmup_status.is_success:
                    self.logger.warning(f"Warmup start: {warmup_status.message}")
            return success_status("Observation session ended successfully")
        except Exception as e:
            return error_status(f"Failed to end observation session: {e}")

    def get_cooling_status(self) -> Dict[str, Any]:
        if not self.cooling_manager:
            return {"error": "Cooling manager not available"}
        status = self.cooling_manager.get_cooling_status()
        return status if isinstance(status, dict) else {"error": "Invalid cooling status"}

    def get_field_of_view(self) -> tuple[float, float]:
        try:
            sensor_width = float(self.config.get_camera_config().get("sensor_width", 6.17))
            sensor_height = float(self.config.get_camera_config().get("sensor_height", 4.55))
            focal_length = float(self.config.get_telescope_config().get("focal_length", 1000))
            fov_width = (sensor_width / focal_length) * (180 / 3.14159)
            fov_height = (sensor_height / focal_length) * (180 / 3.14159)
            return (fov_width, fov_height)
        except Exception:
            return (1.5, 1.0)

    def get_sampling_arcsec_per_pixel(self) -> float:
        try:
            pixel_size = float(self.config.get_camera_config().get("pixel_size", 3.75))
            focal_length = float(self.config.get_telescope_config().get("focal_length", 1000))
            pixel_size_mm = pixel_size / 1000
            sampling = (pixel_size_mm / focal_length) * 206265
            return sampling
        except Exception:
            return 1.0

    def disconnect(self) -> None:
        if self.camera_type == "opencv":
            if self.cap:
                self.cap.release()
                self.cap = None
        elif self.camera_type == "ascom":
            if self.camera:
                self.camera.disconnect()
                self.camera = None
        elif self.camera_type == "alpaca":
            if self.camera:
                self.camera.disconnect()
                self.camera = None
        self.logger.info("Camera disconnected")

    # Legacy shims removed: use start_capture()/disconnect() and adapter-provided info

    def start_capture(self) -> CameraStatus:
        if self.camera_type == "opencv":
            if self.cap is None or not self.cap.isOpened():
                init_status = self._initialize_camera()
                if not getattr(init_status, "is_success", False):
                    return error_status(
                        "Failed to connect to camera", details={"camera_index": self.camera_index}
                    )
        elif self.camera_type == "ascom":
            if not self.camera:
                connect_status = self._initialize_camera()
                if not getattr(connect_status, "is_success", False):
                    return error_status(
                        "Failed to connect to ASCOM camera",
                        details={"driver": getattr(self, "ascom_driver", None)},
                    )
        elif self.camera_type == "alpaca":
            if not self.camera:
                connect_status = self._initialize_camera()
                if not getattr(connect_status, "is_success", False):
                    return error_status(
                        "Failed to connect to Alpaca camera",
                        details={
                            "host": getattr(self, "alpaca_host", None),
                            "port": getattr(self, "alpaca_port", None),
                            "camera_name": getattr(self, "alpaca_camera_name", None),
                        },
                    )

        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        return success_status(
            "Video capture started", details={"camera_type": self.camera_type, "is_capturing": True}
        )

    def stop_capture(self) -> CameraStatus:
        self.is_capturing = False
        if hasattr(self, "capture_thread") and self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        return success_status(
            "Video capture stopped",
            details={"camera_type": self.camera_type, "is_capturing": False},
        )

    def _capture_loop(self) -> None:
        while self.is_capturing:
            try:
                if self.camera_type == "opencv":
                    if self.cap and self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret:
                            # Wrap into Frame and Status for consistency
                            frame_np = frame.copy()
                            details = {
                                "exposure_time_s": self.exposure_time,
                                "gain": getattr(self, "gain", None),
                                "binning": 1,
                                "dimensions": f"{self.resolution[0]}x{self.resolution[1]}",
                                "debayered": True,
                                "capture_started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "capture_finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            }
                            status_obj = success_status(
                                "Frame captured",
                                data=Frame(data=frame_np, metadata=details),
                                details=details,
                            )
                            with self.frame_lock:
                                self.current_frame = status_obj
                        else:
                            time.sleep(0.1)
                elif self.camera_type in ["ascom", "alpaca"]:
                    # For long-exposure cameras, background loop does not auto-capture
                    time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)

    def get_current_frame(self) -> Optional[Any]:
        with self.frame_lock:
            if self.current_frame is None:
                return None
            return self.current_frame

    def capture_single_frame(self) -> CameraStatus:
        # Unified single-frame capture via adapter
        if not self.camera:
            init_status = self._initialize_camera()
            if not init_status or (
                hasattr(init_status, "is_success") and not init_status.is_success
            ):
                return error_status("Failed to connect to camera")
        # Choose exposure/gain/binning from appropriate config block
        cam_cfg = self.config.get_camera_config()
        if self.camera_type == "alpaca":
            section = cam_cfg.get("alpaca", {})
            binning = section.get("binning", [1, 1])
        elif self.camera_type == "ascom":
            section = cam_cfg.get("ascom", {})
            binning = section.get("binning", 1)
        else:
            section = cam_cfg.get("opencv", {})
            binning = 1
        exposure_time = section.get("exposure_time", 1.0)
        # Allow adaptive override (set by VideoProcessor)
        try:
            override = getattr(self, "next_exposure_time_override", None)
            if override is not None:
                exposure_time = float(override)
        except Exception:
            pass
        gain = section.get("gain", None)
        # Hot-reload offset/readout_mode alongside exposure/gain
        try:
            self.offset = section.get("offset", getattr(self, "offset", None))
        except Exception:
            pass
        try:
            self.readout_mode = section.get("readout_mode", getattr(self, "readout_mode", None))
        except Exception:
            pass
        return self.capture_single_frame_generic(exposure_time, gain, binning)

    def capture_single_frame_generic(
        self, exposure_time_s: float, gain: Optional[float] = None, binning: int | list[int] = 1
    ) -> CameraStatus:
        if not self.camera:
            return error_status("Camera not connected")
        try:
            # Set parameters if supported
            try:
                if gain is None:
                    gain = self.gain
                if gain is not None and hasattr(self.camera, "gain"):
                    self.camera.gain = gain
                if isinstance(binning, list):
                    binning_value = binning[0] if len(binning) > 0 else 1
                else:
                    binning_value = int(binning)
                if binning_value != 1:
                    if hasattr(self.camera, "bin_x"):
                        self.camera.bin_x = binning_value
                    if hasattr(self.camera, "bin_y"):
                        self.camera.bin_y = binning_value
                if hasattr(self.camera, "offset"):
                    self.camera.offset = self.offset
                if hasattr(self.camera, "readout_mode"):
                    self.camera.readout_mode = self.readout_mode
            except Exception as param_e:
                self.logger.debug(f"Non-fatal: could not set some camera parameters: {param_e}")

            # Start exposure and timestamp
            capture_started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.logger.info(
                "Capture %s start: exp=%.3fs, gain=%s, bin=%s",
                capture_started_at,
                exposure_time_s,
                str(gain),
                str(binning),
            )
            self.camera.start_exposure(exposure_time_s, light=True)

            # Wait for image readiness depending on camera type
            # Use adapter-provided wait when available
            timeout = exposure_time_s + 30.0
            if hasattr(self.camera, "wait_for_image_ready"):
                ready = self.camera.wait_for_image_ready(timeout)
                if not ready:
                    return error_status("Exposure timeout")
            else:
                # Fallbacks per type
                if self.camera_type == "alpaca":
                    start_time = time.time()
                    while not getattr(self.camera, "image_ready", False):
                        time.sleep(0.1)
                        if time.time() - start_time > timeout:
                            return error_status("Exposure timeout")
                elif self.camera_type == "ascom":
                    time.sleep(min(max(exposure_time_s, 0.0) + 0.05, exposure_time_s + 0.5))
            image_data = self.camera.get_image_array()

            if image_data is None:
                return error_status("Failed to get image data from camera")

            effective_width = getattr(self.camera, "camera_x_size", self.resolution[0])
            effective_height = getattr(self.camera, "camera_y_size", self.resolution[1])
            settings = CameraSettings(
                exposure_time_s=exposure_time_s,
                gain=gain,
                offset=getattr(self.camera, "offset", None),
                readout_mode=getattr(self.camera, "readout_mode", None),
                binning=(binning_value if "binning_value" in locals() else binning),
                dimensions=f"{effective_width}x{effective_height}",
            )
            frame_details = {
                **settings.to_dict(),
                "debayered": bool(getattr(self.camera, "is_color_camera", lambda: False)()),
            }

            frame_data = image_data
            # Preserve original undebayered mosaic (if available) for RAW FITS archival
            raw_mosaic = None
            try:
                import numpy as _np

                raw_mosaic = _np.squeeze(frame_data)
                if getattr(raw_mosaic, "ndim", 0) == 2:
                    pass
                elif getattr(raw_mosaic, "ndim", 0) == 3 and (
                    raw_mosaic.shape[-1] == 1 or raw_mosaic.shape[0] == 1
                ):
                    # Squeeze single-plane dimension
                    raw_mosaic = (
                        raw_mosaic[..., 0] if raw_mosaic.shape[-1] == 1 else raw_mosaic[0, ...]
                    )
                else:
                    # If truly multi-channel, we cannot treat as undebayered mosaic
                    raw_mosaic = None
            except Exception:
                raw_mosaic = None
            if self.enable_calibration and self.calibration_applier:
                calibration_status = self.calibration_applier.calibrate_frame(
                    frame_data, exposure_time_s, frame_details
                )
            else:
                calibration_status = success_status(
                    "Calibration skipped", data=frame_data, details={"calibration_applied": False}
                )

            if calibration_status.is_success:
                calibrated_frame = calibration_status.data
                frame_details.update(calibration_status.details)
                frame_details["capture_started_at"] = capture_started_at
                frame_details["capture_finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

                # Centralized debayer: produce color and green once for the frame
                try:
                    from processing.format_conversion import debayer_to_color_and_green

                    color16, green16, pattern = debayer_to_color_and_green(
                        calibrated_frame, self.camera, self.config, self.logger
                    )
                    if pattern:
                        frame_details["bayer_pattern"] = pattern
                    # Prefer raw mosaic derived from calibrated_frame when possible
                    try:
                        import numpy as _np

                        raw_mosaic_cf = _np.squeeze(calibrated_frame)
                        if getattr(raw_mosaic_cf, "ndim", 0) == 2:
                            raw_mosaic_use = raw_mosaic_cf
                        elif getattr(raw_mosaic_cf, "ndim", 0) == 3 and (
                            raw_mosaic_cf.shape[-1] == 1 or raw_mosaic_cf.shape[0] == 1
                        ):
                            raw_mosaic_use = (
                                raw_mosaic_cf[..., 0]
                                if raw_mosaic_cf.shape[-1] == 1
                                else raw_mosaic_cf[0, ...]
                            )
                        else:
                            raw_mosaic_use = raw_mosaic
                    except Exception:
                        raw_mosaic_use = raw_mosaic
                    if color16 is not None and green16 is not None:
                        frame_details["debayered"] = True
                        frame_obj = Frame(
                            data=color16,
                            metadata=frame_details,
                            green_channel=green16,
                            raw_data=raw_mosaic_use,
                        )
                    else:
                        frame_obj = Frame(
                            data=calibrated_frame, metadata=frame_details, raw_data=raw_mosaic_use
                        )
                except Exception:
                    frame_obj = Frame(
                        data=calibrated_frame, metadata=frame_details, raw_data=raw_mosaic
                    )

                if self.return_frame_objects:
                    return success_status("Frame captured", data=frame_obj, details=frame_details)
                return success_status("Frame captured", data=frame_obj.data, details=frame_details)
            else:
                frame_details["capture_started_at"] = capture_started_at
                frame_details["capture_finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                if self.return_frame_objects:
                    return success_status(
                        "Frame captured (calibration failed)",
                        data=Frame(
                            data=frame_data,
                            metadata=frame_details,
                            raw_data=frame_data,
                        ),
                        details=frame_details,
                    )
                return success_status(
                    "Frame captured (calibration failed)", data=frame_data, details=frame_details
                )
        except Exception as e:
            return error_status(f"Error capturing frame: {e}")

    def capture_single_frame_ascom(
        self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1
    ) -> CameraStatus:
        return self.capture_single_frame_generic(exposure_time_s, gain, binning)

    def capture_single_frame_alpaca(
        self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1
    ) -> CameraStatus:
        return self.capture_single_frame_generic(exposure_time_s, gain, binning)

    def save_frame(self, frame: Any, filename: str) -> CameraStatus:
        try:
            # Prefer centralized FrameWriter for uniform saving behavior
            output_path = Path(filename)
            image_data, details = unwrap_status(frame)
            # Wrap into Frame for structured saving
            frame_obj = Frame(
                data=image_data if image_data is not None else frame, metadata=details or {}
            )
            writer = self._frame_writer
            if writer is None:
                from services.frame_writer import FrameWriter

                writer = FrameWriter(
                    self.config,
                    logger=self.logger,
                    camera=self.camera,
                    camera_type=self.camera_type,
                )
            return writer.save(frame_obj, str(output_path))
        except Exception as e:
            camera_id = (
                self.camera_index
                if hasattr(self, "camera_index")
                else getattr(self, "ascom_driver", None)
            )
            return error_status(f"Error saving frame: {e}", details={"camera_id": camera_id})

    # Note: Image saving is fully delegated to FrameWriter via save_frame().
