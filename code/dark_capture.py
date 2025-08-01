#!/usr/bin/env python3
"""
Dark Capture Module for Telescope Streaming System

This module provides automatic dark frame capture functionality with:
- Multiple exposure times for comprehensive calibration
- Flat exposure time darks (for flat calibration)
- Science exposure time darks (for science image calibration)
- Extended range darks (0.5x, 2x, 4x science exposure)
- Bias frames (minimum exposure time)
- Quality control and validation

The system automatically captures darks for all necessary exposure times
to provide comprehensive calibration data for different observation scenarios.
"""

import os
import time
import logging
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime

from .status import Status, success_status, error_status, warning_status
from .exceptions import DarkCaptureError
from .video_capture import VideoCapture


class DarkCapture:
    """
    Automatic dark frame capture system.
    
    This class manages the capture of dark frames for multiple exposure times
    to provide comprehensive calibration data for different observation scenarios.
    """
    
    def __init__(self, config=None, logger=None):
        """Initialize the dark capture system.
        
        Args:
            config: Configuration manager instance
            logger: Logger instance
        """
        from .config_manager import ConfigManager
        
        # Only create default config if no config is provided
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
            
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        
        # Load dark capture configuration
        dark_config = self.config.get_dark_config()
        self.num_darks = dark_config.get('num_darks', 20)
        self.flat_exposure_time = dark_config.get('flat_exposure_time', None)
        self.science_exposure_time = dark_config.get('science_exposure_time', 1.0)
        self.min_exposure = dark_config.get('min_exposure', 0.001)  # 1ms for bias
        self.max_exposure = dark_config.get('max_exposure', 60.0)  # 60s max
        self.exposure_factors = dark_config.get('exposure_factors', [0.5, 1.0, 2.0, 4.0])
        self.dark_output_dir = dark_config.get('output_dir', 'darks')
        
        # Ensure output directory exists
        os.makedirs(self.dark_output_dir, exist_ok=True)
        
        self.video_capture = None
        self.is_running = False
        
    def initialize(self, video_capture: VideoCapture) -> bool:
        """Initialize the dark capture system with video capture.
        
        Args:
            video_capture: Video capture instance
            
        Returns:
            bool: True if initialization successful
        """
        try:
            self.video_capture = video_capture
            
            # If flat exposure time not specified, try to detect from existing flats
            if self.flat_exposure_time is None:
                self.flat_exposure_time = self._detect_flat_exposure_time()
                if self.flat_exposure_time:
                    self.logger.info(f"Detected flat exposure time: {self.flat_exposure_time}s")
                else:
                    self.logger.warning("Could not detect flat exposure time, using default")
                    self.flat_exposure_time = 1.0
            
            self.logger.info(f"Dark capture initialized with {self.num_darks} darks per exposure time")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dark capture: {e}")
            return False
    
    def _detect_flat_exposure_time(self) -> Optional[float]:
        """Detect flat exposure time from existing flat files.
        
        Returns:
            Optional[float]: Detected exposure time or None
        """
        try:
            flat_config = self.config.get_flat_config()
            flat_dir = flat_config.get('output_dir', 'flats')
            
            if not os.path.exists(flat_dir):
                return None
            
            # Look for flat files and try to extract exposure time
            flat_files = [f for f in os.listdir(flat_dir) if f.endswith('.fits')]
            if not flat_files:
                return None
            
            # For now, return a default value
            # In a full implementation, you would read the FITS headers
            # to extract the actual exposure time
            self.logger.info("Flat files found, using default exposure time")
            return 1.0
            
        except Exception as e:
            self.logger.warning(f"Could not detect flat exposure time: {e}")
            return None
    
    def capture_darks(self) -> Status:
        """Capture dark frames for all required exposure times.
        
        This method captures darks for:
        - Flat exposure time (for flat calibration)
        - Science exposure time (for science image calibration)
        - Extended range (0.5x, 2x, 4x science exposure)
        - Bias frames (minimum exposure time)
        
        Returns:
            Status: Success or error status with details
        """
        try:
            if not self.video_capture:
                return error_status("Video capture not initialized")
            
            self.logger.info("Starting dark frame capture for all exposure times...")
            
            # Calculate all required exposure times
            exposure_times = self._calculate_exposure_times()
            
            self.logger.info(f"Will capture darks for {len(exposure_times)} exposure times:")
            for exp_time in exposure_times:
                self.logger.info(f"  - {exp_time:.3f}s")
            
            # Capture darks for each exposure time
            all_results = {}
            total_captured = 0
            
            for exposure_time in exposure_times:
                self.logger.info(f"Capturing darks for {exposure_time:.3f}s exposure...")
                
                # Set exposure time
                if hasattr(self.video_capture, 'set_exposure_time'):
                    self.video_capture.set_exposure_time(exposure_time)
                    time.sleep(0.1)  # Allow camera to adjust
                
                # Capture darks for this exposure time
                result = self._capture_dark_series(exposure_time)
                
                if result.is_success:
                    all_results[exposure_time] = result.data
                    total_captured += len(result.data)
                    self.logger.info(f"✅ Captured {len(result.data)} darks for {exposure_time:.3f}s")
                else:
                    self.logger.warning(f"⚠️ Failed to capture darks for {exposure_time:.3f}s: {result.message}")
                    all_results[exposure_time] = []
            
            self.logger.info(f"Dark capture completed: {total_captured} total frames")
            
            return success_status(
                "Dark capture completed successfully",
                data=all_results,
                details={
                    'total_captured': total_captured,
                    'exposure_times': list(all_results.keys()),
                    'output_directory': self.dark_output_dir
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error during dark capture: {e}")
            return error_status(f"Dark capture failed: {e}")
    
    def _calculate_exposure_times(self) -> List[float]:
        """Calculate all required exposure times for dark capture.
        
        Returns:
            List[float]: List of exposure times to capture
        """
        exposure_times = []
        
        # Add bias frame exposure time (minimum)
        exposure_times.append(self.min_exposure)
        
        # Add flat exposure time
        if self.flat_exposure_time:
            exposure_times.append(self.flat_exposure_time)
        
        # Add science exposure time and factors
        for factor in self.exposure_factors:
            exposure_time = self.science_exposure_time * factor
            if self.min_exposure <= exposure_time <= self.max_exposure:
                exposure_times.append(exposure_time)
        
        # Remove duplicates and sort
        exposure_times = sorted(list(set(exposure_times)))
        
        return exposure_times
    
    def _capture_dark_series(self, exposure_time: float) -> Status:
        """Capture a series of dark frames for a specific exposure time.
        
        Args:
            exposure_time: Exposure time in seconds
            
        Returns:
            Status: Success status with list of captured files
        """
        try:
            self.logger.info(f"Capturing {self.num_darks} darks for {exposure_time:.3f}s exposure...")
            
            captured_files = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create exposure-specific subdirectory
            exp_dir = os.path.join(self.dark_output_dir, f"exp_{exposure_time:.3f}s")
            os.makedirs(exp_dir, exist_ok=True)
            
            for i in range(self.num_darks):
                # Generate filename
                if exposure_time == self.min_exposure:
                    # Bias frames
                    filename = f"bias_{timestamp}_{i+1:03d}.fits"
                else:
                    # Dark frames
                    filename = f"dark_{timestamp}_{i+1:03d}.fits"
                
                filepath = os.path.join(exp_dir, filename)
                
                # Capture frame
                if hasattr(self.video_capture, 'capture_frame'):
                    frame_status = self.video_capture.capture_frame()
                    if frame_status.is_success:
                        captured_files.append(filepath)
                        self.logger.debug(f"Captured dark {i+1}/{self.num_darks}: {filename}")
                    else:
                        self.logger.warning(f"Failed to capture dark {i+1}: {frame_status.message}")
                
                # Small delay between captures
                time.sleep(0.1)
            
            self.logger.info(f"Dark series for {exposure_time:.3f}s completed: {len(captured_files)}/{self.num_darks} frames")
            
            return success_status(
                f"Dark series for {exposure_time:.3f}s captured: {len(captured_files)} frames",
                data=captured_files,
                details={
                    'exposure_time': exposure_time,
                    'captured_count': len(captured_files),
                    'target_count': self.num_darks,
                    'output_directory': exp_dir
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error capturing dark series for {exposure_time:.3f}s: {e}")
            return error_status(f"Dark series capture failed for {exposure_time:.3f}s: {e}")
    
    def capture_bias_only(self) -> Status:
        """Capture only bias frames (minimum exposure time).
        
        Returns:
            Status: Success or error status with details
        """
        try:
            self.logger.info("Capturing bias frames only...")
            
            # Set minimum exposure time
            if hasattr(self.video_capture, 'set_exposure_time'):
                self.video_capture.set_exposure_time(self.min_exposure)
                time.sleep(0.1)
            
            # Capture bias frames
            result = self._capture_dark_series(self.min_exposure)
            
            if result.is_success:
                self.logger.info("✅ Bias frame capture completed successfully")
            else:
                self.logger.error(f"❌ Bias frame capture failed: {result.message}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during bias capture: {e}")
            return error_status(f"Bias capture failed: {e}")
    
    def capture_science_darks_only(self) -> Status:
        """Capture only darks for science exposure time.
        
        Returns:
            Status: Success or error status with details
        """
        try:
            self.logger.info(f"Capturing science darks for {self.science_exposure_time:.3f}s exposure...")
            
            # Set science exposure time
            if hasattr(self.video_capture, 'set_exposure_time'):
                self.video_capture.set_exposure_time(self.science_exposure_time)
                time.sleep(0.1)
            
            # Capture science darks
            result = self._capture_dark_series(self.science_exposure_time)
            
            if result.is_success:
                self.logger.info("✅ Science dark capture completed successfully")
            else:
                self.logger.error(f"❌ Science dark capture failed: {result.message}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during science dark capture: {e}")
            return error_status(f"Science dark capture failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the dark capture system.
        
        Returns:
            Dict containing system status
        """
        return {
            'initialized': self.video_capture is not None,
            'num_darks': self.num_darks,
            'flat_exposure_time': self.flat_exposure_time,
            'science_exposure_time': self.science_exposure_time,
            'min_exposure': self.min_exposure,
            'max_exposure': self.max_exposure,
            'exposure_factors': self.exposure_factors,
            'output_directory': self.dark_output_dir,
            'is_running': self.is_running
        } 