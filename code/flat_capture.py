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
        # Resolve output directory (support both new and legacy key)
        self.flat_output_dir = (
            flat_config.get('output_dir')
            or flat_config.get('output_directory')
            or 'flats'
        )
        
        # Ensure output directory exists
        os.makedirs(self.flat_output_dir, exist_ok=True)
        
        self.video_capture = None
        self.current_exposure = None
        self.is_running = False
        
    def _create_output_directories(self):
        """Create necessary output directories."""
        try:
            # Create flat frames directory (use resolved path)
            output_dir = Path(self.flat_output_dir)
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
            default_exposure = 2.0  # Start with 2s for efficiency
            
            if video_capture.camera_type == 'ascom':
                ascom_config = camera_config.get('ascom', {})
                self.current_exposure = ascom_config.get('exposure_time', default_exposure)
            elif video_capture.camera_type == 'alpaca':
                alpaca_config = camera_config.get('alpaca', {})
                self.current_exposure = alpaca_config.get('exposure_time', default_exposure)
            else:
                self.current_exposure = default_exposure
            
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
            
            # Ensure current_exposure is set
            if self.current_exposure is None:
                self.logger.warning("Current exposure not set, using default")
                self.current_exposure = 2.0  # Default 2 second exposure
            
            self.logger.info(f"Starting flat capture: {self.num_flats} frames, target count rate: {self.target_count_rate:.1%}")
            self.logger.info(f"Initial exposure time: {self.current_exposure:.3f}s")
            
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
        """Intelligent exposure adjustment to achieve target count rate.
        
        Uses adaptive step sizes and oscillation prevention for better convergence.
        
        Returns:
            Status: Success or error status
        """
        try:
            self.logger.info("Starting intelligent exposure adjustment...")
            
            # Track previous values to detect oscillations
            previous_exposures = []
            previous_count_rates = []
            oscillation_detected = False
            
            for attempt in range(self.max_adjustment_attempts):
                # Capture a test frame
                test_status = self._capture_test_frame()
                if not test_status.is_success:
                    return test_status
                
                # Analyze the frame
                analysis = test_status.data
                current_count_rate = analysis['mean_count_rate']
                
                # Store history for oscillation detection
                previous_exposures.append(self.current_exposure)
                previous_count_rates.append(current_count_rate)
                
                # Keep only last 4 values for oscillation detection
                if len(previous_exposures) > 4:
                    previous_exposures.pop(0)
                    previous_count_rates.pop(0)
                
                self.logger.info(f"Attempt {attempt + 1}: Exposure={self.current_exposure:.3f}s, "
                               f"Count rate={current_count_rate:.1%}, Target={self.target_count_rate:.1%}")
                
                # Check if we're within tolerance
                if self._is_within_tolerance(current_count_rate, self.target_count_rate):
                    self.logger.info(f"✅ Target count rate achieved: {current_count_rate:.1%}")
                    return success_status("Exposure time adjusted successfully")
                
                # Calculate distance from target (as percentage)
                distance_from_target = abs(current_count_rate - self.target_count_rate)
                relative_distance = distance_from_target / self.target_count_rate
                
                # Detect oscillations (if we have enough history)
                if len(previous_count_rates) >= 4:
                    oscillation_detected = self._detect_oscillation(previous_count_rates, previous_exposures)
                    if oscillation_detected:
                        self.logger.warning("🔄 Oscillation detected! Using conservative adjustment...")
                
                # Calculate adaptive step size
                step_factor = self._calculate_adaptive_step(relative_distance, oscillation_detected, attempt)
                
                # Determine adjustment direction and magnitude
                if current_count_rate < self.target_count_rate:
                    # Too dark, increase exposure
                    new_exposure = self.current_exposure * step_factor
                    direction = "increase"
                else:
                    # Too bright, decrease exposure
                    new_exposure = self.current_exposure / step_factor
                    direction = "decrease"
                
                # Apply bounds checking
                if new_exposure > self.max_exposure:
                    self.logger.warning(f"Exposure would exceed maximum ({self.max_exposure}s), using maximum")
                    new_exposure = self.max_exposure
                elif new_exposure < self.min_exposure:
                    self.logger.warning(f"Exposure would be below minimum ({self.min_exposure}s), using minimum")
                    new_exposure = self.min_exposure
                
                # Log the adjustment
                change_percent = ((new_exposure - self.current_exposure) / self.current_exposure) * 100
                self.logger.info(f"Adjusting exposure: {self.current_exposure:.3f}s → {new_exposure:.3f}s "
                               f"({change_percent:+.1f}%, {direction}, step_factor={step_factor:.2f})")
                
                self.current_exposure = new_exposure
                
                # Allow camera to adjust
                time.sleep(0.2)  # Slightly longer delay for better stability
            
            return warning_status(f"Could not achieve target count rate after {self.max_adjustment_attempts} attempts")
            
        except Exception as e:
            self.logger.error(f"Error adjusting exposure: {e}")
            return error_status(f"Exposure adjustment failed: {e}")
    
    def _calculate_adaptive_step(self, relative_distance: float, oscillation_detected: bool, attempt: int) -> float:
        """Calculate adaptive step size based on distance from target and oscillation state.
        
        Args:
            relative_distance: Distance from target as fraction (0.0 = at target, 1.0 = 100% off)
            oscillation_detected: Whether oscillation was detected
            attempt: Current attempt number
            
        Returns:
            float: Step factor to apply to exposure time
        """
        # Base step factors for different distance ranges
        if relative_distance > 0.5:  # Very far from target (>50% off)
            base_step = 2.0
        elif relative_distance > 0.2:  # Far from target (20-50% off)
            base_step = 1.5
        elif relative_distance > 0.1:  # Moderate distance (10-20% off)
            base_step = 1.3
        elif relative_distance > 0.05:  # Close to target (5-10% off)
            base_step = 1.15
        else:  # Very close to target (<5% off)
            base_step = 1.08
        
        # Reduce step size if oscillation detected
        if oscillation_detected:
            base_step = min(base_step, 1.2)  # Conservative step when oscillating
        
        # Gradually reduce step size with attempts (convergence)
        attempt_factor = max(0.8, 1.0 - (attempt * 0.05))  # Reduce by 5% per attempt, minimum 0.8
        
        final_step = base_step * attempt_factor
        
        # Ensure reasonable bounds
        final_step = max(1.05, min(2.5, final_step))
        
        return final_step
    
    def _detect_oscillation(self, count_rates: list, exposures: list) -> bool:
        """Detect oscillation in count rates and exposures.
        
        Args:
            count_rates: List of recent count rates
            exposures: List of recent exposure times
            
        Returns:
            bool: True if oscillation is detected
        """
        if len(count_rates) < 4 or len(exposures) < 4:
            return False
        
        # Check for alternating pattern in count rates (crossing target)
        target = self.target_count_rate
        crossings = 0
        for i in range(1, len(count_rates)):
            if (count_rates[i-1] < target and count_rates[i] > target) or \
               (count_rates[i-1] > target and count_rates[i] < target):
                crossings += 1
        
        # Check for alternating exposure changes (increasing/decreasing pattern)
        exposure_changes = []
        for i in range(1, len(exposures)):
            change = exposures[i] - exposures[i-1]
            exposure_changes.append(change > 0)  # True if increasing
        
        alternating_exposures = 0
        for i in range(1, len(exposure_changes)):
            if exposure_changes[i] != exposure_changes[i-1]:
                alternating_exposures += 1
        
        # Oscillation detected if:
        # 1. Multiple crossings of target value, OR
        # 2. Alternating exposure changes with small improvements
        oscillation = (crossings >= 2) or (alternating_exposures >= 2 and len(count_rates) >= 4)
        
        if oscillation:
            self.logger.debug(f"Oscillation indicators: crossings={crossings}, alternating_exposures={alternating_exposures}")
        
        return oscillation
    
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
            
            # Get frame data - handle Status objects from camera
            frame = None
            if isinstance(frame_status.data, np.ndarray):
                frame = frame_status.data
                self.logger.debug(f"Using frame data directly: shape={frame.shape}, dtype={frame.dtype}")
            elif hasattr(frame_status.data, 'data') and isinstance(frame_status.data.data, np.ndarray):
                # Handle nested Status objects
                frame = frame_status.data.data
                self.logger.debug(f"Extracted frame from Status object: shape={frame.shape}, dtype={frame.dtype}")
            elif hasattr(frame_status.data, 'data') and hasattr(frame_status.data.data, 'data') and isinstance(frame_status.data.data.data, np.ndarray):
                # Handle double-nested Status objects
                frame = frame_status.data.data.data
                self.logger.debug(f"Extracted frame from double-nested Status object: shape={frame.shape}, dtype={frame.dtype}")
            elif isinstance(frame_status.data, list):
                # Convert list to numpy array (for some camera types)
                frame = np.array(frame_status.data)
                self.logger.debug(f"Converted list to numpy array: shape={frame.shape}, dtype={frame.dtype}")
            else:
                # Try to extract data from Status object recursively
                current_data = frame_status.data
                depth = 0
                while hasattr(current_data, 'data') and depth < 5:  # Prevent infinite recursion
                    current_data = current_data.data
                    depth += 1
                    self.logger.debug(f"Extracting data at depth {depth}: {type(current_data)}")
                    
                    if isinstance(current_data, np.ndarray):
                        frame = current_data
                        self.logger.debug(f"Found numpy array at depth {depth}: shape={frame.shape}, dtype={frame.dtype}")
                        break
                    elif isinstance(current_data, list):
                        frame = np.array(current_data)
                        self.logger.debug(f"Found list at depth {depth}, converted to numpy array: shape={frame.shape}, dtype={frame.dtype}")
                        break
                
                if frame is None:
                    self.logger.error(f"Unexpected frame data type: {type(frame_status.data)}")
                    self.logger.error(f"Frame data content: {frame_status.data}")
                    return error_status(f"Unexpected frame data type: {type(frame_status.data)}")
            
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
            # Frame should already be a numpy array from _capture_test_frame
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
            
            # Calculate statistics on original data (no conversion to float32)
            mean_value = np.mean(frame)
            std_value = np.std(frame)
            min_value = np.min(frame)
            max_value = np.max(frame)
            
            # Get bit depth from camera configuration
            camera_config = self.config.get_camera_config()
            bit_depth = camera_config.get('bit_depth', 16)  # Default to 16-bit
            
            # Calculate maximum possible count based on bit depth
            max_possible_count = (2 ** bit_depth) - 1
            
            # Calculate count rate as percentage of maximum
            count_rate = mean_value / max_possible_count
            
            # Add debug information to understand the values
            self.logger.debug(f"Frame analysis: mean={mean_value:.2f}, max={max_value:.2f}, "
                            f"bit_depth={bit_depth}, max_possible={max_possible_count}, count_rate={count_rate:.1%}")
            
            # Cap count rate at 100% for saturation
            if count_rate > 1.0:
                self.logger.warning(f"Count rate {count_rate:.1%} exceeds 100%, capping at 100% (saturation)")
                count_rate = 1.0
            
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
                    # Extract frame data and details from Status object
                    frame_data = frame_status.data
                    frame_details = getattr(frame_status, 'details', {})
                    
                    # Handle nested Status objects
                    if hasattr(frame_data, 'data'):
                        frame_data = frame_data.data
                        # Get details from nested status if available
                        if hasattr(frame_status.data, 'details'):
                            frame_details.update(frame_status.data.details)
                    
                    # Ensure we have the current exposure time in frame details
                    if 'exposure_time_s' not in frame_details:
                        frame_details['exposure_time_s'] = self.current_exposure
                    
                    # Ensure we have gain and binning information
                    if 'gain' not in frame_details and gain is not None:
                        frame_details['gain'] = gain
                    if 'binning' not in frame_details and binning is not None:
                        frame_details['binning'] = binning
                    
                    # Create a Status object with both data and details for FITS saving
                    from status import success_status
                    frame_with_details = success_status("Frame captured", data=frame_data, details=frame_details)
                    
                    # Save the frame directly as FITS with proper details
                    save_status = self.video_capture._save_fits_unified(frame_with_details, filepath)
                    if save_status.is_success:
                        captured_files.append(filepath)
                        self.logger.debug(f"Captured flat {i+1}/{self.num_flats}: {filename} (exposure: {self.current_exposure:.3f}s)")
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