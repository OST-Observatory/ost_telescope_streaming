#!/usr/bin/env python3
"""
Flat Capture Module for Telescope Streaming System

This module provides automatic flat field capture functionality with:
- Configurable target count rate (default: 50% of maximum)
- Configurable tolerance (default: 10%)
- Configurable number of flats (default: 40)
- Automatic exposure time adjustment
- Quality control and validation

The system automatically adjusts exposure time to achieve the target count rate
and captures the specified number of flat frames for calibration.
"""

import os
import time
import logging
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime

from status import Status, success_status, error_status, warning_status
from exceptions import FlatCaptureError
from video_capture import VideoCapture


class FlatCapture:
    """
    Automatic flat field capture system.
    
    This class manages the capture of flat field images for calibration.
    It automatically adjusts exposure time to achieve target count rates
    and validates the quality of captured flats.
    """
    
    def __init__(self, config=None, logger=None):
        """Initialize the flat capture system.
        
        Args:
            config: Configuration manager instance
            logger: Logger instance
        """
        from config_manager import ConfigManager
        
        # Only create default config if no config is provided
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
            
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        
        # Create output directories
        self._create_output_directories()
        
        # Load flat capture configuration
        flat_config = self.config.get_flat_config()
        self.target_count_rate = flat_config.get('target_count_rate', 0.5)  # 50% of max
        self.count_tolerance = flat_config.get('count_tolerance', 0.1)  # 10%
        self.num_flats = flat_config.get('num_flats', 40)
        self.min_exposure = flat_config.get('min_exposure', 0.001)  # 1ms
        self.max_exposure = flat_config.get('max_exposure', 10.0)  # 10s
        self.exposure_step_factor = flat_config.get('exposure_step_factor', 1.5)
        self.max_adjustment_attempts = flat_config.get('max_adjustment_attempts', 10)
        self.flat_output_dir = flat_config.get('output_dir', 'flats')
        
        # Ensure output directory exists
        os.makedirs(self.flat_output_dir, exist_ok=True)
        
        self.video_capture = None
        self.current_exposure = None
        self.is_running = False
        
    def _create_output_directories(self):
        """Create necessary output directories."""
        try:
            # Create flat frames directory
            flat_config = self.config.get_flat_config()
            output_dir = Path(flat_config.get('output_directory', 'flat_frames'))
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Flat frames directory ready: {output_dir}")
                
        except Exception as e:
            self.logger.warning(f"Failed to create flat output directories: {e}")
    
    def initialize(self, video_capture: VideoCapture) -> bool:
        """Initialize the flat capture system with video capture.
        
        Args:
            video_capture: Video capture instance
            
        Returns:
            bool: True if initialization successful
        """
        try:
            self.video_capture = video_capture
            
            # Get current exposure time as starting point from config
            camera_config = self.config.get_camera_config()
            if video_capture.camera_type == 'ascom':
                ascom_config = camera_config.get('ascom', {})
                self.current_exposure = ascom_config.get('exposure_time', self.min_exposure)
            elif video_capture.camera_type == 'alpaca':
                alpaca_config = camera_config.get('alpaca', {})
                self.current_exposure = alpaca_config.get('exposure_time', self.min_exposure)
            else:
                self.current_exposure = self.min_exposure
            
            self.logger.info(f"Starting exposure time: {self.current_exposure}s")
            
            self.logger.info(f"Flat capture initialized with target count rate: {self.target_count_rate:.1%}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize flat capture: {e}")
            return False
    
    def capture_flats(self) -> Status:
        """Capture a series of flat field images.
        
        This method automatically adjusts exposure time to achieve the target
        count rate and captures the specified number of flat frames.
        
        Returns:
            Status: Success or error status with details
        """
        try:
            if not self.video_capture:
                return error_status("Video capture not initialized")
            
            self.logger.info(f"Starting flat capture: {self.num_flats} frames, target count rate: {self.target_count_rate:.1%}")
            
            # Step 1: Adjust exposure time to achieve target count rate
            adjustment_status = self._adjust_exposure_for_target()
            if not adjustment_status.is_success:
                return adjustment_status
            
            # Step 2: Capture the flat frames
            capture_status = self._capture_flat_series()
            if not capture_status.is_success:
                return capture_status
            
            self.logger.info("Flat capture completed successfully")
            return success_status(
                "Flat capture completed successfully",
                data=capture_status.data,
                details={
                    'num_flats': self.num_flats,
                    'target_count_rate': self.target_count_rate,
                    'final_exposure': self.current_exposure,
                    'output_directory': self.flat_output_dir
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error during flat capture: {e}")
            return error_status(f"Flat capture failed: {e}")
    
    def _adjust_exposure_for_target(self) -> Status:
        """Adjust exposure time to achieve target count rate.
        
        Returns:
            Status: Success or error status
        """
        try:
            self.logger.info("Adjusting exposure time for target count rate...")
            
            for attempt in range(self.max_adjustment_attempts):
                # Capture a test frame
                test_status = self._capture_test_frame()
                if not test_status.is_success:
                    return test_status
                
                # Analyze the frame
                analysis = test_status.data
                current_count_rate = analysis['mean_count_rate']
                target_count = self.target_count_rate * analysis['max_possible_count']
                
                self.logger.info(f"Attempt {attempt + 1}: Exposure={self.current_exposure:.3f}s, "
                               f"Count rate={current_count_rate:.1%}, Target={self.target_count_rate:.1%}")
                
                # Check if we're within tolerance
                if self._is_within_tolerance(current_count_rate, self.target_count_rate):
                    self.logger.info(f"Target count rate achieved: {current_count_rate:.1%}")
                    return success_status("Exposure time adjusted successfully")
                
                # Adjust exposure time
                if current_count_rate < self.target_count_rate:
                    # Too dark, increase exposure
                    new_exposure = self.current_exposure * self.exposure_step_factor
                    if new_exposure > self.max_exposure:
                        self.logger.warning(f"Exposure would exceed maximum ({self.max_exposure}s)")
                        break
                else:
                    # Too bright, decrease exposure
                    new_exposure = self.current_exposure / self.exposure_step_factor
                    if new_exposure < self.min_exposure:
                        self.logger.warning(f"Exposure would be below minimum ({self.min_exposure}s)")
                        break
                
                self.current_exposure = new_exposure
                
                # Note: Exposure time will be set in the next capture call
                # No need to set it separately as it's passed to capture methods
                self.logger.debug(f"Updated exposure time to {self.current_exposure:.6f}s")
                time.sleep(0.1)  # Allow camera to adjust
            
            return warning_status(f"Could not achieve target count rate after {self.max_adjustment_attempts} attempts")
            
        except Exception as e:
            self.logger.error(f"Error adjusting exposure: {e}")
            return error_status(f"Exposure adjustment failed: {e}")
    
    def _capture_test_frame(self) -> Status:
        """Capture a single test frame for exposure adjustment.
        
        Returns:
            Status: Success status with frame analysis data
        """
        try:
            if not self.video_capture:
                return error_status("Video capture not available")
            
            # Capture frame with current exposure time
            if hasattr(self.video_capture, 'capture_single_frame_ascom') and self.video_capture.camera_type == 'ascom':
                # Get camera config for other parameters
                camera_config = self.config.get_camera_config()
                ascom_config = camera_config.get('ascom', {})
                gain = ascom_config.get('gain', None)
                binning = ascom_config.get('binning', 1)
                
                frame_status = self.video_capture.capture_single_frame_ascom(
                    self.current_exposure, gain, binning
                )
            elif hasattr(self.video_capture, 'capture_single_frame_alpaca') and self.video_capture.camera_type == 'alpaca':
                # Get camera config for other parameters
                camera_config = self.config.get_camera_config()
                alpaca_config = camera_config.get('alpaca', {})
                gain = alpaca_config.get('gain', None)
                binning = alpaca_config.get('binning', [1, 1])
                
                frame_status = self.video_capture.capture_single_frame_alpaca(
                    self.current_exposure, gain, binning
                )
            elif hasattr(self.video_capture, 'capture_single_frame'):
                frame_status = self.video_capture.capture_single_frame()
            else:
                return error_status("Video capture does not support single frame capture")
            
            if not frame_status.is_success:
                return error_status(f"Failed to capture test frame: {frame_status.message}")
            
            # Get frame data and convert to numpy array
            frame_data = frame_status.data
            
            # Handle different frame data types
            if isinstance(frame_data, str):
                # Frame was saved to file, load it
                import cv2
                frame = cv2.imread(frame_data, cv2.IMREAD_GRAYSCALE)
            elif isinstance(frame_data, list):
                # Convert list to numpy array
                frame = np.array(frame_data, dtype=np.float32)
                self.logger.debug(f"Converted list to numpy array: shape={frame.shape}, dtype={frame.dtype}")
            elif isinstance(frame_data, np.ndarray):
                # Already a numpy array
                frame = frame_data
            else:
                # Try to convert to numpy array
                try:
                    frame = np.array(frame_data, dtype=np.float32)
                    self.logger.debug(f"Converted {type(frame_data)} to numpy array: shape={frame.shape}")
                except Exception as e:
                    self.logger.error(f"Cannot convert frame data to numpy array: {e}")
                    return error_status(f"Cannot convert frame data to numpy array: {e}")
            
            # Analyze frame
            analysis = self._analyze_frame(frame)
            return success_status("Test frame captured", data=analysis)
                
        except Exception as e:
            self.logger.error(f"Error capturing test frame: {e}")
            return error_status(f"Test frame capture failed: {e}")
    
    def _analyze_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Analyze a frame to determine count rate and statistics.
        
        Args:
            frame: Frame data as numpy array
            
        Returns:
            Dict containing frame analysis
        """
        try:
            # Ensure frame is a numpy array
            if not isinstance(frame, np.ndarray):
                self.logger.error(f"Frame is not a numpy array: {type(frame)}")
                return {
                    'mean_value': 0,
                    'std_value': 0,
                    'min_value': 0,
                    'max_value': 0,
                    'max_possible_count': 255,
                    'mean_count_rate': 0,
                    'frame_shape': (0, 0),
                    'dtype': 'unknown',
                    'error': f"Invalid frame type: {type(frame)}"
                }
            
            # Convert to float for analysis
            frame_float = frame.astype(np.float32)
            
            # Calculate statistics
            mean_value = np.mean(frame_float)
            std_value = np.std(frame_float)
            min_value = np.min(frame_float)
            max_value = np.max(frame_float)
            
            # Determine bit depth and max possible count
            if frame.dtype == np.uint8:
                max_possible_count = 255
            elif frame.dtype == np.uint16:
                max_possible_count = 65535
            else:
                max_possible_count = 255  # Default assumption
            
            # Calculate count rate as percentage of maximum
            count_rate = mean_value / max_possible_count
            
            return {
                'mean_value': mean_value,
                'std_value': std_value,
                'min_value': min_value,
                'max_value': max_value,
                'max_possible_count': max_possible_count,
                'mean_count_rate': count_rate,
                'frame_shape': frame.shape,
                'dtype': str(frame.dtype)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing frame: {e}")
            return {
                'mean_value': 0,
                'std_value': 0,
                'min_value': 0,
                'max_value': 0,
                'max_possible_count': 255,
                'mean_count_rate': 0,
                'frame_shape': (0, 0),
                'dtype': 'unknown',
                'error': str(e)
            }
    
    def _is_within_tolerance(self, current: float, target: float) -> bool:
        """Check if current value is within tolerance of target.
        
        Args:
            current: Current value
            target: Target value
            
        Returns:
            bool: True if within tolerance
        """
        tolerance_range = target * self.count_tolerance
        return abs(current - target) <= tolerance_range
    
    def _capture_flat_series(self) -> Status:
        """Capture the series of flat field images.
        
        Returns:
            Status: Success status with list of captured files
        """
        try:
            self.logger.info(f"Capturing {self.num_flats} flat frames...")
            
            captured_files = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Get camera config for other parameters
            camera_config = self.config.get_camera_config()
            if self.video_capture.camera_type == 'ascom':
                ascom_config = camera_config.get('ascom', {})
                gain = ascom_config.get('gain', None)
                binning = ascom_config.get('binning', 1)
            elif self.video_capture.camera_type == 'alpaca':
                alpaca_config = camera_config.get('alpaca', {})
                gain = alpaca_config.get('gain', None)
                binning = alpaca_config.get('binning', [1, 1])
            else:
                gain = None
                binning = 1
            
            for i in range(self.num_flats):
                # Generate filename
                filename = f"flat_{timestamp}_{i+1:03d}.fits"
                filepath = os.path.join(self.flat_output_dir, filename)
                
                # Capture frame with current exposure time
                if hasattr(self.video_capture, 'capture_single_frame_ascom') and self.video_capture.camera_type == 'ascom':
                    frame_status = self.video_capture.capture_single_frame_ascom(
                        self.current_exposure, gain, binning
                    )
                elif hasattr(self.video_capture, 'capture_single_frame_alpaca') and self.video_capture.camera_type == 'alpaca':
                    frame_status = self.video_capture.capture_single_frame_alpaca(
                        self.current_exposure, gain, binning
                    )
                elif hasattr(self.video_capture, 'capture_single_frame'):
                    frame_status = self.video_capture.capture_single_frame()
                else:
                    self.logger.warning(f"Failed to capture flat {i+1}: No capture method available")
                    continue
                
                if frame_status.is_success:
                    # Save the frame
                    save_status = self.video_capture.save_frame(frame_status.data, filepath)
                    if save_status.is_success:
                        captured_files.append(filepath)
                        self.logger.debug(f"Captured flat {i+1}/{self.num_flats}: {filename}")
                    else:
                        self.logger.warning(f"Failed to save flat {i+1}: {save_status.message}")
                else:
                    self.logger.warning(f"Failed to capture flat {i+1}: {frame_status.message}")
                
                # Small delay between captures
                time.sleep(0.1)
            
            self.logger.info(f"Flat series capture completed: {len(captured_files)}/{self.num_flats} frames")
            
            return success_status(
                f"Flat series captured: {len(captured_files)} frames",
                data=captured_files,
                details={
                    'captured_count': len(captured_files),
                    'target_count': self.num_flats,
                    'output_directory': self.flat_output_dir
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error capturing flat series: {e}")
            return error_status(f"Flat series capture failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the flat capture system.
        
        Returns:
            Dict containing system status
        """
        return {
            'initialized': self.video_capture is not None,
            'current_exposure': self.current_exposure,
            'target_count_rate': self.target_count_rate,
            'count_tolerance': self.count_tolerance,
            'num_flats': self.num_flats,
            'output_directory': self.flat_output_dir,
            'is_running': self.is_running
        } 