#!/usr/bin/env python3
"""
Video capture module for telescope streaming system.
Handles video capture, frame processing, calibration metadata, and cooling lifecycle.
"""

from __future__ import annotations

import os
import time
try:
    import cv2  # optional at import time; used only for OpenCV camera
except Exception:  # pragma: no cover
    cv2 = None
import numpy as np
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from status import CameraStatus, success_status, error_status, warning_status
from calibration_applier import CalibrationApplier
from utils.fits_utils import enrich_header_from_metadata
from processing.format_conversion import convert_camera_data_to_opencv
from utils.status_utils import unwrap_status
from capture.adapters import AlpacaCameraAdapter, AscomCameraAdapter
from capture.frame import Frame


class VideoCapture:
    """Video capture class for telescope streaming."""
    
    def __init__(self, config, logger: Optional[logging.Logger] = None, enable_calibration: bool = True, return_frame_objects: bool = False) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Camera/config state
        frame_config = config.get_frame_processing_config()
        camera_cfg = config.get_camera_config()
        self.camera_type = camera_cfg.get('camera_type', 'opencv')
        self.camera_index = camera_cfg.get('opencv', {}).get('camera_index', 0)
        self.exposure_time = camera_cfg.get('opencv', {}).get('exposure_time', 1.0)
        self.gain = camera_cfg.get('ascom', {}).get('gain', 100.0)
        self.offset = camera_cfg.get('ascom', {}).get('offset', 50.0)
        self.readout_mode = camera_cfg.get('ascom', {}).get('readout_mode', 0)
        self.binning = camera_cfg.get('ascom', {}).get('binning', 1)
        self.frame_rate = camera_cfg.get('opencv', {}).get('fps', 30)
        self.resolution = camera_cfg.get('opencv', {}).get('resolution', [1920, 1080])
        self.frame_enabled = frame_config.get('enabled', True)
        
        # Cooling configuration
        cooling_config = camera_cfg.get('cooling', {})
        self.enable_cooling = cooling_config.get('enable_cooling', False)
        self.wait_for_cooling = cooling_config.get('wait_for_cooling', True)
        self.cooling_timeout = cooling_config.get('cooling_timeout', 300)
        
        # Runtime camera handles
        self.camera = None
        self.cap = None
        self.cooling_manager = None
        
        # Threading and state
        self.is_capturing = False
        self.capture_thread = None
        self.current_frame = None
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
        self._initialize_camera()
        if self.enable_cooling:
            if self.camera:
                from cooling_manager import create_cooling_manager
                self.cooling_manager = create_cooling_manager(self.camera, config, logger)
            elif self.camera_type == 'opencv':
                self.logger.info("Cooling not supported for OpenCV cameras")
                self.enable_cooling = False
            else:
                self.logger.warning("Cooling enabled but no compatible camera found")
    
    def _ensure_directories(self) -> None:
        try:
            output_dir = Path(self.config.get_frame_processing_config().get('output_dir', 'captured_frames'))
            output_dir.mkdir(parents=True, exist_ok=True)
            cache_dir = Path("cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.warning(f"Failed to create output directories: {e}")
    
    def _initialize_camera(self) -> CameraStatus:
        if self.camera_type == 'opencv':
            if cv2 is None:
                return error_status("OpenCV (cv2) not available")
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                return error_status(f"Failed to open camera {self.camera_index}", details={'camera_index': self.camera_index})
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.frame_rate)
            if not self.enable_cooling:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                exposure_cv = int(self.exposure_time * 1_000_000)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_cv)
            if hasattr(cv2, 'CAP_PROP_GAIN'):
                self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
            return success_status("Camera connected", details={'camera_index': self.camera_index})
            
        elif self.camera_type == 'ascom':
            cam_cfg = self.config.get_camera_config()
            self.ascom_driver = cam_cfg.get('ascom_driver', None)
            if not self.ascom_driver:
                return error_status("ASCOM driver ID not configured")
            # Lazy import to avoid import-time dependency in environments without ASCOM
            from ascom_camera import ASCOMCamera
            cam = ASCOMCamera(driver_id=self.ascom_driver, config=self.config, logger=self.logger)
            status = cam.connect()
            if status.is_success:
                # Preconfigure subframe on the underlying ASCOM camera
                try:
                    native_width = cam.camera.CameraXSize
                    native_height = cam.camera.CameraYSize
                    ascom_config = self.config.get_camera_config().get('ascom', {})
                    binning = ascom_config.get('binning', 1)
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
                return success_status("ASCOM camera connected", details={'driver': self.ascom_driver})
            else:
                self.camera = None
                return error_status(f"ASCOM camera connection failed: {status.message}", details={'driver': self.ascom_driver})

        elif self.camera_type == 'alpaca':
            cam_cfg = self.config.get_camera_config()
            self.alpaca_host = cam_cfg.get('alpaca_host', 'localhost')
            self.alpaca_port = cam_cfg.get('alpaca_port', 11111)
            self.alpaca_device_id = cam_cfg.get('alpaca_device_id', 0)
            self.alpaca_camera_name = cam_cfg.get('alpaca_camera_name', 'Unknown')
            # Lazy import to avoid import-time dependency if alpaca lib is not installed
            from alpaca_camera import AlpycaCameraWrapper
            cam = AlpycaCameraWrapper(self.alpaca_host, self.alpaca_port, self.alpaca_device_id, self.config, self.logger)
            status = cam.connect()
            if status.is_success:
                self.camera = AlpacaCameraAdapter(cam)
                return success_status("Alpaca camera connected", details={'host': self.alpaca_host, 'port': self.alpaca_port, 'camera_name': self.alpaca_camera_name})
            else:
                self.camera = None
                return error_status(f"Alpaca camera connection failed: {status.message}", details={'host': self.alpaca_host, 'port': self.alpaca_port, 'camera_name': self.alpaca_camera_name})
        else:
            return error_status(f"Unsupported camera type: {self.camera_type}")
    
    def _initialize_cooling(self) -> CameraStatus:
        if not self.enable_cooling:
            return success_status("Cooling not enabled")
        if not self.cooling_manager:
            return error_status("Cooling manager not initialized")
        try:
            target_temp = self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0)
            status = self.cooling_manager.set_target_temperature(target_temp)
            if not status.is_success:
                return status
            if self.wait_for_cooling:
                stabilization_status = self.cooling_manager.wait_for_stabilization(timeout=self.cooling_timeout)
                if not stabilization_status.is_success:
                    return warning_status(f"Cooling initialized but stabilization failed: {stabilization_status.message}")
            return success_status("Cooling initialized successfully")
        except Exception as e:
            return error_status(f"Failed to initialize cooling: {e}")
    
    def start_observation_session(self) -> CameraStatus:
        try:
            if self.enable_cooling:
                cooling_status = self._initialize_cooling()
                if not cooling_status.is_success:
                    return cooling_status
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
            if self.cooling_manager and self.cooling_manager.is_cooling:
                warmup_status = self.cooling_manager.start_warmup()
                if not warmup_status.is_success:
                    self.logger.warning(f"Warmup start: {warmup_status.message}")
            return success_status("Observation session ended successfully")
        except Exception as e:
            return error_status(f"Failed to end observation session: {e}")
    
    def get_cooling_status(self) -> Dict[str, Any]:
        if not self.cooling_manager:
            return {'error': 'Cooling manager not available'}
        return self.cooling_manager.get_cooling_status()
    
    def get_field_of_view(self) -> tuple[float, float]:
        try:
            sensor_width = self.config.get_camera_config().get('sensor_width', 6.17)
            sensor_height = self.config.get_camera_config().get('sensor_height', 4.55)
            focal_length = self.config.get_telescope_config().get('focal_length', 1000)
            fov_width = (sensor_width / focal_length) * (180 / 3.14159)
            fov_height = (sensor_height / focal_length) * (180 / 3.14159)
            return (fov_width, fov_height)
        except Exception:
            return (1.5, 1.0)
    
    def get_sampling_arcsec_per_pixel(self) -> float:
        try:
            pixel_size = self.config.get_camera_config().get('pixel_size', 3.75)
            focal_length = self.config.get_telescope_config().get('focal_length', 1000)
            pixel_size_mm = pixel_size / 1000
            sampling = (pixel_size_mm / focal_length) * 206265
            return sampling
        except Exception:
            return 1.0
    
    def disconnect(self) -> None:
        if self.camera_type == 'opencv':
            if self.cap:
                self.cap.release()
                self.cap = None
        elif self.camera_type == 'ascom':
            if self.camera:
                self.camera.disconnect()
                self.camera = None
        elif self.camera_type == 'alpaca':
            if self.camera:
                self.camera.disconnect()
                self.camera = None
        self.logger.info("Camera disconnected")
    
    # Legacy shim for tests expecting a connect() method
    def connect(self):  # pragma: no cover
        return self._initialize_camera()

    # Legacy shim used by tests
    def get_camera_info(self):  # pragma: no cover
        info = {
            'camera_type': self.camera_type,
            'resolution': tuple(self.resolution),
        }
        if self.camera_type == 'ascom' and self.camera:
            try:
                info['name'] = getattr(self.camera, 'name', None)
            except Exception:
                pass
        return info

    def start_capture(self) -> CameraStatus:
        if self.camera_type == 'opencv':
            if not self.cap or not self.cap.isOpened():
                init_status = self._initialize_camera()
                if not init_status or (hasattr(init_status, 'is_success') and not init_status.is_success):
                    return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
        elif self.camera_type == 'ascom':
            if not self.camera:
                connect_status = self._initialize_camera()
                if not connect_status.is_success:
                    return error_status("Failed to connect to ASCOM camera", details={'driver': getattr(self, 'ascom_driver', None)})
        elif self.camera_type == 'alpaca':
            if not self.camera:
                connect_status = self._initialize_camera()
                if not connect_status.is_success:
                    return error_status("Failed to connect to Alpaca camera", details={'host': getattr(self, 'alpaca_host', None), 'port': getattr(self, 'alpaca_port', None), 'camera_name': getattr(self, 'alpaca_camera_name', None)})
        
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        return success_status("Video capture started", details={'camera_type': self.camera_type, 'is_capturing': True})
    
    def stop_capture(self) -> CameraStatus:
        self.is_capturing = False
        if hasattr(self, 'capture_thread') and self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        return success_status("Video capture stopped", details={'camera_type': self.camera_type, 'is_capturing': False})
    
    def _capture_loop(self) -> None:
        while self.is_capturing:
            try:
                if self.camera_type == 'opencv':
                    if self.cap and self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret:
                            with self.frame_lock:
                                self.current_frame = frame.copy()
                        else:
                            time.sleep(0.1)
                elif self.camera_type in ['ascom', 'alpaca']:
                    if self.camera:
                        if self.camera_type == 'alpaca':
                            alpaca_config = self.config.get_camera_config().get('alpaca', {})
                            exposure_time = alpaca_config.get('exposure_time', 1.0)
                            gain = alpaca_config.get('gain', None)
                            binning = alpaca_config.get('binning', [1, 1])
                            status = self.capture_single_frame_alpaca(exposure_time, gain, binning)
                        else:
                            ascom_config = self.config.get_camera_config().get('ascom', {})
                            exposure_time = ascom_config.get('exposure_time', 1.0)
                            gain = ascom_config.get('gain', None)
                            binning = ascom_config.get('binning', 1)
                            status = self.capture_single_frame_ascom(exposure_time, gain, binning)
                        if status.is_success:
                            with self.frame_lock:
                                self.current_frame = status
                        else:
                            time.sleep(0.1)
                    else:
                        time.sleep(0.1)
                    time.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
    
    def get_current_frame(self) -> Optional[Any]:
        with self.frame_lock:
            if self.current_frame is None:
                return None
            if hasattr(self.current_frame, 'data') or hasattr(self.current_frame, 'is_success'):
                return self.current_frame
            return self.current_frame
    
    def capture_single_frame(self) -> CameraStatus:
        if self.camera_type == 'ascom' and self.camera:
            ascom_config = self.config.get_camera_config().get('ascom', {})
            exposure_time = ascom_config.get('exposure_time', 1.0)
            gain = ascom_config.get('gain', None)
            binning = ascom_config.get('binning', 1)
            return self.capture_single_frame_ascom(exposure_time, gain, binning)
        elif self.camera_type == 'alpaca' and self.camera:
            alpaca_config = self.config.get_camera_config().get('alpaca', {})
            exposure_time = alpaca_config.get('exposure_time', 1.0)
            gain = alpaca_config.get('gain', None)
            binning = alpaca_config.get('binning', [1, 1])
            return self.capture_single_frame_alpaca(exposure_time, gain, binning)
        elif self.camera_type == 'opencv':
            if not self.cap or not self.cap.isOpened():
                init_status = self._initialize_camera()
                if not init_status or (hasattr(init_status, 'is_success') and not init_status.is_success):
                    return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
            ret, frame = self.cap.read()
            if ret:
                return success_status("Frame captured", data=frame, details={'camera_index': self.camera_index})
            else:
                return error_status("Failed to capture single frame", details={'camera_index': self.camera_index})
        else:
            return error_status(f"Unsupported camera type: {self.camera_type}")
    
    def capture_single_frame_ascom(self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1) -> CameraStatus:
        if not self.camera:
            return error_status("ASCOM camera not connected")
        try:
            # Set parameters via adapter when available
            if gain is None:
                gain = self.gain
            try:
                if gain is not None:
                    self.camera.gain = gain  # type: ignore[attr-defined]
                if isinstance(binning, list):
                    binning_value = binning[0] if len(binning) > 0 else 1
                else:
                    binning_value = int(binning)
                if binning_value != 1:
                    # Best-effort set binning if supported
                    if hasattr(self.camera, 'bin_x'):
                        self.camera.bin_x = binning_value  # type: ignore[attr-defined]
                    if hasattr(self.camera, 'bin_y'):
                        self.camera.bin_y = binning_value  # type: ignore[attr-defined]
                if hasattr(self.camera, 'offset'):
                    self.camera.offset = self.offset  # type: ignore[attr-defined]
                if hasattr(self.camera, 'readout_mode'):
                    self.camera.readout_mode = self.readout_mode  # type: ignore[attr-defined]
            except Exception as e:
                self.logger.warning(f"Could not set ASCOM camera parameters: {e}")

            # Start exposure using adapter
            try:
                self.camera.start_exposure(exposure_time_s, light=True)  # type: ignore[attr-defined]
            except Exception as e:
                return error_status(f"Failed to start ASCOM exposure: {e}")

            # ASCOM adapter returns image_array from get_image_array()
            # Wait a minimal time; in real ASCOM flow we would poll image_ready
            time.sleep(min(max(exposure_time_s, 0.0) + 0.05, exposure_time_s + 0.5))
            image_data = None
            try:
                image_data = self.camera.get_image_array()  # type: ignore[attr-defined]
            except Exception as e:
                return error_status(f"Failed to get ASCOM image: {e}")
            if image_data is None:
                return error_status("Failed to get image data from ASCOM camera")

            effective_width = getattr(self.camera, 'camera_x_size', self.resolution[0])  # type: ignore[attr-defined]
            effective_height = getattr(self.camera, 'camera_y_size', self.resolution[1])  # type: ignore[attr-defined]
            # Build frame details
            frame_data = image_data
            frame_details = {
                'exposure_time_s': exposure_time_s,
                'gain': gain,
                'binning': binning_value if 'binning_value' in locals() else binning,
                'offset': getattr(self.camera, 'offset', None),
                'readout_mode': getattr(self.camera, 'readout_mode', None),
                'dimensions': f"{effective_width}x{effective_height}",
                'debayered': bool(getattr(self.camera, 'is_color_camera', lambda: False)()),
            }
            if self.enable_calibration and self.calibration_applier:
                calibration_status = self.calibration_applier.calibrate_frame(frame_data, exposure_time_s, frame_details)
            else:
                calibration_status = success_status("Calibration skipped", data=frame_data, details={'calibration_applied': False})
            if calibration_status.is_success:
                calibrated_frame = calibration_status.data
                frame_details.update(calibration_status.details)
                if self.return_frame_objects:
                    return success_status("Frame captured", data=Frame(data=calibrated_frame, metadata=frame_details), details=frame_details)
                return success_status("Frame captured", data=calibrated_frame, details=frame_details)
            else:
                if self.return_frame_objects:
                    return success_status("Frame captured (calibration failed)", data=Frame(data=frame_data, metadata=frame_details), details=frame_details)
                return success_status("Frame captured (calibration failed)", data=frame_data, details=frame_details)
        except Exception as e:
            return error_status(f"Error capturing ASCOM frame: {e}")
    
    def capture_single_frame_alpaca(self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1) -> CameraStatus:
        if not self.camera:
            return error_status("Alpaca camera not connected")
        try:
            if gain is None:
                gain = self.gain
            try:
                if gain is not None:
                    self.camera.gain = gain
                if isinstance(binning, list):
                    binning_value = binning[0] if len(binning) > 0 else 1
                else:
                    binning_value = int(binning)
                if binning_value != 1:
                    self.camera.bin_x = binning_value
                    self.camera.bin_y = binning_value
                if hasattr(self.camera, 'offset'):
                    self.camera.offset = self.offset
                if hasattr(self.camera, 'readout_mode'):
                    self.camera.readout_mode = self.readout_mode
            except Exception as e:
                self.logger.warning(f"Could not set camera parameters: {e}")
            self.camera.start_exposure(exposure_time_s, light=True)
            start_time = time.time()
            timeout = exposure_time_s + 30
            while not self.camera.image_ready:
                time.sleep(0.1)
                if time.time() - start_time > timeout:
                    return error_status("Exposure timeout")
            image_data = self.camera.get_image_array()
            if image_data is None:
                return error_status("Failed to get image data from Alpaca camera")
            effective_width = self.camera.camera_x_size
            effective_height = self.camera.camera_y_size
            if self.camera.is_color_camera():
                frame_data = image_data
                frame_details = {
                    'exposure_time_s': exposure_time_s, 
                    'gain': gain, 
                    'binning': binning_value, 
                    'offset': getattr(self.camera, 'offset', None),
                    'readout_mode': getattr(self.camera, 'readout_mode', None),
                    'dimensions': f"{effective_width}x{effective_height}", 
                    'debayered': True,
                }
            else:
                frame_data = image_data
                frame_details = {
                    'exposure_time_s': exposure_time_s, 
                    'gain': gain, 
                    'binning': binning_value, 
                    'offset': getattr(self.camera, 'offset', None),
                    'readout_mode': getattr(self.camera, 'readout_mode', None),
                    'dimensions': f"{effective_width}x{effective_height}", 
                    'debayered': False,
                }
            if self.enable_calibration and self.calibration_applier:
                calibration_status = self.calibration_applier.calibrate_frame(frame_data, exposure_time_s, frame_details)
            else:
                calibration_status = success_status("Calibration skipped", data=frame_data, details={'calibration_applied': False})
            if calibration_status.is_success:
                calibrated_frame = calibration_status.data
                frame_details.update(calibration_status.details)
                if self.return_frame_objects:
                    return success_status("Frame captured", data=Frame(data=calibrated_frame, metadata=frame_details), details=frame_details)
                return success_status("Frame captured", data=calibrated_frame, details=frame_details)
            else:
                if self.return_frame_objects:
                    return success_status("Frame captured (calibration failed)", data=Frame(data=frame_data, metadata=frame_details), details=frame_details)
                return success_status("Frame captured (calibration failed)", data=frame_data, details=frame_details)
        except Exception as e:
            return error_status(f"Error capturing Alpaca frame: {e}")
    
    def save_frame(self, frame: Any, filename: str) -> CameraStatus:
        try:
            # Prefer centralized FrameWriter for uniform saving behavior
            from services.frame_writer import FrameWriter
            output_path = Path(filename)
            image_data, details = unwrap_status(frame)
            # Wrap into Frame for structured saving
            frame_obj = Frame(data=image_data if image_data is not None else frame, metadata=details or {})
            writer = FrameWriter(self.config, logger=self.logger, camera=self.camera, camera_type=self.camera_type)
            return writer.save(frame_obj, str(output_path))
        except Exception as e:
            camera_id = self.camera_index if hasattr(self, 'camera_index') else getattr(self, 'ascom_driver', None)
            return error_status(f"Error saving frame: {e}", details={'camera_id': camera_id})
    
    def _save_fits_unified(self, frame: Any, filename: str) -> CameraStatus:
        try:
            # Delegate to FrameWriter for unified FITS saving
            from services.frame_writer import FrameWriter
            image_data, details = unwrap_status(frame)
            writer = FrameWriter(self.config, logger=self.logger, camera=self.camera, camera_type=self.camera_type)
            return writer.save_fits(image_data if image_data is not None else frame, filename, metadata=details)
        except Exception as e:
            return error_status(f"Error saving FITS file: {e}")
    
    def _save_image_file(self, frame: Any, filename: str) -> CameraStatus:
        try:
            from services.frame_writer import FrameWriter
            image_data, details = unwrap_status(frame)
            frame_obj = Frame(data=image_data if image_data is not None else frame, metadata=details or {})
            writer = FrameWriter(self.config, logger=self.logger, camera=self.camera, camera_type=self.camera_type)
            return writer.save_image(frame_obj, filename)
        except Exception as e:
            return error_status(f"Error saving image file: {e}")

    def _needs_rotation(self, image_shape: tuple) -> bool:
        if len(image_shape) >= 2:
            height, width = image_shape[0], image_shape[1]
            return height > width
        return False 
