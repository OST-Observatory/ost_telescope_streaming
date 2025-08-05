#!/usr/bin/env python3
"""
Video capture module for telescope streaming system.
Handles video capture, frame processing, and plate-solving integration.
"""

import cv2
import numpy as np
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging
import os

# Import configuration
from config_manager import ConfigManager
from exceptions import CameraError, FileError
from status import CameraStatus, success_status, error_status, warning_status
from ascom_camera import ASCOMCamera
from alpaca_camera import AlpycaCameraWrapper
from calibration_applier import CalibrationApplier

class VideoCapture:
    """Video capture class for telescope streaming."""
    
    def __init__(self, config, logger=None):
        """Initialize video capture with cooling support."""
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Video configuration
        video_config = config.get_video_config()
        self.camera_type = video_config.get('camera_type', 'opencv')
        self.camera_index = video_config.get('camera_index', 0)
        self.exposure_time = video_config.get('exposure_time', 1.0)
        self.gain = video_config.get('gain', 100.0)
        self.offset = video_config.get('offset', 50.0)
        self.readout_mode = video_config.get('readout_mode', 0)
        self.binning = video_config.get('binning', [1, 1])
        self.frame_rate = video_config.get('frame_rate', 30)
        self.resolution = video_config.get('resolution', [1920, 1080])
        self.video_enabled = video_config.get('video_enabled', True)
        
        # Cooling configuration
        cooling_config = self.config.get_camera_config().get('cooling', {})
        self.enable_cooling = cooling_config.get('enable_cooling', False)
        self.wait_for_cooling = cooling_config.get('wait_for_cooling', True)
        self.cooling_timeout = cooling_config.get('cooling_timeout', 300)
        
        # Camera objects
        self.camera = None
        self.cooling_manager = None
        
        # Threading and state management
        self.is_capturing = False
        self.capture_thread = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Calibration
        self.calibration_applier = CalibrationApplier(config, logger)
        
        # Directories
        self._ensure_directories()
        
        # Initialize camera
        self._initialize_camera()
        
        # Initialize cooling if enabled
        if self.enable_cooling:
            if self.camera:  # ASCOM or Alpaca camera
                from cooling_manager import create_cooling_manager
                self.cooling_manager = create_cooling_manager(self.camera, config, logger)
            elif self.camera_type == 'opencv':
                # OpenCV cameras don't support cooling
                self.logger.info("Cooling not supported for OpenCV cameras")
                self.enable_cooling = False
            else:
                self.logger.warning("Cooling enabled but no compatible camera found")
    
    def _ensure_directories(self):
        """Create necessary output directories."""
        try:
            # Create captured frames directory
            output_dir = Path(self.config.get_video_config().get('output_directory', 'captured_frames'))
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Output directory ready: {output_dir}")
            
            # Create cache directory
            cache_dir = Path("cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Cache directory ready: {cache_dir}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create output directories: {e}")
    
    def _initialize_camera(self) -> CameraStatus:
        """Initialize the video camera."""
        if self.camera_type == 'opencv':
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.logger.error(f"Failed to open camera {self.camera_index}")
                return error_status(f"Failed to open camera {self.camera_index}", details={'camera_index': self.camera_index})
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.frame_rate)
            
            if not self.enable_cooling: # OpenCV cameras don't have auto-exposure
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure
                # Convert seconds to OpenCV exposure units (typically microseconds)
                exposure_cv = int(self.exposure_time * 1000000)  # Convert seconds to microseconds
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_cv)
            
            # Set gain if supported
            if hasattr(cv2, 'CAP_PROP_GAIN'):
                self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
            
            # Calculate field of view
            self.fov_width, self.fov_height = self.get_field_of_view()
            
            # Verify settings
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.logger.info(f"Camera connected: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")
            self.logger.info(f"FOV: {self.fov_width:.3f}° x {self.fov_height:.3f}°")
            self.logger.info(f"Sampling: {self.get_sampling_arcsec_per_pixel():.2f} arcsec/pixel")
            
            return success_status("Camera connected", details={'camera_index': self.camera_index, 'resolution': f'{actual_width}x{actual_height}', 'fps': actual_fps})
            
        elif self.camera_type == 'ascom':
            cam_cfg = self.config.get_camera_config()
            self.ascom_driver = cam_cfg.get('ascom_driver', None)
            if not self.ascom_driver:
                return error_status("ASCOM driver ID not configured")
            
            cam = ASCOMCamera(driver_id=self.ascom_driver, config=self.config, logger=self.logger)
            status = cam.connect()
            if status.is_success:
                self.camera = cam
                
                # Get actual camera dimensions from ASCOM camera
                try:
                    # Get native sensor dimensions from ASCOM camera
                    native_width = cam.camera.CameraXSize
                    native_height = cam.camera.CameraYSize
                    
                    # Get binning from config
                    ascom_config = self.config.get_video_config().get('ascom', {})
                    binning = ascom_config.get('binning', 1)
                    
                    # Calculate effective dimensions with binning
                    self.resolution[0] = native_width // binning
                    self.resolution[1] = native_height // binning
                    
                    self.logger.info(f"ASCOM camera dimensions: {self.resolution[0]}x{self.resolution[1]} (native: {native_width}x{native_height}, binning: {binning}x{binning})")
                    
                    # Set the subframe to use the full sensor with binning
                    cam.camera.NumX = self.resolution[0]
                    cam.camera.NumY = self.resolution[1]
                    cam.camera.StartX = 0
                    cam.camera.StartY = 0
                    
                except Exception as e:
                    self.logger.warning(f"Could not get camera dimensions: {e}, using defaults")
                    # Use default dimensions from config
                    self.resolution[0] = 1920
                    self.resolution[1] = 1080
                
                self.logger.info("ASCOM camera connected")
                
                return success_status("ASCOM camera connected", details={'driver': self.ascom_driver})
            else:
                self.camera = None
                self.logger.error(f"ASCOM camera connection failed: {status.message}")
                return error_status(f"ASCOM camera connection failed: {status.message}", details={'driver': self.ascom_driver})
        elif self.camera_type == 'alpaca':
            cam_cfg = self.config.get_camera_config()
            self.alpaca_host = cam_cfg.get('alpaca_host', 'localhost')
            self.alpaca_port = cam_cfg.get('alpaca_port', 11111)
            self.alpaca_device_id = cam_cfg.get('alpaca_device_id', 0)
            self.alpaca_camera_name = cam_cfg.get('alpaca_camera_name', 'Unknown')
            
            cam = AlpycaCameraWrapper(self.alpaca_host, self.alpaca_port, self.alpaca_device_id, self.config, self.logger)
            status = cam.connect()
            if status.is_success:
                self.camera = cam
                self.logger.info("Alpaca camera connected")
                
                return success_status("Alpaca camera connected", details={'host': self.alpaca_host, 'port': self.alpaca_port, 'camera_name': self.alpaca_camera_name})
            else:
                self.camera = None
                self.logger.error(f"Alpaca camera connection failed: {status.message}")
                return error_status(f"Alpaca camera connection failed: {status.message}", details={'host': self.alpaca_host, 'port': self.alpaca_port, 'camera_name': self.alpaca_camera_name})
        else:
            return error_status(f"Unsupported camera type: {self.camera_type}")
    
    def _initialize_cooling(self) -> CameraStatus:
        """Initialize cooling system."""
        if not self.enable_cooling:
            return success_status("Cooling not enabled")
        
        if not self.cooling_manager:
            return error_status("Cooling manager not initialized")
        
        try:
            # Get cooling settings from config
            cooling_config = self.config.get_camera_config().get('cooling', {})
            target_temp = cooling_config.get('target_temperature', -10.0)
            
            self.logger.info(f"Initializing cooling to {target_temp}°C")
            
            # Set target temperature
            status = self.cooling_manager.set_target_temperature(target_temp)
            if not status.is_success:
                return status
            
            # Wait for stabilization if required
            if self.wait_for_cooling:
                self.logger.info("Waiting for temperature stabilization...")
                stabilization_status = self.cooling_manager.wait_for_stabilization(
                    timeout=self.cooling_timeout
                )
                
                if not stabilization_status.is_success:
                    self.logger.warning(f"Temperature stabilization: {stabilization_status.message}")
                    return warning_status(f"Cooling initialized but stabilization failed: {stabilization_status.message}")
                else:
                    self.logger.info("✅ Cooling initialized and stabilized successfully")
            
            return success_status("Cooling initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize cooling: {e}")
            return error_status(f"Failed to initialize cooling: {e}")
    
    def start_observation_session(self) -> CameraStatus:
        """Start observation session with cooling initialization."""
        try:
            self.logger.info("Starting observation session...")
            
            # Initialize cooling first
            if self.enable_cooling:
                cooling_status = self._initialize_cooling()
                if not cooling_status.is_success:
                    return cooling_status
            
            # Initialize calibration
            calibration_status = self.calibration_applier.load_master_frames()
            if not calibration_status.is_success:
                self.logger.warning(f"Calibration initialization: {calibration_status.message}")
            
            return success_status("Observation session started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start observation session: {e}")
            return error_status(f"Failed to start observation session: {e}")
    
    def end_observation_session(self) -> CameraStatus:
        """End observation session with warmup."""
        try:
            self.logger.info("Ending observation session...")
            
            # Start warmup if cooling was active
            if self.cooling_manager and self.cooling_manager.is_cooling:
                self.logger.info("Starting warmup phase to prevent thermal shock...")
                warmup_status = self.cooling_manager.start_warmup()
                if warmup_status.is_success:
                    self.logger.info("✅ Warmup started successfully")
                else:
                    self.logger.warning(f"Warmup start: {warmup_status.message}")
            
            return success_status("Observation session ended successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to end observation session: {e}")
            return error_status(f"Failed to end observation session: {e}")
    
    def get_cooling_status(self) -> Dict[str, Any]:
        """Get current cooling status."""
        if not self.cooling_manager:
            return {'error': 'Cooling manager not available'}
        
        return self.cooling_manager.get_cooling_status()
    
    def get_field_of_view(self) -> tuple[float, float]:
        """Returns the current field of view (FOV) in degrees."""
        # Calculate FOV based on camera sensor size and telescope focal length
        try:
            # Get sensor dimensions from config
            sensor_width = self.config.get_camera_config().get('sensor_width', 6.17)  # mm
            sensor_height = self.config.get_camera_config().get('sensor_height', 4.55)  # mm
            
            # Get focal length from telescope config
            focal_length = self.config.get_telescope_config().get('focal_length', 1000)  # mm
            
            # Calculate FOV in degrees
            fov_width = (sensor_width / focal_length) * (180 / 3.14159)  # degrees
            fov_height = (sensor_height / focal_length) * (180 / 3.14159)  # degrees
            
            return (fov_width, fov_height)
        except Exception as e:
            self.logger.warning(f"Could not calculate FOV: {e}, using defaults")
            return (1.5, 1.0)  # Default FOV
    
    def get_sampling_arcsec_per_pixel(self) -> float:
        """Calculates the sampling in arcseconds per pixel."""
        try:
            # Get pixel size from config
            pixel_size = self.config.get_camera_config().get('pixel_size', 3.75)  # micrometers
            
            # Get focal length from telescope config
            focal_length = self.config.get_telescope_config().get('focal_length', 1000)  # mm
            
            # Calculate sampling in arcseconds per pixel
            # Formula: (pixel_size_mm / focal_length_mm) * 206265 arcsec/radian
            pixel_size_mm = pixel_size / 1000  # Convert micrometers to mm
            sampling = (pixel_size_mm / focal_length) * 206265
            
            return sampling
        except Exception as e:
            self.logger.warning(f"Could not calculate sampling: {e}, using default")
            return 1.0  # Default sampling
    
    def disconnect(self):
        """Disconnects from the video camera."""
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
    
    def start_capture(self) -> CameraStatus:
        """Starts continuous frame capture in the background thread.
        Returns:
            CameraStatus: Status object with start information or error.
        """
        if self.camera_type == 'opencv':
            # For OpenCV cameras, just ensure connection
            if not self.cap or not self.cap.isOpened():
                if not self._initialize_camera():
                    return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
        elif self.camera_type == 'ascom':
            # For ASCOM cameras, just ensure connection
            if not self.camera:
                connect_status = self._initialize_camera()
                if not connect_status.is_success:
                    return error_status("Failed to connect to ASCOM camera", details={'driver': self.ascom_driver})
        elif self.camera_type == 'alpaca':
            # For Alpaca cameras, just ensure connection
            if not self.camera:
                connect_status = self._initialize_camera()
                if not connect_status.is_success:
                    return error_status("Failed to connect to Alpaca camera", details={'host': self.alpaca_host, 'port': self.alpaca_port, 'camera_name': self.alpaca_camera_name})
        
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.logger.info("Video capture started")
        return success_status("Video capture started", details={'camera_type': self.camera_type, 'is_capturing': True})
    
    def stop_capture(self) -> CameraStatus:
        """Stops continuous frame capture.
        Returns:
            CameraStatus: Status object with stop information or error.
        """
        self.is_capturing = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=2.0)
        self.logger.info("Video capture stopped")
        return success_status("Video capture stopped", details={'camera_type': self.camera_type, 'is_capturing': False})
    
    def _capture_loop(self) -> None:
        """Background thread for continuous frame capture."""
        while self.is_capturing:
            try:
                if self.camera_type == 'opencv':
                    # OpenCV camera logic
                    if self.cap and self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret:
                            with self.frame_lock:
                                self.current_frame = frame.copy()
                        else:
                            self.logger.warning("Failed to read frame from OpenCV camera")
                            time.sleep(0.1)
                            
                elif self.camera_type == 'ascom':
                    # ASCOM camera logic
                    if self.camera:
                        # Use exposure time in seconds
                        exposure_time = self.config.get_camera_config().get('exposure_time', 1.0)  # seconds
                        gain = self.config.get_camera_config().get('gain', None)
                        binning = self.config.get_camera_config().get('ascom', {}).get('binning', 1)
                        status = self.capture_single_frame_ascom(exposure_time, gain, binning)
                        if status.is_success:
                            # Convert ASCOM image to OpenCV format with debayering
                            frame = self._convert_ascom_to_opencv(status.data)
                            if frame is not None:
                                with self.frame_lock:
                                    self.current_frame = frame.copy()
                            else:
                                self.logger.warning("Failed to convert ASCOM image")
                                time.sleep(0.1)
                        else:
                            self.logger.warning(f"Failed to capture frame from ASCOM camera: {status.message}")
                            time.sleep(0.1)
                    else:
                        self.logger.warning("ASCOM camera not available")
                        time.sleep(0.1)
                elif self.camera_type == 'alpaca':
                    # Alpaca camera logic
                    if self.camera:
                        # Use exposure time in seconds
                        exposure_time = self.config.get_camera_config().get('exposure_time', 1.0)  # seconds
                        gain = self.config.get_camera_config().get('gain', None)
                        binning = self.config.get_camera_config().get('alpaca', {}).get('binning', [1, 1])
                        status = self.capture_single_frame_alpaca(exposure_time, gain, binning)
                        if status.is_success:
                            # Convert Alpaca image to OpenCV format
                            frame = self._convert_alpaca_to_opencv(status.data)
                            if frame is not None:
                                with self.frame_lock:
                                    self.current_frame = frame.copy()
                            else:
                                self.logger.warning("Failed to convert Alpaca image")
                                time.sleep(0.1)
                        else:
                            self.logger.warning(f"Failed to capture frame from Alpaca camera: {status.message}")
                            time.sleep(0.1)
                    else:
                        self.logger.warning("Alpaca camera not available")
                        time.sleep(0.1)
                        
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Returns the last captured frame."""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def capture_single_frame(self) -> CameraStatus:
        """Captures a single frame and returns status.
        Returns:
            CameraStatus: Status object with frame or error.
        """
        if self.camera_type == 'ascom' and self.camera:
            # Use exposure time in seconds
            exposure_time = self.config.get_camera_config().get('exposure_time', 1.0)  # seconds
            gain = self.config.get_camera_config().get('gain', None)
            binning = self.config.get_video_config().get('binning', 1)
            return self.capture_single_frame_ascom(exposure_time, gain, binning)
        elif self.camera_type == 'alpaca' and self.camera:
            # Use exposure time in seconds
            exposure_time = self.config.get_camera_config().get('exposure_time', 1.0)  # seconds
            gain = self.config.get_camera_config().get('gain', None)
            binning = self.config.get_camera_config().get('alpaca', {}).get('binning', [1, 1])
            return self.capture_single_frame_alpaca(exposure_time, gain, binning)
        elif self.camera_type == 'opencv':
            if not self.cap or not self.cap.isOpened():
                if not self._initialize_camera():
                    return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
            ret, frame = self.cap.read()
            if ret:
                return success_status("Frame captured", data=frame, details={'camera_index': self.camera_index})
            else:
                self.logger.error("Failed to capture single frame")
                return error_status("Failed to capture single frame", details={'camera_index': self.camera_index})
        else:
            return error_status(f"Unsupported camera type: {self.camera_type}")
    
    def capture_single_frame_ascom(self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1) -> CameraStatus:
        """Captures a single frame with ASCOM camera.
        Args:
            exposure_time_s: Exposure time in seconds
            gain: Gain value (optional, uses config default if None)
            binning: Binning factor (default: 1)
        Returns:
            CameraStatus: Status object with frame or error.
        """
        if not self.camera:
            return error_status("ASCOM camera not connected")
        
        try:
            # Use the already set dimensions from connect()
            effective_width = self.resolution[0]
            effective_height = self.resolution[1]
            
            # Only set subframe if dimensions have changed
            try:
                current_numx = self.camera.camera.NumX
                current_numy = self.camera.camera.NumY
                
                if current_numx != effective_width or current_numy != effective_height:
                    self.logger.debug(f"Updating subframe: {current_numx}x{current_numy} -> {effective_width}x{effective_height}")
                    self.camera.camera.NumX = effective_width
                    self.camera.camera.NumY = effective_height
                    self.camera.camera.StartX = 0
                    self.camera.camera.StartY = 0
                else:
                    self.logger.debug(f"Subframe already set correctly: {effective_width}x{effective_height}")
                    
            except Exception as e:
                self.logger.warning(f"Could not update subframe: {e}")
                self.logger.info("Using existing subframe settings")
            
            # Use configuration defaults if not provided
            if gain is None:
                gain = self.gain
            
            # Get offset and readout mode from configuration
            offset = self.offset
            readout_mode = self.readout_mode
            
            # Start exposure with all parameters
            exp_status = self.camera.expose(exposure_time_s, gain, binning, offset, readout_mode)
            if not exp_status.is_success:
                return exp_status
            
            # Get image
            img_status = self.camera.get_image()
            if not img_status.is_success:
                return img_status
            
            # Check if debayering is needed
            if hasattr(self.camera, 'is_color_camera') and self.camera.is_color_camera():
                debayer_status = self.camera.debayer(img_status.data)
                if debayer_status.is_success:
                    frame_data = debayer_status.data
                    frame_details = {'exposure_time_s': exposure_time_s, 'gain': gain, 'binning': binning, 'offset': offset, 'readout_mode': readout_mode, 'dimensions': f"{effective_width}x{effective_height}", 'debayered': True}
                else:
                    self.logger.warning(f"Debayering failed: {debayer_status.message}, returning raw image")
                    frame_data = img_status.data
                    frame_details = {'exposure_time_s': exposure_time_s, 'gain': gain, 'binning': binning, 'offset': offset, 'readout_mode': readout_mode, 'dimensions': f"{effective_width}x{effective_height}", 'debayered': False}
            else:
                frame_data = img_status.data
                frame_details = {'exposure_time_s': exposure_time_s, 'gain': gain, 'binning': binning, 'offset': offset, 'readout_mode': readout_mode, 'dimensions': f"{effective_width}x{effective_height}", 'debayered': False}
            
            # Apply calibration if enabled and master frames are available
            calibration_status = self.calibration_applier.calibrate_frame(frame_data, exposure_time_s, frame_details)
            
            if calibration_status.is_success:
                calibrated_frame = calibration_status.data
                calibration_details = calibration_status.details
                
                # Update frame details with calibration information
                frame_details.update(calibration_details)
                
                if calibration_details.get('calibration_applied', False):
                    self.logger.info(f"Frame calibrated: Dark={calibration_details.get('dark_subtraction_applied', False)}, "
                                   f"Flat={calibration_details.get('flat_correction_applied', False)}")
                    return success_status("Frame captured and calibrated", 
                                        data=calibrated_frame, 
                                        details=frame_details)
                else:
                    self.logger.debug("Frame captured (no calibration applied)")
                    return success_status("Frame captured", 
                                        data=calibrated_frame, 
                                        details=frame_details)
            else:
                self.logger.warning(f"Calibration failed: {calibration_status.message}, returning uncalibrated frame")
                return success_status("Frame captured (calibration failed)", 
                                    data=frame_data, 
                                    details=frame_details)
                
        except Exception as e:
            self.logger.error(f"Error capturing ASCOM frame: {e}")
            return error_status(f"Error capturing ASCOM frame: {e}")
    
    def capture_single_frame_alpaca(self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1) -> CameraStatus:
        """Captures a single frame with Alpaca camera.
        Args:
            exposure_time_s: Exposure time in seconds
            gain: Gain value (optional, uses config default if None)
            binning: Binning factor (default: 1)
        Returns:
            CameraStatus: Status object with frame or error.
        """
        if not self.camera:
            return error_status("Alpaca camera not connected")
        
        try:
            # Use configuration defaults if not provided
            if gain is None:
                gain = self.gain
            
            # Set camera parameters
            try:
                # Set gain if provided
                if gain is not None:
                    self.camera.gain = gain
                
                # Set binning - ensure it's an integer, not a list
                if isinstance(binning, list):
                    binning_value = binning[0] if len(binning) > 0 else 1
                else:
                    binning_value = int(binning)
                
                if binning_value != 1:
                    self.camera.bin_x = binning_value
                    self.camera.bin_y = binning_value
                
                # Set offset if available
                if hasattr(self.camera, 'offset'):
                    self.camera.offset = self.offset
                
                # Set readout mode if available
                if hasattr(self.camera, 'readout_mode'):
                    self.camera.readout_mode = self.readout_mode
                    
            except Exception as e:
                self.logger.warning(f"Could not set camera parameters: {e}")
            
            # Start exposure
            self.logger.debug(f"Starting Alpaca exposure: {exposure_time_s}s, gain={gain}, binning={binning_value}")
            self.logger.info(f"DEBUG: About to call camera.start_exposure with duration={exposure_time_s}s")
            self.camera.start_exposure(exposure_time_s, light=True)
            
            # Wait for exposure to complete with proper timeout handling
            start_time = time.time()
            timeout = exposure_time_s + 30  # 30s extra timeout
            
            while not self.camera.image_ready:
                time.sleep(0.1)
                # Add timeout protection
                if time.time() - start_time > timeout:
                    self.logger.error("Exposure timeout")
                    return error_status("Exposure timeout")
            
            # Get image data
            image_data = self.camera.get_image_array()
            if image_data is None:
                return error_status("Failed to get image data from Alpaca camera")
            
            # Get effective dimensions
            effective_width = self.camera.camera_x_size
            effective_height = self.camera.camera_y_size
            
            # Check if debayering is needed
            if self.camera.is_color_camera():
                # For color cameras, image_data is already debayered
                frame_data = image_data
                frame_details = {
                    'exposure_time_s': exposure_time_s, 
                    'gain': gain, 
                    'binning': binning_value, 
                    'offset': getattr(self.camera, 'offset', None),
                    'readout_mode': getattr(self.camera, 'readout_mode', None),
                    'dimensions': f"{effective_width}x{effective_height}", 
                    'debayered': True
                }
            else:
                # For monochrome cameras
                frame_data = image_data
                frame_details = {
                    'exposure_time_s': exposure_time_s, 
                    'gain': gain, 
                    'binning': binning_value, 
                    'offset': getattr(self.camera, 'offset', None),
                    'readout_mode': getattr(self.camera, 'readout_mode', None),
                    'dimensions': f"{effective_width}x{effective_height}", 
                    'debayered': False
                }
            
            # Apply calibration if enabled and master frames are available
            calibration_status = self.calibration_applier.calibrate_frame(frame_data, exposure_time_s, frame_details)
            
            if calibration_status.is_success:
                calibrated_frame = calibration_status.data
                calibration_details = calibration_status.details
                
                # Update frame details with calibration information
                frame_details.update(calibration_details)
                
                if calibration_details.get('calibration_applied', False):
                    self.logger.info(f"Frame calibrated: Dark={calibration_details.get('dark_subtraction_applied', False)}, "
                                   f"Flat={calibration_details.get('flat_correction_applied', False)}")
                    return success_status("Frame captured and calibrated", 
                                        data=calibrated_frame, 
                                        details=frame_details)
                else:
                    self.logger.debug("Frame captured (no calibration applied)")
                    return success_status("Frame captured", 
                                        data=calibrated_frame, 
                                        details=frame_details)
            else:
                self.logger.warning(f"Calibration failed: {calibration_status.message}, returning uncalibrated frame")
                return success_status("Frame captured (calibration failed)", 
                                    data=frame_data, 
                                    details=frame_details)
                
        except Exception as e:
            self.logger.error(f"Error capturing Alpaca frame: {e}")
            return error_status(f"Error capturing Alpaca frame: {e}")
    
    def save_frame(self, frame: Any, filename: str) -> CameraStatus:
        """Saves a frame as a file.
        Args:
            frame: The image to save (np.ndarray)
            filename: File name
        Returns:
            CameraStatus: Status object with file path or error.
        """
        try:
            output_path = Path(filename)
            file_extension = output_path.suffix.lower()
            
            # For ASCOM cameras, preserve original data for FITS files
            if self.camera_type == 'ascom' and self.camera and file_extension in ['.fit', '.fits']:
                # Save original ASCOM data as FITS
                return self._save_ascom_fits(frame, str(output_path))
            
            # For Alpaca cameras, handle FITS files specially
            if self.camera_type == 'alpaca' and self.camera and file_extension in ['.fit', '.fits']:
                # Save Alpaca data as FITS
                return self._save_alpaca_fits(frame, str(output_path))
            
            # For Alpaca cameras, save as a generic image file
            if self.camera_type == 'alpaca' and self.camera:
                # Convert Alpaca image data to OpenCV format
                frame = self._convert_alpaca_to_opencv(frame)
                if frame is None:
                    return error_status("Failed to convert Alpaca image to OpenCV format")
            
            # Ensure frame is a numpy array
            if not isinstance(frame, np.ndarray):
                frame = np.array(frame)
            
            # Convert to uint8 if needed
            if frame.dtype != np.uint8:
                if frame.dtype == np.float32 or frame.dtype == np.float64:
                    # Normalize to 0-255 range
                    frame = ((frame - frame.min()) / (frame.max() - frame.min()) * 255).astype(np.uint8)
                else:
                    frame = frame.astype(np.uint8)
            
            success = cv2.imwrite(str(output_path), frame)
            if success:
                self.logger.info(f"Frame saved: {output_path.absolute()}")
                # Use appropriate camera identifier
                camera_id = self.camera_index if hasattr(self, 'camera_index') else self.ascom_driver
                return success_status("Frame saved", data=str(output_path.absolute()), details={'camera_id': camera_id})
            else:
                self.logger.error(f"Failed to save frame: {output_path}")
                camera_id = self.camera_index if hasattr(self, 'camera_index') else self.ascom_driver
                return error_status("Failed to save frame", details={'camera_id': camera_id})
        except Exception as e:
            self.logger.error(f"Error saving frame: {e}")
            camera_id = self.camera_index if hasattr(self, 'camera_index') else self.ascom_driver
            return error_status(f"Error saving frame: {e}", details={'camera_id': camera_id})
    
    def _save_ascom_fits(self, frame: Any, filename: str) -> CameraStatus:
        """Saves ASCOM image data as FITS file with proper headers.
        Supports both monochrome and color cameras with debayering.
        Args:
            frame: The image data (could be status object or direct data)
            filename: Output filename
        Returns:
            CameraStatus: Status object with result
        """
        try:
            import astropy.io.fits as fits
            from astropy.time import Time
            
            # Get original ASCOM data
            if hasattr(frame, 'data'):
                # Frame is a status object with data
                image_data = frame.data
            else:
                # Frame is direct data
                image_data = frame
            
            # Ensure it's a numpy array
            if not isinstance(image_data, np.ndarray):
                image_data = np.array(image_data)
            

            
            # Check if this is a color camera
            is_color_camera = False
            bayer_pattern = None
            
            if hasattr(self.camera, 'sensor_type'):
                sensor_type = self.camera.sensor_type
                if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                    is_color_camera = True
                    bayer_pattern = sensor_type
                    self.logger.info(f"Detected color camera with Bayer pattern: {bayer_pattern}")
            
            # For color cameras, we have two options:
            # 1. Save raw Bayer data (for plate-solving)
            # 2. Save debayered color data (for display)
            
            # For plate-solving, we typically want the raw Bayer data
            # But we need to ensure it's in the right format
            
            # Ensure data is in a format that PlateSolve 2 can read
            # PlateSolve 2 prefers 16-bit integer data for best compatibility
            original_dtype = image_data.dtype
            original_min = image_data.min()
            original_max = image_data.max()
            

            
            # Convert to int16 for PlateSolve 2 compatibility
            if image_data.dtype == np.int16:
                # Already int16, keep as is
                pass
            elif image_data.dtype == np.uint16:
                # Convert uint16 to int16 (most common case for ASCOM cameras)
                # Handle potential overflow by clipping
                image_data = np.clip(image_data, 0, 32767).astype(np.int16)
            elif image_data.dtype == np.int32:
                # Convert int32 to int16 (clip to avoid overflow)
                image_data = np.clip(image_data, -32768, 32767).astype(np.int16)
            elif image_data.dtype == np.uint8:
                # Convert uint8 to int16
                image_data = image_data.astype(np.int16)
            elif image_data.dtype == np.float32 or image_data.dtype == np.float64:
                # Convert float to int16 (normalize and clip)
                if original_max > original_min:
                    # Normalize to 0-32767 range
                    image_data = ((image_data - original_min) / (original_max - original_min) * 32767).astype(np.int16)
                else:
                    # All values are the same, set to 0
                    image_data = np.zeros_like(image_data, dtype=np.int16)
            else:
                # Convert other types to int16
                image_data = image_data.astype(np.int16)
            

            
            # Fix image orientation for ASCOM cameras
            # ASCOM images are often rotated 90° compared to other software
            # Transpose the image to correct orientation
            original_shape = image_data.shape
            
            # Check if rotation is needed
            if self._needs_rotation(image_data.shape):
                image_data = np.transpose(image_data)
                self.logger.info(f"Image orientation corrected: {original_shape} -> {image_data.shape}")
            else:
                self.logger.debug(f"Image already in correct orientation: {original_shape}, no rotation needed")
            
            # Note: For 90° rotation (transpose), Bayer patterns remain unchanged
            # RGGB -> RGGB, GRBG -> GRBG, GBRG -> GBRG, BGGR -> BGGR
            # No pattern adjustment needed for this rotation
            
            # Create FITS header with astronomical information
            header = fits.Header()
            
            # REQUIRED FITS headers (FITS Standard)
            header['SIMPLE'] = True
            header['BITPIX'] = image_data.dtype.itemsize * 8
            header['NAXIS'] = len(image_data.shape)
            header['NAXIS1'] = image_data.shape[1] if len(image_data.shape) >= 2 else 1
            header['NAXIS2'] = image_data.shape[0] if len(image_data.shape) >= 2 else 1
            
            # Add NAXIS3 for color images
            if len(image_data.shape) == 3:
                header['NAXIS3'] = image_data.shape[2]
                header['NAXIS'] = 3
            
            # Data scaling (important for PlateSolve 2)
            header['BZERO'] = 0
            header['BSCALE'] = 1
            
            # Standard astronomical headers
            header['DATE'] = Time.now().isot
            header['DATE-OBS'] = Time.now().isot
            header['ORIGIN'] = 'OST Telescope Streaming'
            header['TELESCOP'] = 'OST Telescope'
            header['INSTRUME'] = self.ascom_driver if hasattr(self, 'ascom_driver') else 'Unknown'
            
            # Color camera information
            if is_color_camera:
                header['BAYERPAT'] = bayer_pattern
                header['COLORCAM'] = True
                header['IMAGETYP'] = 'LIGHT'
                self.logger.info(f"Added color camera info: Bayer pattern = {bayer_pattern}")
            else:
                header['COLORCAM'] = False
                header['IMAGETYP'] = 'LIGHT'
            
            # Camera information
            if hasattr(self.camera, 'camera'):
                try:
                    # Try different exposure time property names
                    exposure_time = None
                    for exp_prop in ['ExposureDuration', 'ExposureTime', 'Exposure']:
                        if hasattr(self.camera.camera, exp_prop):
                            try:
                                exposure_time = float(getattr(self.camera.camera, exp_prop))
                                self.logger.debug(f"Found exposure time using property: {exp_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    if exposure_time is not None:
                        header['EXPTIME'] = exposure_time
                    else:
                        # Use the exposure time from our configuration
                        header['EXPTIME'] = float(self.exposure_time)
                        self.logger.debug(f"Using configured exposure time: {self.exposure_time}")
                    
                    # Try different gain property names
                    gain_value = None
                    for gain_prop in ['Gain', 'GainValue', 'CCDGain']:
                        if hasattr(self.camera.camera, gain_prop):
                            try:
                                gain_value = float(getattr(self.camera.camera, gain_prop))
                                self.logger.debug(f"Found gain using property: {gain_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    if gain_value is not None:
                        header['GAIN'] = gain_value
                    else:
                        # Use the gain from our configuration
                        header['GAIN'] = float(self.gain)
                        self.logger.debug(f"Using configured gain: {self.gain}")
                    
                    # Try different binning property names
                    bin_x = None
                    bin_y = None
                    for bin_prop in ['BinX', 'BinningX', 'XBinning']:
                        if hasattr(self.camera.camera, bin_prop):
                            try:
                                bin_x = int(getattr(self.camera.camera, bin_prop))
                                self.logger.debug(f"Found X binning using property: {bin_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    for bin_prop in ['BinY', 'BinningY', 'YBinning']:
                        if hasattr(self.camera.camera, bin_prop):
                            try:
                                bin_y = int(getattr(self.camera.camera, bin_prop))
                                self.logger.debug(f"Found Y binning using property: {bin_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    if bin_x is not None:
                        header['XBINNING'] = bin_x
                    else:
                        header['XBINNING'] = 1
                        self.logger.debug("Using default X binning: 1")
                    
                    if bin_y is not None:
                        header['YBINNING'] = bin_y
                    else:
                        header['YBINNING'] = 1
                        self.logger.debug("Using default Y binning: 1")
                    
                    # Try different subframe property names
                    start_x = None
                    start_y = None
                    num_x = None
                    num_y = None
                    
                    for start_prop in ['StartX', 'SubFrameX', 'XStart']:
                        if hasattr(self.camera.camera, start_prop):
                            try:
                                start_x = int(getattr(self.camera.camera, start_prop))
                                self.logger.debug(f"Found X start using property: {start_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    for start_prop in ['StartY', 'SubFrameY', 'YStart']:
                        if hasattr(self.camera.camera, start_prop):
                            try:
                                start_y = int(getattr(self.camera.camera, start_prop))
                                self.logger.debug(f"Found Y start using property: {start_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    for num_prop in ['NumX', 'SubFrameWidth', 'XSize']:
                        if hasattr(self.camera.camera, num_prop):
                            try:
                                num_x = int(getattr(self.camera.camera, num_prop))
                                self.logger.debug(f"Found X size using property: {num_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    for num_prop in ['NumY', 'SubFrameHeight', 'YSize']:
                        if hasattr(self.camera.camera, num_prop):
                            try:
                                num_y = int(getattr(self.camera.camera, num_prop))
                                self.logger.debug(f"Found Y size using property: {num_prop}")
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    if start_x is not None:
                        header['XORGSUBF'] = start_x
                    else:
                        header['XORGSUBF'] = 0
                        self.logger.debug("Using default X start: 0")
                    
                    if start_y is not None:
                        header['YORGSUBF'] = start_y
                    else:
                        header['YORGSUBF'] = 0
                        self.logger.debug("Using default Y start: 0")
                    
                    # Image dimensions (swapped due to transposition)
                    if num_y is not None:
                        header['NAXIS1'] = int(num_y)  # Width (now height)
                    else:
                        header['NAXIS1'] = int(self.resolution[1])
                    
                    if num_x is not None:
                        header['NAXIS2'] = int(num_x)  # Height (now width)
                    else:
                        header['NAXIS2'] = int(self.resolution[0])
                    
                except Exception as e:
                    self.logger.warning(f"Could not add camera info to FITS header: {e}")
                    # Add basic camera info using configuration values
                    header['EXPTIME'] = float(self.exposure_time)
                    header['GAIN'] = float(self.gain)
                    header['XBINNING'] = 1
                    header['YBINNING'] = 1
                    header['XORGSUBF'] = 0
                    header['YORGSUBF'] = 0
                    header['NAXIS1'] = int(self.resolution[1])
                    header['NAXIS2'] = int(self.resolution[0])
                    self.logger.info("Added basic camera info using configuration values")
            
            # Telescope information
            header['FOCALLEN'] = float(self.config.get_telescope_config().get('focal_length', 1000)) # mm
            header['APERTURE'] = float(self.config.get_telescope_config().get('aperture', 200)) # mm
            # Pixel sizes (swapped due to image transposition)
            header['PIXSIZE1'] = float(self.config.get_camera_config().get('sensor_height', 15.7) / self.resolution[1])  # mm per pixel X (now height)
            header['PIXSIZE2'] = float(self.config.get_camera_config().get('sensor_width', 23.5) / self.resolution[0])    # mm per pixel Y (now width)
            
            # Field of view information (swapped due to image transposition)
            header['FOVW'] = float(self.fov_height)  # Now width after transpose
            header['FOVH'] = float(self.fov_width)   # Now height after transpose
            
            # PlateSolve 2 specific headers
            header['OBJECT'] = 'Unknown'
            header['OBSERVER'] = 'OST System'
            header['SITELAT'] = 0.0  # Default, should be set from config
            header['SITELONG'] = 0.0  # Default, should be set from config
            
            # For plate-solving, we want 2D data
            # If it's a color camera, we need to handle this carefully
            if is_color_camera and len(image_data.shape) == 3:
                # For color cameras, we have several options:
                # 1. Use the green channel (most sensitive for plate-solving)
                # 2. Convert to grayscale
                # 3. Use the first channel
                
                # Option 1: Use green channel (most common for plate-solving)
                if image_data.shape[2] >= 3:
                    # Convert to grayscale using standard RGB weights
                    # Green channel is most sensitive for astronomical imaging
                    green_channel = image_data[:, :, 1]  # Green channel
                    self.logger.info("Using green channel for plate-solving (color camera)")
                    image_data = green_channel
                else:
                    # Use first channel if not RGB
                    image_data = image_data[:, :, 0]
                    self.logger.info("Using first channel for plate-solving (color camera)")
            
            # Ensure 2D array for FITS (PlateSolve 2 requirement)
            if len(image_data.shape) == 1:
                # Convert 1D to 2D
                image_data = image_data.reshape(1, -1)
            elif len(image_data.shape) > 2:
                # Take first 2D slice if 3D or higher
                image_data = image_data[:, :, 0] if len(image_data.shape) == 3 else image_data[:, :]
            
            # Update header with final dimensions
            header['NAXIS'] = len(image_data.shape)
            header['NAXIS1'] = image_data.shape[1]
            header['NAXIS2'] = image_data.shape[0]
            header['BITPIX'] = image_data.dtype.itemsize * 8
            
            # Create FITS file with proper data type
            hdu = fits.PrimaryHDU(image_data, header=header)
            
            # Verify FITS file is valid
            hdu.verify('fix')
            
            # Write to file
            hdu.writeto(filename, overwrite=True, output_verify='fix')
            
            self.logger.info(f"FITS frame saved: {filename}")
            return success_status("FITS frame saved", data=filename, details={'camera_id': self.ascom_driver})
            
        except ImportError:
            self.logger.warning("astropy not available, falling back to OpenCV format")
            return error_status("astropy not available for FITS saving")
        except Exception as e:
            self.logger.error(f"Failed to save FITS: {e}")
            return error_status(f"Failed to save FITS: {e}")
    
    def _save_alpaca_fits(self, frame: Any, filename: str) -> CameraStatus:
        """Saves Alpaca image data as FITS file with proper headers.
        Supports both monochrome and color cameras with debayering.
        Args:
            frame: The image data (could be status object or direct data)
            filename: Output filename
        Returns:
            CameraStatus: Status object with result
        """
        try:
            # Try to import astropy
            try:
                import astropy.io.fits as fits
                from astropy.time import Time
                self.logger.debug("Astropy imported successfully")
            except ImportError as e:
                self.logger.error(f"Astropy not available for FITS saving: {e}")
                return error_status(f"Astropy not available for FITS saving: {e}")
            
            # Debug: Log the type and attributes of the frame object
            self.logger.debug(f"Frame object type: {type(frame)}")
            self.logger.debug(f"Frame object attributes: {dir(frame)}")
            if hasattr(frame, 'data'):
                self.logger.debug(f"Frame.data type: {type(frame.data)}")
                self.logger.debug(f"Frame.data value: {frame.data}")
                # Check for nested Status objects
                if hasattr(frame.data, 'data'):
                    self.logger.debug(f"Frame.data.data type: {type(frame.data.data)}")
                    self.logger.debug(f"Frame.data.data value: {frame.data.data}")
            if hasattr(frame, 'is_success'):
                self.logger.debug(f"Frame.is_success: {frame.is_success}")
            
            # Get original Alpaca data - handle Status objects properly
            image_data = None
            frame_details = {}
            
            if hasattr(frame, 'data') and frame.data is not None:
                # Frame is a status object with data
                if hasattr(frame.data, 'data') and frame.data.data is not None:
                    # Nested Status object - extract the actual data
                    image_data = frame.data.data
                    frame_details = getattr(frame.data, 'details', {})
                    self.logger.debug("Extracted data from nested status object")
                elif hasattr(frame.data, 'is_success') and frame.data.is_success and hasattr(frame.data, 'data'):
                    # Nested success status object
                    image_data = frame.data.data
                    frame_details = getattr(frame.data, 'details', {})
                    self.logger.debug("Extracted data from nested success status object")
                else:
                    # Direct data in status object
                    image_data = frame.data
                    frame_details = getattr(frame, 'details', {})
                    self.logger.debug("Extracted data from status object")
            elif hasattr(frame, 'is_success') and frame.is_success and hasattr(frame, 'data'):
                # Frame is a success status object
                if hasattr(frame.data, 'data') and frame.data.data is not None:
                    # Nested Status object - extract the actual data
                    image_data = frame.data.data
                    frame_details = getattr(frame.data, 'details', {})
                    self.logger.debug("Extracted data from nested status object in success frame")
                else:
                    # Direct data in success status object
                    image_data = frame.data
                    frame_details = getattr(frame, 'details', {})
                    self.logger.debug("Extracted data from success status object")
            else:
                # Frame is direct data
                image_data = frame
                frame_details = {}
                self.logger.debug("Using direct frame data")
            
            # Validate that we have actual image data
            if image_data is None:
                self.logger.error("No image data found in frame")
                return error_status("No image data found in frame")
            

            
            # Ensure it's a numpy array
            if not isinstance(image_data, np.ndarray):
                try:
                    image_data = np.array(image_data)
                except Exception as e:
                    self.logger.error(f"Failed to convert to numpy array: {e}")
                    self.logger.error(f"Image data type: {type(image_data)}")
                    return error_status(f"Failed to convert to numpy array: {e}")
            
            # Log the data properties for debugging
            self.logger.debug(f"Alpaca FITS data: dtype={image_data.dtype}, shape={image_data.shape}")
            
            # Apply orientation correction if needed (same as PNG files)
            original_shape = image_data.shape
            if self._needs_rotation(image_data.shape):
                # For 2D images (monochrome)
                if len(image_data.shape) == 2:
                    image_data = np.transpose(image_data, (1, 0))
                # For 3D images (color)
                elif len(image_data.shape) == 3:
                    image_data = np.transpose(image_data, (1, 0, 2))
                self.logger.info(f"Alpaca FITS orientation corrected: {original_shape} -> {image_data.shape}")
            else:
                self.logger.debug(f"Alpaca FITS already in correct orientation: {original_shape}, no rotation needed")
            
            # Check if this is a color camera
            is_color_camera = False
            bayer_pattern = None
            
            # For Alpaca cameras, we need to determine color from sensor type
            if hasattr(self.camera, 'sensor_type'):
                sensor_type = self.camera.sensor_type
                if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                    is_color_camera = True
                    bayer_pattern = sensor_type
                    self.logger.info(f"Detected color camera with Bayer pattern: {bayer_pattern}")
            
            # Ensure data is in a format that PlateSolve 2 can read
            # PlateSolve 2 prefers 16-bit integer data for best compatibility
            if image_data.dtype != np.uint16:
                if image_data.dtype in [np.float32, np.float64]:
                    # Convert float data to 16-bit integer
                    # Normalize to 0-65535 range
                    data_min = image_data.min()
                    data_max = image_data.max()
                    if data_max > data_min:
                        image_data = ((image_data - data_min) / (data_max - data_min) * 65535).astype(np.uint16)
                    else:
                        image_data = image_data.astype(np.uint16)
                else:
                    # Convert to 16-bit
                    image_data = image_data.astype(np.uint16)
            
            # Create FITS header with astronomical information
            header = fits.Header()
            
            # Basic image information
            header['NAXIS'] = len(image_data.shape)
            header['NAXIS1'] = image_data.shape[1] if len(image_data.shape) >= 2 else 1
            header['NAXIS2'] = image_data.shape[0] if len(image_data.shape) >= 2 else 1
            if len(image_data.shape) == 3:
                header['NAXIS3'] = image_data.shape[2]
            
            # Data type information
            header['BITPIX'] = 16  # 16-bit integer
            header['BZERO'] = 0
            header['BSCALE'] = 1
            
            # Camera information
            header['CAMERA'] = 'Alpaca'
            if hasattr(self.camera, 'name'):
                header['CAMNAME'] = self.camera.name
            
            # Sensor information
            if hasattr(self, 'sensor_width') and hasattr(self, 'sensor_height'):
                header['XPIXSZ'] = self.pixel_size  # Pixel size in microns
                header['YPIXSZ'] = self.pixel_size
                header['XBAYROFF'] = 0
                header['YBAYROFF'] = 0
            
            # Color camera information
            if is_color_camera and bayer_pattern:
                header['BAYERPAT'] = bayer_pattern
                header['COLORTYP'] = 'COLOR'
            else:
                header['COLORTYP'] = 'MONO'
            
            # Exposure information - use actual values from frame details
            actual_exposure_time = frame_details.get('exposure_time_s')
            if actual_exposure_time is not None:
                header['EXPTIME'] = actual_exposure_time
            elif hasattr(self.camera, 'exposure_time'):
                header['EXPTIME'] = self.camera.exposure_time
            
            actual_gain = frame_details.get('gain')
            if actual_gain is not None:
                header['GAIN'] = actual_gain
            elif hasattr(self.camera, 'gain'):
                header['GAIN'] = self.camera.gain
            
            actual_binning = frame_details.get('binning')
            if actual_binning is not None:
                if isinstance(actual_binning, list):
                    header['XBINNING'] = actual_binning[0]
                    header['YBINNING'] = actual_binning[1]
                else:
                    header['XBINNING'] = actual_binning
                    header['YBINNING'] = actual_binning
            elif hasattr(self.camera, 'bin_x') and hasattr(self.camera, 'bin_y'):
                header['XBINNING'] = self.camera.bin_x
                header['YBINNING'] = self.camera.bin_y
            
            # Temperature information
            if hasattr(self.camera, 'ccdtemperature'):
                header['CCD-TEMP'] = self.camera.ccdtemperature
            
            # Timestamp
            header['DATE-OBS'] = Time.now().isot
            
            # Create FITS file
            hdu = fits.PrimaryHDU(image_data, header=header)
            hdu.writeto(filename, overwrite=True)
            
            # Verify file was created
            if os.path.exists(filename):
                self.logger.info(f"Alpaca FITS file saved successfully: {filename}")
                return success_status("Alpaca FITS file saved", data=filename)
            else:
                self.logger.error(f"FITS file was not created: {filename}")
                return error_status("FITS file was not created")
            
        except Exception as e:
            self.logger.error(f"Error saving Alpaca FITS file: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return error_status(f"Error saving Alpaca FITS file: {e}")
    
    def get_camera_info(self) -> dict[str, Any]:
        """Get comprehensive camera information.
        
        Returns:
            dict: Camera information including cooling status
        """
        info = {
            'camera_type': self.camera_type,
            'connected': self.camera is not None,
            'frame_width': self.resolution[0],
            'frame_height': self.resolution[1],
            'fps': self.frame_rate,
            'exposure_time': self.exposure_time,
            'gain': self.gain,
            'field_of_view': self.get_field_of_view(),
            'sampling': self.get_sampling_arcsec_per_pixel()
        }
        
        # Add ASCOM-specific information
        if self.camera_type == 'ascom' and self.camera:
            info.update({
                'driver_id': self.ascom_driver,
                'has_cooling': self.enable_cooling,
                'cooling_enabled': self.enable_cooling,
                        'target_temperature': self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0),
        'wait_for_cooling': self.config.get_camera_config().get('cooling', {}).get('wait_for_cooling', True),
                'has_offset': hasattr(self.camera, 'has_offset') and self.camera.has_offset(),
                'has_readout_mode': hasattr(self.camera, 'has_readout_mode') and self.camera.has_readout_mode(),
                'offset': self.offset,
                'readout_mode': self.readout_mode
            })
            
            # Get current cooling status if available
            if self.enable_cooling:
                cooling_status = self.get_cooling_status()
                info.update(cooling_status)
        
        # Add Alpaca-specific information
        if self.camera_type == 'alpaca' and self.camera:
            info.update({
                'host': self.alpaca_host,
                'port': self.alpaca_port,
                'camera_name': self.alpaca_camera_name,
                'is_color': hasattr(self.camera, 'is_color_camera') and self.camera.is_color_camera(),
                'has_cooling': hasattr(self.camera, 'has_cooling') and self.camera.has_cooling(),
                'has_offset': hasattr(self.camera, 'has_offset') and self.camera.has_offset(),
                'has_readout_mode': hasattr(self.camera, 'has_readout_mode') and self.camera.has_readout_mode(),
                'offset': self.offset,
                'readout_mode': self.readout_mode
            })
            if hasattr(self.camera, 'has_cooling') and self.camera.has_cooling():
                cooling_status = self.get_cooling_status()
                info.update(cooling_status)
        
        return info 

    def has_cooling(self) -> bool:
        """Check if the camera supports cooling.
        
        Returns:
            bool: True if cooling is supported
        """
        if self.camera_type == 'ascom' and self.camera:
            return self.enable_cooling
        elif self.camera_type == 'alpaca' and self.camera:
            return self.enable_cooling
        return False
    
    def enable_cooling_system(self) -> CameraStatus:
        """Enable the camera cooling system.
        
        Returns:
            CameraStatus: Status of the operation
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        
        if not self.enable_cooling:
            return error_status("Cooling is disabled in configuration")
        
        try:
            # Turn on the cooler
            cooler_status = self.camera.set_cooler_on(True) if self.camera_type == 'ascom' else self.camera.set_cooler_on(True)
            if not cooler_status.is_success:
                return cooler_status
            
            # Set target temperature
            temp_status = self.camera.set_cooling(self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0)) if self.camera_type == 'ascom' else self.camera.set_cooling(self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0))
            if not temp_status.is_success:
                return temp_status
            
            self.logger.info(f"Cooling system enabled, target temperature: {self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0)}°C")
            
            # Wait for target temperature if configured
            if self.wait_for_cooling:
                return self.wait_for_target_temperature()
            
            return success_status(f"Cooling system enabled, target: {self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0)}°C")
            
        except Exception as e:
            self.logger.error(f"Error enabling cooling system: {e}")
            return error_status(f"Failed to enable cooling system: {e}")
    
    def disable_cooling_system(self) -> CameraStatus:
        """Disable the camera cooling system.
        
        Returns:
            CameraStatus: Status of the operation
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        
        try:
            # Turn off the cooler
            status = self.camera.turn_cooling_off() if self.camera_type == 'ascom' else self.camera.turn_cooling_off()
            if status.is_success:
                self.logger.info("Cooling system disabled")
            return status
            
        except Exception as e:
            self.logger.error(f"Error disabling cooling system: {e}")
            return error_status(f"Failed to disable cooling system: {e}")
    
    def set_target_temperature(self, temperature: float) -> CameraStatus:
        """Set the target temperature for cooling.
        
        Args:
            temperature: Target temperature in Celsius
            
        Returns:
            CameraStatus: Status of the operation
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        
        if not self.enable_cooling:
            return error_status("Cooling is disabled in configuration")
        
        try:
            status = self.camera.set_cooling(temperature) if self.camera_type == 'ascom' else self.camera.set_cooling(temperature)
            if status.is_success:
                self.config.get_camera_config()['cooling']['target_temperature'] = temperature # Update config
                self.logger.info(f"Target temperature set to {temperature}°C")
            return status
            
        except Exception as e:
            self.logger.error(f"Error setting target temperature: {e}")
            return error_status(f"Failed to set target temperature: {e}")
    
    def get_cooling_status(self) -> dict[str, Any]:
        """Get current cooling status.
        
        Returns:
            dict: Cooling status information
        """
        if not self.has_cooling():
            return {
                'cooling_supported': False,
                'cooling_enabled': False
            }
        
        try:
            # Get fresh cooling information
            if self.camera_type == 'ascom':
                cooling_info = self.camera.get_smart_cooling_info()
            elif self.camera_type == 'alpaca':
                cooling_info = self.camera.get_cooling_status()
            
            if cooling_info.is_success:
                info = cooling_info.data
                return {
                    'cooling_supported': True,
                    'cooling_enabled': self.enable_cooling,
                    'current_temperature': info.get('temperature'),
                    'target_temperature': info.get('target_temperature'),
                    'cooler_power': info.get('cooler_power'),
                    'cooler_on': info.get('cooler_on'),
                    'temperature_stable': self._is_temperature_stable(info.get('temperature'), info.get('target_temperature'))
                }
            else:
                return {
                    'cooling_supported': True,
                    'cooling_enabled': self.enable_cooling,
                    'error': cooling_info.message
                }
                
        except Exception as e:
            self.logger.error(f"Error getting cooling status: {e}")
            return {
                'cooling_supported': True,
                'cooling_enabled': self.enable_cooling,
                'error': str(e)
            }
    
    def wait_for_target_temperature(self) -> CameraStatus:
        """Wait for the camera to reach the target temperature.
        
        Returns:
            CameraStatus: Status of the operation
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        
        if not self.wait_for_cooling:
            return success_status("Waiting for cooling disabled in configuration")
        
        try:
            import time
            start_time = time.time()
            
            self.logger.info(f"Waiting for target temperature: {self.config.get_camera_config().get('cooling', {}).get('target_temperature', -10.0)}°C")
            
            while time.time() - start_time < self.cooling_timeout:
                cooling_status = self.get_cooling_status()
                
                if 'error' in cooling_status:
                    return error_status(f"Error monitoring temperature: {cooling_status['error']}")
                
                current_temp = cooling_status.get('current_temperature')
                target_temp = cooling_status.get('target_temperature')
                
                if current_temp is not None and target_temp is not None:
                    temp_diff = abs(current_temp - target_temp)
                    
                    if temp_diff <= self.config.get_camera_config().get('cooling', {}).get('stabilization_tolerance', 1.0):
                        self.logger.info(f"Target temperature reached: {current_temp:.1f}°C (target: {target_temp:.1f}°C)")
                        return success_status(f"Target temperature reached: {current_temp:.1f}°C")
                    
        
                
                time.sleep(2)  # Check every 2 seconds
            
            return error_status(f"Timeout waiting for target temperature after {self.cooling_timeout}s")
            
        except Exception as e:
            self.logger.error(f"Error waiting for target temperature: {e}")
            return error_status(f"Failed to wait for target temperature: {e}")
    
    def _is_temperature_stable(self, current_temp: Optional[float], target_temp: Optional[float]) -> bool:
        """Check if the temperature is stable at the target.
        
        Args:
            current_temp: Current temperature
            target_temp: Target temperature
            
        Returns:
            bool: True if temperature is stable
        """
        if current_temp is None or target_temp is None:
            return False
        
        temp_diff = abs(current_temp - target_temp)
        return temp_diff <= self.config.get_camera_config().get('cooling', {}).get('stabilization_tolerance', 1.0)
    
    def initialize_cooling(self) -> CameraStatus:
        """Initialize camera cooling system with improved status detection."""
        if not self.has_cooling():
            return warning_status("Cooling not supported by this camera")
        
        try:
            self.logger.info("Initializing camera cooling system...")
            
            # Get current cooling status
            if self.camera_type == 'ascom':
                cooling_info = self.camera.get_smart_cooling_info()
            elif self.camera_type == 'alpaca':
                cooling_info = self.camera.get_cooling_status()
            
            if not cooling_info.is_success:
                return error_status(f"Failed to get cooling info: {cooling_info.message}")
            
            info = cooling_info.data
            current_temp = info.get('temperature')
            target_temp = info.get('target_temperature')
            
            self.logger.info(f"Current temperature: {current_temp}°C, Target: {target_temp}°C")
            
            # If cooling is enabled and target temperature is set
            if self.enable_cooling and target_temp is not None:
                self.logger.info(f"Setting target temperature to {target_temp}°C")
                
                # Set cooling with improved method
                cooling_status = self.camera.set_cooling(target_temp) if self.camera_type == 'ascom' else self.camera.set_cooling(target_temp)
                if not cooling_status.is_success:
                    return error_status(f"Failed to set cooling: {cooling_status.message}")
                
                self.logger.info(f"Cooling set successfully: {cooling_status.message}")
                
                # Force refresh cooling status to get accurate power readings
                self.logger.info("Forcing cooling status refresh...")
                refresh_status = self.camera.force_refresh_cooling_status() if self.camera_type == 'ascom' else self.camera.force_refresh_cooling_status()
                if refresh_status.is_success:
                    refresh_info = refresh_status.data
                    self.logger.info(f"Cooling status refreshed: temp={refresh_info.get('temperature')}°C, "
                                   f"power={refresh_info.get('cooler_power')}%")
                
                # Wait for cooling to stabilize if configured
                if self.wait_for_cooling:
                    self.logger.info(f"Waiting for cooling to stabilize (timeout: {self.cooling_timeout}s)...")
                    stabilization_status = self.camera.wait_for_cooling_stabilization(
                        timeout=self.cooling_timeout, 
                        check_interval=2.0
                    ) if self.camera_type == 'ascom' else self.camera.wait_for_cooling_stabilization(
                        timeout=self.cooling_timeout, 
                        check_interval=2.0
                    )
                    
                    if stabilization_status.is_success:
                        final_info = stabilization_status.data
                        self.logger.info(f"Cooling stabilized: temp={final_info.get('temperature')}°C, "
                                       f"power={final_info.get('cooler_power')}%")
                    else:
                        self.logger.warning(f"Cooling stabilization: {stabilization_status.message}")
                
                return success_status("Camera cooling initialized successfully", data=cooling_status.data)
            
            else:
                self.logger.info("Cooling initialization skipped (not enabled or no target temperature)")
                return success_status("Cooling initialization skipped", data=info)
                
        except Exception as e:
            self.logger.error(f"Error initializing cooling: {e}")
            return error_status(f"Failed to initialize cooling: {e}")
    
    def _convert_ascom_to_opencv(self, ascom_image_data):
        """Convert ASCOM image data to OpenCV format with debayering.
        Supports both monochrome and color cameras with automatic Bayer pattern detection.
        Args:
            ascom_image_data: Raw image data from ASCOM camera
        Returns:
            numpy.ndarray: OpenCV-compatible image array or None if conversion fails
        """
        try:
            # Check if image data is None or empty
            if ascom_image_data is None:
                self.logger.error("ASCOM image data is None")
                return None
            
            # Convert ASCOM image array to numpy array
            image_array = np.array(ascom_image_data)
            
            # Check if array is empty or has invalid shape
            if image_array.size == 0:
                self.logger.error("ASCOM image array is empty")
                return None
            
            # Log the original data type and shape for debugging
            self.logger.debug(f"ASCOM image data type: {image_array.dtype}, shape: {image_array.shape}")
            
            # Convert data type to uint16 first (most ASCOM cameras use 16-bit)
            if image_array.dtype == np.int32:
                # For 32-bit signed integers, convert to uint16
                image_array = image_array.astype(np.uint16)
            elif image_array.dtype == np.float32 or image_array.dtype == np.float64:
                # For floating point, normalize to uint16
                image_array = ((image_array - image_array.min()) / (image_array.max() - image_array.min()) * 65535).astype(np.uint16)
            elif image_array.dtype != np.uint8 and image_array.dtype != np.uint16:
                # For other types, try to convert to uint16
                image_array = image_array.astype(np.uint16)
            
            # Check if camera is color (has Bayer pattern)
            is_color_camera = False
            bayer_pattern = None
            
            if hasattr(self.camera, 'sensor_type'):
                sensor_type = self.camera.sensor_type
                if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                    is_color_camera = True
                    bayer_pattern = sensor_type
                    self.logger.debug(f"Detected color camera with Bayer pattern: {bayer_pattern}")
            
            # If already 3-channel (already debayered), handle as is
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                self.logger.debug("Image is already 3-channel RGB, proceeding with orientation correction")
                result_image = image_array
            else:
                # Apply debayering for color cameras FIRST (before rotation)
                if is_color_camera and bayer_pattern:
                    # Apply debayering based on Bayer pattern
                    if bayer_pattern == 'RGGB':
                        bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
                    elif bayer_pattern == 'GRBG':
                        bayer_pattern_cv2 = cv2.COLOR_BayerGR2BGR
                    elif bayer_pattern == 'GBRG':
                        bayer_pattern_cv2 = cv2.COLOR_BayerGB2BGR
                    elif bayer_pattern == 'BGGR':
                        bayer_pattern_cv2 = cv2.COLOR_BayerBG2BGR
                    else:
                        self.logger.warning(f"Unknown Bayer pattern: {bayer_pattern}, using RGGB")
                        bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
                    
                    # Apply debayering
                    try:
                        result_image = cv2.cvtColor(image_array, bayer_pattern_cv2)
                        self.logger.debug(f"Successfully debayered image with {bayer_pattern} pattern")
                    except Exception as e:
                        self.logger.warning(f"Debayering failed: {e}, falling back to grayscale")
                        # Fall back to grayscale conversion
                        result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
                else:
                    # For monochrome cameras, convert to 3-channel grayscale
                    if len(image_array.shape) == 2:
                        self.logger.debug("Converting monochrome image to 3-channel")
                        result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
                    elif len(image_array.shape) == 3:
                        # If already 3-channel but not RGB (e.g., RGBA), convert to BGR
                        if image_array.shape[2] == 4:  # RGBA
                            self.logger.debug("Converting RGBA to BGR")
                            result_image = cv2.cvtColor(image_array, cv2.COLOR_RGBA2BGR)
                        elif image_array.shape[2] == 1:  # Single channel
                            self.logger.debug("Converting single channel to 3-channel")
                            result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
                        else:
                            self.logger.debug("Returning existing 3-channel image")
                            result_image = image_array
                    else:
                        # Fallback: assume monochrome and convert
                        self.logger.debug("Fallback: converting to 3-channel grayscale")
                        result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            
            # NOW apply orientation correction to the debayered RGB image
            # This is much simpler and more robust than rotating Bayer patterns
            original_shape = result_image.shape
            
            # Check if rotation is needed
            if self._needs_rotation(result_image.shape):
                result_image = np.transpose(result_image, (1, 0, 2))  # Transpose only spatial dimensions
                self.logger.info(f"Image orientation corrected: {original_shape} -> {result_image.shape}")
                
                # Debug: Check if the rotation actually changed the dimensions
                if original_shape[0] == result_image.shape[1] and original_shape[1] == result_image.shape[0]:
                    self.logger.info(f"[OK] Rotation applied successfully: {original_shape} -> {result_image.shape}")
                else:
                    self.logger.warning(f"[WARNING] Rotation may not have worked as expected: {original_shape} -> {result_image.shape}")
            else:
                self.logger.debug(f"Image already in correct orientation: {original_shape}, no rotation needed")
            
            return result_image
            
        except Exception as e:
            self.logger.error(f"Error converting ASCOM image: {e}")
            return None 

    def _convert_alpaca_to_opencv(self, alpaca_image_data):
        """Convert Alpaca image data to OpenCV format.
        Args:
            alpaca_image_data: Raw image data from Alpaca camera or Status object
        Returns:
            numpy.ndarray: OpenCV-compatible image array or None if conversion fails
        """
        try:
            # Check if input is a Status object and extract data
            if hasattr(alpaca_image_data, 'data'):
                # It's a Status object, extract the data
                image_data = alpaca_image_data.data
            else:
                # It's direct data
                image_data = alpaca_image_data
            
            # Check if image data is None or empty
            if image_data is None:
                self.logger.error("Alpaca image data is None")
                return None
            
            # Convert Alpaca image array to numpy array
            image_array = np.array(image_data)
            
            # Check if array is empty or has invalid shape
            if image_array.size == 0:
                self.logger.error("Alpaca image array is empty")
                return None
            
            # Log the original data type and shape for debugging
            self.logger.debug(f"Alpaca image data type: {image_array.dtype}, shape: {image_array.shape}")
            
            # Ensure it's a numpy array
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)
            
            # Convert to uint8 if needed
            if image_array.dtype != np.uint8:
                if image_array.dtype == np.float32 or image_array.dtype == np.float64:
                    # Normalize to 0-255 range
                    image_array = ((image_array - image_array.min()) / (image_array.max() - image_array.min()) * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)
            
            # Ensure it's 3-channel (OpenCV expects BGR)
            if len(image_array.shape) == 2:
                self.logger.debug("Converting monochrome Alpaca image to 3-channel")
                result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            elif len(image_array.shape) == 3:
                # If it's already 3-channel (e.g., RGBA), convert to BGR
                if image_array.shape[2] == 4:
                    self.logger.debug("Converting RGBA to BGR")
                    result_image = cv2.cvtColor(image_array, cv2.COLOR_RGBA2BGR)
                else:
                    # Assume it's RGB and convert to BGR
                    self.logger.debug("Converting RGB to BGR")
                    result_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            else:
                # Fallback: assume monochrome and convert
                self.logger.debug("Fallback: converting to 3-channel grayscale")
                result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            
            # Apply orientation correction if needed (Alpaca images are typically landscape)
            original_shape = result_image.shape
            if self._needs_rotation(result_image.shape):
                result_image = np.transpose(result_image, (1, 0, 2)) # Transpose spatial dimensions
                self.logger.info(f"Alpaca image orientation corrected: {original_shape} -> {result_image.shape}")
            else:
                self.logger.debug(f"Alpaca image already in correct orientation: {original_shape}, no rotation needed")
            
            return result_image
            
        except Exception as e:
            self.logger.error(f"Error converting Alpaca image: {e}")
            return None

    def _needs_rotation(self, image_shape: tuple) -> bool:
        """Check if the image needs rotation based on its dimensions.
        
        ASCOM cameras typically provide images with long side vertical,
        but we want long side horizontal for display.
        
        Args:
            image_shape: Tuple of (height, width) or (height, width, channels)
        Returns:
            bool: True if rotation is needed, False otherwise
        """
        if len(image_shape) >= 2:
            height, width = image_shape[0], image_shape[1]
            
            # If height > width, the long side is vertical (needs rotation)
            # If width > height, the long side is horizontal (no rotation needed)
            needs_rotation = height > width
            
            self.logger.debug(f"Image dimensions: {width}x{height}, needs rotation: {needs_rotation}")
            return needs_rotation
        
        return False 