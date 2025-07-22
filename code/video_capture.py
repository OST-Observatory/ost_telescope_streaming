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
from config_manager import config as default_config
from exceptions import CameraError, FileError
from status import CameraStatus, success_status, error_status, warning_status

class VideoCapture:
    """Video capture class for telescope streaming."""
    
    def __init__(self, config=None, logger=None):
        """Initialisiert das Video-Capture-System."""
        self.cap = None
        self.is_capturing = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Load configuration
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        self.video_config = self.config.get_video_config()
        self.camera_config = self.config.get_camera_config()
        self.telescope_config = self.config.get_telescope_config()
        
        # Camera settings
        self.camera_index = self.video_config.get('camera_index', 0)
        self.frame_width = self.video_config.get('frame_width', 1920)
        self.frame_height = self.video_config.get('frame_height', 1080)
        self.fps = self.video_config.get('fps', 30)
        self.auto_exposure = self.video_config.get('auto_exposure', True)
        self.exposure_time = self.video_config.get('exposure_time', 100)
        self.gain = self.video_config.get('gain', 1.0)
        
        # Telescope parameters for FOV calculation
        self.focal_length = self.telescope_config.get('focal_length', 1000)  # mm
        self.aperture = self.telescope_config.get('aperture', 200)  # mm
        self.sensor_width = self.camera_config.get('sensor_width', 6.17)  # mm
        self.sensor_height = self.camera_config.get('sensor_height', 4.55)  # mm
        
        # Calculate field of view
        self.fov_width, self.fov_height = self._calculate_field_of_view()
        
        # Video capture settings
        self.capture_enabled = self.video_config.get('plate_solving_enabled', False)
        self.capture_interval = self.video_config.get('plate_solving_interval', 60)  # seconds
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
    def _calculate_field_of_view(self) -> tuple[float, float]:
        """Berechnet das Sichtfeld (FOV) in Grad basierend auf Teleskop- und Kameraparametern.
        Returns:
            tuple: (FOV-Breite in Grad, FOV-Höhe in Grad)
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
        """Gibt das aktuelle Sichtfeld (FOV) in Grad zurück."""
        return self.fov_width, self.fov_height
    
    def get_sampling_arcsec_per_pixel(self) -> float:
        """Berechnet das Sampling in Bogensekunden pro Pixel."""
        # arcsec/pixel = (206265 * pixel_size) / focal_length
        # pixel_size = sensor_size / pixel_count
        pixel_size_width = self.sensor_width / self.frame_width
        pixel_size_height = self.sensor_height / self.frame_height
        
        # Use average pixel size
        avg_pixel_size = (pixel_size_width + pixel_size_height) / 2
        
        sampling = (206265 * avg_pixel_size) / self.focal_length
        return sampling
    
    def connect(self) -> bool:
        """Connect to video camera."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.logger.error(f"Failed to open camera {self.camera_index}")
                return False
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            if not self.auto_exposure:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure
                self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure_time)
            
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
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to camera: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from video camera."""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_capturing = False
        self.logger.info("Camera disconnected")
    
    def start_capture(self) -> CameraStatus:
        """Startet die kontinuierliche Frame-Aufnahme im Hintergrund-Thread.
        Returns:
            CameraStatus: Status-Objekt mit Startinformation oder Fehler.
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
        """Stoppt die kontinuierliche Frame-Aufnahme.
        Returns:
            CameraStatus: Status-Objekt mit Stopinformation oder Fehler.
        """
        self.is_capturing = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=2.0)
        self.logger.info("Video capture stopped")
        return success_status("Video capture stopped", details={'camera_index': self.camera_index, 'is_capturing': False})
    
    def _capture_loop(self) -> None:
        """Hintergrund-Thread für kontinuierliche Frame-Aufnahme."""
        while self.is_capturing and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame.copy()
                    
                    # Frame captured successfully
                    pass
                        
                else:
                    self.logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Gibt das zuletzt aufgenommene Frame zurück."""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def capture_single_frame(self) -> CameraStatus:
        """Nimmt ein einzelnes Frame auf und gibt Status zurück.
        Returns:
            CameraStatus: Status-Objekt mit Frame oder Fehler.
        """
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return error_status("Failed to connect to camera", details={'camera_index': self.camera_index})
        ret, frame = self.cap.read()
        if ret:
            return success_status("Frame captured", data=frame, details={'camera_index': self.camera_index})
        else:
            self.logger.error("Failed to capture single frame")
            return error_status("Failed to capture single frame", details={'camera_index': self.camera_index})
    
    def save_frame(self, frame: Any, filename: str) -> CameraStatus:
        """Speichert ein Frame als Datei.
        Args:
            frame: Das zu speichernde Bild (np.ndarray)
            filename: Dateiname
        Returns:
            CameraStatus: Status-Objekt mit Dateipfad oder Fehler.
        """
        try:
            output_path = Path(filename)
            success = cv2.imwrite(str(output_path), frame)
            if success:
                self.logger.info(f"Frame saved: {output_path.absolute()}")
                return success_status("Frame saved", data=str(output_path.absolute()), details={'camera_index': self.camera_index})
            else:
                self.logger.error(f"Failed to save frame: {output_path}")
                return error_status("Failed to save frame", details={'camera_index': self.camera_index})
        except Exception as e:
            self.logger.error(f"Error saving frame: {e}")
            return error_status(f"Error saving frame: {e}", details={'camera_index': self.camera_index})
    
    def get_camera_info(self) -> dict[str, Any]:
        """Gibt Kamera-Informationen und Einstellungen zurück."""
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