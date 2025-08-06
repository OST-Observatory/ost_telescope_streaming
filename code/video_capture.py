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
from datetime import datetime

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
        
        # Frame processing configuration
        frame_config = config.get_frame_processing_config()
        self.camera_type = config.get_camera_config().get('camera_type', 'opencv')
        self.camera_index = config.get_camera_config().get('opencv', {}).get('camera_index', 0)
        self.exposure_time = config.get_camera_config().get('opencv', {}).get('exposure_time', 1.0)
        self.gain = config.get_camera_config().get('ascom', {}).get('gain', 100.0)
        self.offset = config.get_camera_config().get('ascom', {}).get('offset', 50.0)
        self.readout_mode = config.get_camera_config().get('ascom', {}).get('readout_mode', 0)
        self.binning = config.get_camera_config().get('ascom', {}).get('binning', 1)
        self.frame_rate = config.get_camera_config().get('opencv', {}).get('fps', 30)
        self.resolution = config.get_camera_config().get('opencv', {}).get('resolution', [1920, 1080])
        self.frame_enabled = frame_config.get('enabled', True)
        
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
            output_dir = Path(self.config.get_frame_processing_config().get('output_dir', 'captured_frames'))
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
            
            if not self.enable_cooling:  # OpenCV cameras don't have auto-exposure
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
                    ascom_config = self.config.get_camera_config().get('ascom', {})
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
                    # OpenCV camera logic - continuous capture
                    if self.cap and self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret:
                            with self.frame_lock:
                                self.current_frame = frame.copy()
                        else:
                            self.logger.warning("Failed to read frame from OpenCV camera")
                            time.sleep(0.1)
                            
                elif self.camera_type in ['ascom', 'alpaca']:
                    # For ASCOM and Alpaca cameras, make captures but don't save files
                    # The VideoProcessor will handle file saving and plate-solving
                    if self.camera:
                        if self.camera_type == 'alpaca':
                            # Use exposure time from alpaca config
                            alpaca_config = self.config.get_camera_config().get('alpaca', {})
                            exposure_time = alpaca_config.get('exposure_time', 1.0)  # seconds
                            gain = alpaca_config.get('gain', None)
                            binning = alpaca_config.get('binning', [1, 1])
                            status = self.capture_single_frame_alpaca(exposure_time, gain, binning)
                        else:  # ascom
                            # Use ASCOM-specific settings
                            ascom_config = self.config.get_camera_config().get('ascom', {})
                            exposure_time = ascom_config.get('exposure_time', 1.0)  # seconds
                            gain = ascom_config.get('gain', None)
                            binning = ascom_config.get('binning', 1)
                            status = self.capture_single_frame_ascom(exposure_time, gain, binning)
                        
                        if status.is_success:
                            # Store raw camera data in current_frame (no conversion here)
                            # Conversion will happen only when needed for display
                            with self.frame_lock:
                                self.current_frame = status
                        else:
                            self.logger.warning(f"Failed to capture frame from {self.camera_type} camera: {status.message}")
                            time.sleep(0.1)
                    else:
                        self.logger.warning(f"{self.camera_type.upper()} camera not available")
                        time.sleep(0.1)
                    
                    # Sleep between captures to avoid overwhelming the camera
                    time.sleep(5)  # 5 second interval between captures
                            
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Returns the last captured frame."""
        with self.frame_lock:
            if self.current_frame is None:
                return None
            
            # Handle Status objects
            if hasattr(self.current_frame, 'data'):
                # It's a Status object, extract the data
                frame_data = self.current_frame.data
                if hasattr(frame_data, 'data'):
                    # Nested Status object
                    return frame_data.data
                else:
                    return frame_data
            else:
                # It's direct data
                return self.current_frame
    
    def capture_single_frame(self) -> CameraStatus:
        """Captures a single frame and returns status.
        Returns:
            CameraStatus: Status object with frame or error.
        """
        if self.camera_type == 'ascom' and self.camera:
            # Use ASCOM-specific settings
            ascom_config = self.config.get_camera_config().get('ascom', {})
            exposure_time = ascom_config.get('exposure_time', 1.0)  # seconds
            gain = ascom_config.get('gain', None)
            binning = ascom_config.get('binning', 1)
            return self.capture_single_frame_ascom(exposure_time, gain, binning)
        elif self.camera_type == 'alpaca' and self.camera:
            # Use exposure time from alpaca config
            alpaca_config = self.config.get_camera_config().get('alpaca', {})
            exposure_time = alpaca_config.get('exposure_time', 1.0)  # seconds
            gain = alpaca_config.get('gain', None)
            binning = alpaca_config.get('binning', [1, 1])
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
            
            # For FITS files, use unified function for all camera types
            if file_extension in ['.fit', '.fits']:
                return self._save_fits_unified(frame, str(output_path))
            
            # For image files (PNG, JPG, etc.), use unified function with conversion
            return self._save_image_file(frame, str(output_path))
        except Exception as e:
            self.logger.error(f"Error saving frame: {e}")
            camera_id = self.camera_index if hasattr(self, 'camera_index') else self.ascom_driver
            return error_status(f"Error saving frame: {e}", details={'camera_id': camera_id})
    
    # DEPRECATED: Use _save_fits_unified() instead
    # This function has been replaced by _save_fits_unified() which works for all camera types
    def _save_alpaca_fits(self, frame: Any, filename: str) -> CameraStatus:
        """DEPRECATED: Use _save_fits_unified() instead.
        
        This function has been replaced by _save_fits_unified() which provides
        unified FITS saving for all camera types (ASCOM, Alpaca, etc.).
        """
        self.logger.warning("_save_alpaca_fits is deprecated, use _save_fits_unified instead")
        return self._save_fits_unified(frame, filename)
    
    def _save_fits_unified(self, frame: Any, filename: str) -> CameraStatus:
        """Save camera frame as FITS file (unified for all camera types).
        
        This function works for both ASCOM and Alpaca cameras, treating them
        as astronomical cameras with similar data formats.
        
        Args:
            frame: Raw image data from camera (Status object or direct data)
            filename: Output filename for FITS file
            
        Returns:
            CameraStatus: Success or error status
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
            
            # Get original data - handle Status objects properly
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
            
            # Method 1: Check sensor type from camera
            if hasattr(self.camera, 'sensor_type'):
                sensor_type = self.camera.sensor_type
                if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                    is_color_camera = True
                    bayer_pattern = sensor_type
                    self.logger.info(f"Detected color camera with Bayer pattern: {bayer_pattern}")
            
            # Method 2: Check if auto_debayer is enabled in config
            if not is_color_camera:
                camera_config = self.config.get_camera_config()
                auto_debayer = camera_config.get('auto_debayer', False)
                if auto_debayer:
                    debayer_method = camera_config.get('debayer_method', 'RGGB')
                    if debayer_method in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                        is_color_camera = True
                        bayer_pattern = debayer_method
                        self.logger.info(f"Color camera detected via config, Bayer pattern: {bayer_pattern}")
            
            # Method 3: Check camera name for color indicators
            if not is_color_camera and hasattr(self.camera, 'name'):
                camera_name = self.camera.name.lower()
                color_indicators = ['color', 'rgb', 'bayer', 'asi2600mc', 'asi2600mmc', 'qhy600c', 'qhy600mc']
                if any(indicator in camera_name for indicator in color_indicators):
                    is_color_camera = True
                    bayer_pattern = 'RGGB'  # Default for most color cameras
                    self.logger.info(f"Color camera detected via name: {camera_name}, using default Bayer pattern: {bayer_pattern}")
            
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
            if frame_details is not None:
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
            else:
                # Fallback to camera attributes if frame_details is None
                if hasattr(self.camera, 'exposure_time'):
                    header['EXPTIME'] = self.camera.exposure_time
                if hasattr(self.camera, 'gain'):
                    header['GAIN'] = self.camera.gain
                if hasattr(self.camera, 'bin_x') and hasattr(self.camera, 'bin_y'):
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
    
    def _save_image_file(self, frame: Any, filename: str) -> CameraStatus:
        """Save frame as image file (PNG, JPG, etc.) with conversion to OpenCV format.
        
        Args:
            frame: Raw image data from camera (Status object or direct data)
            filename: Output filename
            
        Returns:
            CameraStatus: Success or error status
        """
        try:
            # Extract data from Status object if needed
            if hasattr(frame, 'data'):
                # Frame is a Status object, extract the data
                frame_data = frame.data
            else:
                # Frame is direct data
                frame_data = frame
            
            # Convert camera data to OpenCV format for display
            if self.camera_type == 'alpaca' or self.camera_type == 'ascom':
                frame = self._convert_to_opencv(frame_data)
            else:
                # For other camera types, assume it's already in OpenCV format
                frame = frame_data
            
            if frame is None:
                return error_status("Failed to convert camera image to OpenCV format")
            
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
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Save image file
            success = cv2.imwrite(filename, frame)
            if success:
                self.logger.info(f"Image file saved: {filename}")
                return success_status("Image file saved", data=filename)
            else:
                self.logger.error(f"Failed to save image file: {filename}")
                return error_status("Failed to save image file")
                
        except Exception as e:
            self.logger.error(f"Error saving image file: {e}")
            return error_status(f"Error saving image file: {e}")

    def _convert_to_opencv(self, image_data):
        """Convert camera image data to OpenCV format with debayering support.
        
        Unified function for both ASCOM and Alpaca cameras.
        
        Args:
            image_data: Raw image data from camera (Status object or direct data)
        Returns:
            numpy.ndarray: OpenCV-compatible image array or None if conversion fails
        """
        try:
            # Check if input is a Status object and extract data
            if hasattr(image_data, 'data'):
                # It's a Status object, extract the data
                raw_data = image_data.data
            else:
                # It's direct data
                raw_data = image_data
            
            # Check if image data is None or empty
            if raw_data is None:
                self.logger.error("Image data is None")
                return None
            
            # Convert to numpy array
            image_array = np.array(raw_data)
            
            # Check if array is empty or has invalid shape
            if image_array.size == 0:
                self.logger.error("Image array is empty")
                return None
            
            # Log the original data type and shape for debugging
            self.logger.debug(f"Image data type: {image_array.dtype}, shape: {image_array.shape}")
            
            # Ensure it's a numpy array
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)
            
            # Check if camera is color (has Bayer pattern)
            is_color_camera = False
            bayer_pattern = None
            
            # Method 1: Check sensor type from camera
            if hasattr(self.camera, 'sensor_type'):
                sensor_type = self.camera.sensor_type
                if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                    is_color_camera = True
                    bayer_pattern = sensor_type
                    self.logger.debug(f"Detected color camera with Bayer pattern: {bayer_pattern}")
            
            # Method 2: Check if auto_debayer is enabled in config
            if not is_color_camera:
                camera_config = self.config.get_camera_config()
                auto_debayer = camera_config.get('auto_debayer', False)
                if auto_debayer:
                    debayer_method = camera_config.get('debayer_method', 'RGGB')
                    if debayer_method in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                        is_color_camera = True
                        bayer_pattern = debayer_method
                        self.logger.debug(f"Color camera detected via config, Bayer pattern: {bayer_pattern}")
            
            # Method 3: Check camera name for color indicators
            if not is_color_camera and hasattr(self.camera, 'name'):
                camera_name = self.camera.name.lower()
                color_indicators = ['color', 'rgb', 'bayer', 'asi2600mc', 'asi2600mmc', 'qhy600c', 'qhy600mc']
                if any(indicator in camera_name for indicator in color_indicators):
                    is_color_camera = True
                    bayer_pattern = 'RGGB'  # Default for most color cameras
                    self.logger.debug(f"Color camera detected via name: {camera_name}, using default Bayer pattern: {bayer_pattern}")
            
            # Convert data type for processing
            if image_array.dtype != np.uint16:
                if image_array.dtype in [np.float32, np.float64]:
                    # Normalize to 0-65535 range for 16-bit
                    data_min = image_array.min()
                    data_max = image_array.max()
                    if data_max > data_min:
                        image_array = ((image_array - data_min) / (data_max - data_min) * 65535).astype(np.uint16)
                    else:
                        image_array = image_array.astype(np.uint16)
                else:
                    image_array = image_array.astype(np.uint16)
            
            # Apply debayering for color cameras FIRST (before rotation)
            if is_color_camera and bayer_pattern and len(image_array.shape) == 2:
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
                    result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            else:
                # Handle non-color or already debayered images
                if len(image_array.shape) == 2:
                    self.logger.debug("Converting monochrome image to 3-channel")
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
            
            # NOW apply orientation correction to the debayered RGB image
            # This is much simpler and more robust than rotating Bayer patterns
            original_shape = result_image.shape
            if self._needs_rotation(result_image.shape):
                result_image = np.transpose(result_image, (1, 0, 2))  # Transpose spatial dimensions
                self.logger.info(f"Image orientation corrected: {original_shape} -> {result_image.shape}")
            else:
                self.logger.debug(f"Image already in correct orientation: {original_shape}, no rotation needed")
            
            # Convert to uint8 for display (if needed)
            if result_image.dtype != np.uint8:
                if result_image.dtype == np.uint16:
                    # Apply intelligent scaling for 16-bit to 8-bit conversion
                    result_image = self._scale_16bit_to_8bit(result_image)
                else:
                    result_image = result_image.astype(np.uint8)
            
            return result_image
            
        except Exception as e:
            self.logger.error(f"Error converting image to OpenCV format: {e}")
            return None

    def _scale_16bit_to_8bit(self, image_16bit: np.ndarray) -> np.ndarray:
        """Intelligently scale 16-bit image to 8-bit for display.
        
        Uses histogram-based scaling to preserve image details and avoid
        completely black or white images.
        
        Args:
            image_16bit: 16-bit image array (uint16)
            
        Returns:
            np.ndarray: 8-bit image array (uint8)
        """
        try:
            # Calculate histogram to understand data distribution
            hist, bins = np.histogram(image_16bit.flatten(), bins=256, range=(0, 65535))
            
            # Find the 1st and 99th percentiles to avoid outliers
            cumulative_hist = np.cumsum(hist)
            total_pixels = cumulative_hist[-1]
            
            # Find 1st percentile (lower bound)
            lower_percentile = 0.01
            lower_idx = np.searchsorted(cumulative_hist, total_pixels * lower_percentile)
            lower_bound = bins[lower_idx] if lower_idx < len(bins) else 0
            
            # Find 99th percentile (upper bound)
            upper_percentile = 0.99
            upper_idx = np.searchsorted(cumulative_hist, total_pixels * upper_percentile)
            upper_bound = bins[upper_idx] if upper_idx < len(bins) else 65535
            
            # Ensure we have a reasonable range
            if upper_bound <= lower_bound:
                # Fallback to min/max if percentiles are too close
                lower_bound = image_16bit.min()
                upper_bound = image_16bit.max()
                if upper_bound <= lower_bound:
                    # If still no range, use full 16-bit range
                    lower_bound = 0
                    upper_bound = 65535
            
            # Apply contrast stretching
            range_16bit = upper_bound - lower_bound
            if range_16bit > 0:
                # Scale to 0-255 range
                image_8bit = np.clip(((image_16bit.astype(np.float32) - lower_bound) / range_16bit) * 255, 0, 255).astype(np.uint8)
            else:
                # Fallback to simple division
                image_8bit = (image_16bit / 256).astype(np.uint8)
            
            # Log scaling information for debugging
            self.logger.debug(f"16-bit to 8-bit scaling: range={lower_bound:.0f}-{upper_bound:.0f}, "
                            f"output range={image_8bit.min()}-{image_8bit.max()}")
            
            return image_8bit
            
        except Exception as e:
            self.logger.warning(f"Intelligent scaling failed: {e}, using fallback")
            # Fallback to simple division
            return (image_16bit / 256).astype(np.uint8)

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