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
from config_manager import config

class VideoCapture:
    """Video capture class for telescope streaming."""
    
    def __init__(self):
        """Initialize video capture system."""
        self.cap = None
        self.is_capturing = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Load configuration
        self.video_config = config.get_video_config()
        self.camera_config = config.get_camera_config()
        self.telescope_config = config.get_telescope_config()
        
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
        
    def _calculate_field_of_view(self) -> Tuple[float, float]:
        """Calculate field of view in degrees based on telescope and camera parameters."""
        # Convert sensor dimensions to degrees
        # FOV = 2 * arctan(sensor_size / (2 * focal_length))
        fov_width_rad = 2 * np.arctan(self.sensor_width / (2 * self.focal_length))
        fov_height_rad = 2 * np.arctan(self.sensor_height / (2 * self.focal_length))
        
        # Convert to degrees
        fov_width_deg = np.degrees(fov_width_rad)
        fov_height_deg = np.degrees(fov_height_rad)
        
        self.logger.info(f"Calculated FOV: {fov_width_deg:.3f}° x {fov_height_deg:.3f}°")
        return fov_width_deg, fov_height_deg
    
    def get_field_of_view(self) -> Tuple[float, float]:
        """Get current field of view in degrees."""
        return self.fov_width, self.fov_height
    
    def get_sampling_arcsec_per_pixel(self) -> float:
        """Calculate sampling in arcseconds per pixel."""
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
    
    def start_capture(self):
        """Start continuous frame capture in background thread."""
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return False
        
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.logger.info("Video capture started")
        return True
    
    def stop_capture(self):
        """Stop continuous frame capture."""
        self.is_capturing = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=2.0)
        self.logger.info("Video capture stopped")
    
    def _capture_loop(self):
        """Background thread for continuous frame capture."""
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
        """Get the most recent captured frame."""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def capture_single_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame."""
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return None
        
        ret, frame = self.cap.read()
        if ret:
            return frame
        else:
            self.logger.error("Failed to capture single frame")
            return None
    
    def save_frame(self, frame: np.ndarray, filename: str) -> bool:
        """Save frame to file."""
        try:
            output_path = Path(filename)
            success = cv2.imwrite(str(output_path), frame)
            if success:
                self.logger.info(f"Frame saved: {output_path.absolute()}")
            else:
                self.logger.error(f"Failed to save frame: {output_path}")
            return success
        except Exception as e:
            self.logger.error(f"Error saving frame: {e}")
            return False
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information and settings."""
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

def main():
    """Test function for video capture module."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test video capture module")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--capture", action="store_true", help="Capture single frame")
    parser.add_argument("--stream", action="store_true", help="Start continuous capture")
    parser.add_argument("--info", action="store_true", help="Show camera info")
    parser.add_argument("--output", default="test_frame.jpg", help="Output filename")
    
    args = parser.parse_args()
    
    # Update camera index in config for testing
    config.update_video_config({"camera_index": args.camera})
    
    video_capture = VideoCapture()
    
    if args.info:
        info = video_capture.get_camera_info()
        print("Camera Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    
    if args.capture:
        if video_capture.connect():
            frame = video_capture.capture_single_frame()
            if frame is not None:
                video_capture.save_frame(frame, args.output)
            video_capture.disconnect()
    
    if args.stream:
        if video_capture.start_capture():
            try:
                print("Press Ctrl+C to stop streaming...")
                while True:
                    frame = video_capture.get_current_frame()
                    if frame is not None:
                        print(f"Frame captured: {frame.shape}")
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping stream...")
            finally:
                video_capture.stop_capture()
                video_capture.disconnect()

if __name__ == "__main__":
    main() 