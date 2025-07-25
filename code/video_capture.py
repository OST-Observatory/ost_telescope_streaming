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

# Import configuration
from config_manager import ConfigManager
from exceptions import CameraError, FileError
from status import CameraStatus, success_status, error_status, warning_status
from ascom_camera import ASCOMCamera

class VideoCapture:
    """Video capture class for telescope streaming."""
    
    def __init__(self, config=None, logger=None):
        """Initialises the video capture system."""
        self.cap = None
        self.is_capturing = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Load configuration
        default_config = ConfigManager()
        self.config = config or default_config
        
        # Use provided logger or get logger with proper name
        if logger:
            self.logger = logger
        else:
            # Get logger with module name for better identification
            self.logger = logging.getLogger(__name__)
            # Ensure logger has proper level if root logger is configured
            if logging.getLogger().handlers:
                self.logger.setLevel(logging.getLogger().level)
        
        self.video_config = self.config.get_video_config()
        self.camera_config = self.config.get_camera_config()
        self.telescope_config = self.config.get_telescope_config()
        self.camera_type = self.video_config.get('camera_type', 'opencv')
        if self.camera_type == 'opencv':
            cam_cfg = self.video_config.get('opencv', {})
            self.camera_index = cam_cfg.get('camera_index', 0)
            self.frame_width = cam_cfg.get('frame_width', 1920)
            self.frame_height = cam_cfg.get('frame_height', 1080)
            self.fps = cam_cfg.get('fps', 30)
            self.auto_exposure = cam_cfg.get('auto_exposure', True)
            self.exposure_time = cam_cfg.get('exposure_time', 0.1)
            self.gain = cam_cfg.get('gain', 1.0)
        elif self.camera_type == 'ascom':
            cam_cfg = self.video_config.get('ascom', {})
            self.ascom_driver = cam_cfg.get('ascom_driver', None)
            self.exposure_time = cam_cfg.get('exposure_time', 0.1)
            self.gain = cam_cfg.get('gain', 1.0)
        # Remove any remaining German comments and ensure all are in English
        
        # Telescope parameters for FOV calculation
        self.focal_length = self.telescope_config.get('focal_length', 1000)  # mm
        self.aperture = self.telescope_config.get('aperture', 200)  # mm
        self.sensor_width = self.camera_config.get('sensor_width', 6.17)  # mm
        self.sensor_height = self.camera_config.get('sensor_height', 4.55)  # mm
        
        # Calculate field of view
        self.fov_width, self.fov_height = self._calculate_field_of_view()
        
        # Video capture settings
        self.capture_enabled = self.config.get_plate_solve_config().get('auto_solve', False)
        self.capture_interval = self.config.get_plate_solve_config().get('min_solve_interval', 60)  # seconds
        
        # Logger is already set up above
        
        self.ascom_camera = None
        
    def _calculate_field_of_view(self) -> tuple[float, float]:
        """Calculates the field of view (FOV) in degrees based on telescope and camera parameters.
        Returns:
            tuple: (FOV width in degrees, FOV height in degrees)
        """
        # Convert sensor dimensions to degrees
        # FOV = 2 * arctan(sensor_size / (2 * focal_length))
        fov_width_rad = 2 * np.arctan(self.sensor_width / (2 * self.focal_length))
        fov_height_rad = 2 * np.arctan(self.sensor_height / (2 * self.focal_length))
        
        # Convert to degrees
        fov_width_deg = np.degrees(fov_width_rad)
        fov_height_deg = np.degrees(fov_height_rad)
        
        self.logger.info(f"Calculated FOV: {fov_width_deg:.3f}° x {fov_height_deg:.3f}°")
        return fov_width_deg, fov_height_deg
    
    def get_field_of_view(self) -> tuple[float, float]:
        """Returns the current field of view (FOV) in degrees."""
        return self.fov_width, self.fov_height
    
    def get_sampling_arcsec_per_pixel(self) -> float:
        """Calculates the sampling in arcseconds per pixel."""
        # arcsec/pixel = (206265 * pixel_size) / focal_length
        # pixel_size = sensor_size / pixel_count
        pixel_size_width = self.sensor_width / self.frame_width
        pixel_size_height = self.sensor_height / self.frame_height
        
        # Use average pixel size
        avg_pixel_size = (pixel_size_width + pixel_size_height) / 2
        
        sampling = (206265 * avg_pixel_size) / self.focal_length
        return sampling
    
    def connect(self) -> CameraStatus:
        """Connects to the video camera."""
        if self.camera_type == 'ascom' and self.ascom_driver:
            cam = ASCOMCamera(driver_id=self.ascom_driver, config=self.config, logger=self.logger)
            status = cam.connect()
            if status.is_success:
                self.ascom_camera = cam
                self.logger.info("ASCOM camera connected")
                return success_status("ASCOM camera connected", details={'driver': self.ascom_driver})
            else:
                self.ascom_camera = None
                self.logger.error(f"ASCOM camera connection failed: {status.message}")
                return error_status(f"ASCOM camera connection failed: {status.message}", details={'driver': self.ascom_driver})
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.logger.error(f"Failed to open camera {self.camera_index}")
                return error_status(f"Failed to open camera {self.camera_index}", details={'camera_index': self.camera_index})
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            if not self.auto_exposure:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure
                # Convert seconds to OpenCV exposure units (typically microseconds)
                exposure_cv = int(self.exposure_time * 1000000)  # Convert seconds to microseconds
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_cv)
            
            # Set gain if supported
            if hasattr(cv2, 'CAP_PROP_GAIN'):
                self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
            
            # Verify settings
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.logger.info(f"Camera connected: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")
            self.logger.info(f"FOV: {self.fov_width:.3f}° x {self.fov_height:.3f}°")
            self.logger.info(f"Sampling: {self.get_sampling_arcsec_per_pixel():.2f} arcsec/pixel")
            
            return success_status("Camera connected", details={'camera_index': self.camera_index, 'resolution': f'{actual_width}x{actual_height}', 'fps': actual_fps})
            
        except Exception as e:
            self.logger.error(f"Error connecting to camera: {e}")
            return error_status(f"Error connecting to camera: {e}", details={'camera_index': self.camera_index})
    
    def disconnect(self):
        """Disconnects from the video camera."""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_capturing = False
        self.logger.info("Camera disconnected")
    
    def start_capture(self) -> CameraStatus:
        """Starts continuous frame capture in the background thread.
        Returns:
            CameraStatus: Status object with start information or error.
        """
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.logger.info("Video capture started")
        return success_status("Video capture started", details={'camera_index': self.camera_index, 'is_capturing': True})
    
    def stop_capture(self) -> CameraStatus:
        """Stops continuous frame capture.
        Returns:
            CameraStatus: Status object with stop information or error.
        """
        self.is_capturing = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=2.0)
        self.logger.info("Video capture stopped")
        return success_status("Video capture stopped", details={'camera_index': self.camera_index, 'is_capturing': False})
    
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
                    if self.ascom_camera:
                        # Get settings from config
                        ascom_config = self.video_config.get('ascom', {})
                        exposure_time = ascom_config.get('exposure_time', 1.0)
                        gain = ascom_config.get('gain', None)
                        binning = ascom_config.get('binning', 1)
                        
                        # Capture frame with ASCOM camera
                        status = self.ascom_camera.expose(exposure_time, gain, binning)
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
        if self.camera_type == 'ascom' and self.ascom_camera:
            # Use exposure time in seconds
            exposure_time = self.camera_config.get('exposure_time', 1.0)  # seconds
            gain = self.camera_config.get('gain', None)
            binning = self.camera_config.get('binning', 1)
            exp_status = self.ascom_camera.expose(exposure_time, gain, binning)
            if not exp_status.is_success:
                return exp_status
            img_status = self.ascom_camera.get_image()
            return img_status
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
        ret, frame = self.cap.read()
        if ret:
            return success_status("Frame captured", data=frame, details={'camera_index': self.camera_index})
        else:
            self.logger.error("Failed to capture single frame")
            return error_status("Failed to capture single frame", details={'camera_index': self.camera_index})
    
    def capture_single_frame_ascom(self, exposure_time_s: float, gain: Optional[float] = None, binning: int = 1) -> CameraStatus:
        """Captures a single frame with ASCOM camera.
        Args:
            exposure_time_s: Exposure time in seconds
            gain: Gain value (optional)
            binning: Binning factor (default: 1)
        Returns:
            CameraStatus: Status object with frame or error.
        """
        if not self.ascom_camera:
            return error_status("ASCOM camera not connected")
        
        try:
            # Get sensor dimensions from ASCOM camera
            try:
                # Get native sensor dimensions
                native_width = self.ascom_camera.camera.CameraXSize
                native_height = self.ascom_camera.camera.CameraYSize
                
                # Calculate effective dimensions with binning
                effective_width = native_width // binning
                effective_height = native_height // binning
                
                self.logger.info(f"Native sensor: {native_width}x{native_height}, Binning: {binning}x{binning}, Effective: {effective_width}x{effective_height}")
                
                # Set the subframe to use the full sensor with binning
                self.ascom_camera.camera.NumX = effective_width
                self.ascom_camera.camera.NumY = effective_height
                self.ascom_camera.camera.StartX = 0
                self.ascom_camera.camera.StartY = 0
                
            except Exception as e:
                self.logger.warning(f"Could not get sensor dimensions from ASCOM camera: {e}")
                self.logger.info("Using default dimensions - this may cause issues with some cameras")
            
            # Start exposure
            exp_status = self.ascom_camera.expose(exposure_time_s, gain, binning)
            if not exp_status.is_success:
                return exp_status
            
            # Get image
            img_status = self.ascom_camera.get_image()
            if not img_status.is_success:
                return img_status
            
            # Check if debayering is needed
            if self.ascom_camera.is_color_camera():
                debayer_status = self.ascom_camera.debayer(img_status.data)
                if debayer_status.is_success:
                    return success_status("Color frame captured and debayered", 
                                        data=debayer_status.data, 
                                        details={'exposure_time_s': exposure_time_s, 'gain': gain, 'binning': binning, 'dimensions': f"{effective_width}x{effective_height}"})
                else:
                    self.logger.warning(f"Debayering failed: {debayer_status.message}, returning raw image")
                    return success_status("Color frame captured (raw)", 
                                        data=img_status.data, 
                                        details={'exposure_time_s': exposure_time_s, 'gain': gain, 'binning': binning, 'dimensions': f"{effective_width}x{effective_height}"})
            else:
                return success_status("Mono frame captured", 
                                    data=img_status.data, 
                                    details={'exposure_time_s': exposure_time_s, 'gain': gain, 'binning': binning, 'dimensions': f"{effective_width}x{effective_height}"})
                
        except Exception as e:
            self.logger.error(f"Error capturing ASCOM frame: {e}")
            return error_status(f"Error capturing ASCOM frame: {e}")
    
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
            
            # Convert frame to proper OpenCV format if needed
            if self.camera_type == 'ascom' and self.ascom_camera:
                # Convert ASCOM image data to OpenCV format
                frame = self._convert_ascom_to_opencv(frame)
                if frame is None:
                    return error_status("Failed to convert ASCOM image to OpenCV format")
            
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
    
    def get_camera_info(self) -> dict[str, Any]:
        """Returns camera information and settings."""
        if not self.cap or not self.cap.isOpened():
            return {"error": "Camera not connected"}
        
        info = {
            "camera_index": self.camera_index,
            "frame_width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "frame_height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self.cap.get(cv2.CAP_PROP_FPS),
            "fov_width": self.fov_width,
            "fov_height": self.fov_height,
            "sampling_arcsec_per_pixel": self.get_sampling_arcsec_per_pixel(),
            "is_capturing": self.is_capturing,
            "capture_enabled": self.capture_enabled
        }
        
        return info 

    def _convert_ascom_to_opencv(self, ascom_image_data):
        """Convert ASCOM image data to OpenCV format with debayering.
        Args:
            ascom_image_data: Raw image data from ASCOM camera
        Returns:
            numpy.ndarray: OpenCV-compatible image array or None if conversion fails
        """
        try:
            # Convert ASCOM image array to numpy array
            image_array = np.array(ascom_image_data)
            
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
            if hasattr(self.ascom_camera, 'sensor_type'):
                sensor_type = self.ascom_camera.sensor_type
                if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                    # Apply debayering based on Bayer pattern
                    if sensor_type == 'RGGB':
                        bayer_pattern = cv2.COLOR_BayerRG2BGR
                    elif sensor_type == 'GRBG':
                        bayer_pattern = cv2.COLOR_BayerGR2BGR
                    elif sensor_type == 'GBRG':
                        bayer_pattern = cv2.COLOR_BayerGB2BGR
                    elif sensor_type == 'BGGR':
                        bayer_pattern = cv2.COLOR_BayerBG2BGR
                    
                    # Apply debayering
                    color_image = cv2.cvtColor(image_array, bayer_pattern)
                    return color_image
            
            # For monochrome cameras, convert to 3-channel grayscale
            if len(image_array.shape) == 2:
                return cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            
            # If already 3-channel, return as is
            if len(image_array.shape) == 3:
                return image_array
            
            # Fallback: assume monochrome and convert
            return cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            
        except Exception as e:
            self.logger.error(f"Error converting ASCOM image: {e}")
            return None 