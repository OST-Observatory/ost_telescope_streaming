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

from status import Status, success_status, error_status, warning_status
from exceptions import DarkCaptureError
from video_capture import VideoCapture
from utils.status_utils import unwrap_status


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
        
        # Load dark capture configuration
        dark_config = self.config.get_dark_config()
        self.num_darks = dark_config.get('num_darks', 20)
        self.flat_exposure_time = dark_config.get('flat_exposure_time', None)
        self.science_exposure_time = dark_config.get('science_exposure_time', 1.0)
        self.min_exposure = dark_config.get('min_exposure', 0.001)  # 1ms for bias
        self.max_exposure = dark_config.get('max_exposure', 60.0)  # 60s max
        self.exposure_factors = dark_config.get('exposure_factors', [0.5, 1.0, 2.0, 4.0])
        # Resolve output directory (support both new and legacy key)
        self.dark_output_dir = (
            dark_config.get('output_dir')
            or dark_config.get('output_directory')
            or 'darks'
        )
        
        # Ensure output directory exists
        os.makedirs(self.dark_output_dir, exist_ok=True)
        
        self.video_capture = None
        self.is_running = False
        
    def _create_output_directories(self):
        """Create necessary output directories."""
        try:
            # Create dark frames directory (use resolved path)
            output_dir = Path(self.dark_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Dark frames directory ready: {output_dir}")
        except Exception as e:
            self.logger.warning(f"Failed to create dark output directories: {e}")
    
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
            
            # Try to read exposure time from FITS headers
            try:
                import astropy.io.fits as fits
                
                # Check first few flat files for exposure time
                for filename in flat_files[:3]:  # Check first 3 files
                    filepath = os.path.join(flat_dir, filename)
                    try:
                        with fits.open(filepath) as hdul:
                            header = hdul[0].header
                            exp_time = header.get('EXPTIME')
                            if exp_time is not None:
                                self.logger.info(f"Detected flat exposure time from {filename}: {exp_time}s")
                                return float(exp_time)
                    except Exception as e:
                        self.logger.debug(f"Could not read {filename}: {e}")
                        continue
                
                # If no exposure time found in headers, try to extract from filename
                # Look for patterns like flat_YYYYMMDD_HHMMSS_001.fits
                for filename in flat_files:
                    # For now, return a reasonable default
                    # In a full implementation, you might parse the filename or use other methods
                    pass
                
                self.logger.warning("Could not detect exposure time from FITS headers, using default")
                return 1.0
                
            except ImportError:
                self.logger.warning("Astropy not available, cannot read FITS headers")
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
                
                # Set exposure time on camera if possible
                if hasattr(self.video_capture, 'camera') and self.video_capture.camera:
                    if hasattr(self.video_capture.camera, 'exposure_time'):
                        old_exposure = getattr(self.video_capture.camera, 'exposure_time', 'unknown')
                        self.video_capture.camera.exposure_time = exposure_time
                        self.logger.debug(f"Set camera exposure time: {old_exposure} → {exposure_time}s")
                    elif hasattr(self.video_capture.camera, 'set_exposure_time'):
                        self.video_capture.camera.set_exposure_time(exposure_time)
                        self.logger.debug(f"Set camera exposure time via set_exposure_time: {exposure_time}s")
                    else:
                        self.logger.debug(f"Camera does not support exposure time setting, will use parameter in capture method")
                else:
                    self.logger.debug(f"No camera available for exposure time setting, will use parameter in capture method")
                
                # Allow camera to adjust
                time.sleep(0.2)
                
                # Capture darks for this exposure time
                result = self._capture_dark_series(exposure_time)
                
                if result.is_success:
                    # Ensure result.data is a list, handle None case
                    captured_files = result.data if result.data is not None else []
                    if not isinstance(captured_files, list):
                        self.logger.warning(f"Unexpected data type for captured files: {type(captured_files)}")
                        captured_files = []
                    
                    all_results[exposure_time] = captured_files
                    total_captured += len(captured_files)
                    self.logger.info(f"✅ Captured {len(captured_files)} darks for {exposure_time:.3f}s")
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
            
            # Initialize gain and binning variables
            gain = None
            binning = None
            
            # Create exposure-specific subdirectory
            exp_dir = os.path.join(self.dark_output_dir, f"exp_{exposure_time:.3f}s")
            os.makedirs(exp_dir, exist_ok=True)
            self.logger.debug(f"Created/verified directory: {exp_dir}")
            
            for i in range(self.num_darks):
                # Generate filename
                if exposure_time == self.min_exposure:
                    # Bias frames
                    filename = f"bias_{timestamp}_{i+1:03d}.fits"
                else:
                    # Dark frames
                    filename = f"dark_{timestamp}_{i+1:03d}.fits"
                
                filepath = os.path.join(exp_dir, filename)
                self.logger.debug(f"Will save to: {filepath}")
                
                # Capture frame with specific exposure time
                if hasattr(self.video_capture, 'capture_single_frame_ascom') and self.video_capture.camera_type == 'ascom':
                    # Get camera config for other parameters
                    camera_config = self.config.get_camera_config()
                    ascom_config = camera_config.get('ascom', {})
                    gain = ascom_config.get('gain', None)
                    binning = ascom_config.get('binning', 1)
                    
                    self.logger.debug(f"Capturing ASCOM frame: exposure={exposure_time:.3f}s, gain={gain}, binning={binning}")
                    frame_status = self.video_capture.capture_single_frame_ascom(
                        exposure_time, gain, binning
                    )
                    self.logger.debug(f"ASCOM capture result: {type(frame_status)}, success={getattr(frame_status, 'is_success', 'N/A')}")
                elif hasattr(self.video_capture, 'capture_single_frame_alpaca') and self.video_capture.camera_type == 'alpaca':
                    # Get camera config for other parameters
                    camera_config = self.config.get_camera_config()
                    alpaca_config = camera_config.get('alpaca', {})
                    gain = alpaca_config.get('gain', None)
                    binning = alpaca_config.get('binning', [1, 1])
                    
                    self.logger.debug(f"Capturing Alpaca frame: exposure={exposure_time:.3f}s, gain={gain}, binning={binning}")
                    frame_status = self.video_capture.capture_single_frame_alpaca(
                        exposure_time, gain, binning
                    )
                    self.logger.debug(f"Alpaca capture result: {type(frame_status)}, success={getattr(frame_status, 'is_success', 'N/A')}")
                    if frame_status and hasattr(frame_status, 'data'):
                        self.logger.debug(f"Alpaca capture data type: {type(frame_status.data)}")
                        if frame_status.data is not None:
                            if hasattr(frame_status.data, 'shape'):
                                self.logger.debug(f"Alpaca capture data shape: {frame_status.data.shape}")
                            elif hasattr(frame_status.data, 'data'):
                                self.logger.debug(f"Alpaca capture data has nested data: {type(frame_status.data.data)}")
                                if frame_status.data.data is not None:
                                    if hasattr(frame_status.data.data, 'shape'):
                                        self.logger.debug(f"Alpaca capture nested data shape: {frame_status.data.data.shape}")
                                    elif isinstance(frame_status.data.data, list):
                                        self.logger.debug(f"Alpaca capture nested data is list with length: {len(frame_status.data.data)}")
                                        if len(frame_status.data.data) > 0:
                                            self.logger.debug(f"First element type: {type(frame_status.data.data[0])}")
                        else:
                            self.logger.debug("Alpaca capture data is None")
                elif hasattr(self.video_capture, 'capture_single_frame'):
                    self.logger.debug(f"Capturing generic frame: exposure={exposure_time:.3f}s")
                    frame_status = self.video_capture.capture_single_frame()
                    self.logger.debug(f"Generic capture result: {type(frame_status)}, success={getattr(frame_status, 'is_success', 'N/A')}")
                else:
                    self.logger.warning(f"Failed to capture dark {i+1}: No capture method available")
                    continue
                
                # Check if frame_status is None or invalid
                if frame_status is None:
                    self.logger.warning(f"Failed to capture dark {i+1}: frame_status is None")
                    continue
                
                if frame_status.is_success:
                    # Extract frame data and details from Status object
                    frame_data, frame_details = unwrap_status(frame_status)
                    
                    self.logger.debug(f"Frame status data type: {type(frame_data)}")
                    self.logger.debug(f"Frame status details: {frame_details}")
                    
                    # Check if frame_data is None
                    if frame_data is None:
                        self.logger.warning(f"Failed to capture dark {i+1}: frame_data is None")
                        continue
                    
                    # Handle nested Status objects - extract recursively until we get actual data
                    # (nested Status unwrapping handled by unwrap_status)
                    
                    # Convert list to numpy array if needed (like in flat_capture.py)
                    if isinstance(frame_data, list):
                        self.logger.debug(f"Converting list to numpy array: list length={len(frame_data)}")
                        try:
                            frame_data = np.array(frame_data)
                            self.logger.debug(f"Successfully converted list to numpy array: shape={frame_data.shape}, dtype={frame_data.dtype}")
                        except Exception as e:
                            self.logger.error(f"Failed to convert list to numpy array: {e}")
                            continue
                    
                    # Final check for None after nested extraction
                    if frame_data is None:
                        self.logger.warning(f"Failed to capture dark {i+1}: frame_data is None after extraction")
                        self.logger.debug(f"Original frame_status.data: {frame_status.data}")
                        if hasattr(frame_status.data, 'data'):
                            self.logger.debug(f"frame_status.data.data: {frame_status.data.data}")
                        continue
                    
                    # Validate that we have actual image data (numpy array)
                    if not isinstance(frame_data, np.ndarray):
                        self.logger.warning(f"Failed to capture dark {i+1}: frame_data is not a numpy array: {type(frame_data)}")
                        self.logger.debug(f"frame_data: {frame_data}")
                        continue
                    
                    # Validate that the array has the expected shape
                    if len(frame_data.shape) < 2:
                        self.logger.warning(f"Failed to capture dark {i+1}: frame_data has invalid shape: {frame_data.shape}")
                        continue
                    
                    self.logger.debug(f"Successfully extracted image data: shape={frame_data.shape}, dtype={frame_data.dtype}")
                    
                    # Ensure we have the exposure time in frame details
                    if 'exposure_time_s' not in frame_details:
                        frame_details['exposure_time_s'] = exposure_time
                    
                    # Ensure we have gain and binning information
                    if 'gain' not in frame_details and gain is not None:
                        frame_details['gain'] = gain
                    if 'binning' not in frame_details and binning is not None:
                        frame_details['binning'] = binning
                    
                    # Create a Status object with both data and details for FITS saving
                    from status import success_status
                    
                    # Ensure frame_data is not None and is a numpy array before creating status
                    if frame_data is None:
                        self.logger.warning(f"Failed to capture dark {i+1}: frame_data is None before creating status")
                        continue
                    
                    if not isinstance(frame_data, np.ndarray):
                        self.logger.error(f"Failed to capture dark {i+1}: frame_data is not a numpy array before creating status: {type(frame_data)}")
                        continue
                    
                    frame_with_details = success_status("Frame captured", data=frame_data, details=frame_details)
                    self.logger.debug(f"Created frame_with_details: {type(frame_with_details)}")
                    self.logger.debug(f"frame_with_details.data type: {type(frame_with_details.data)}")
                    self.logger.debug(f"frame_with_details.data shape: {getattr(frame_with_details.data, 'shape', 'N/A')}")
                    
                    # Save the frame as FITS with proper details
                    self.logger.debug(f"Saving frame to: {filepath}")
                    self.logger.debug(f"Frame data type: {type(frame_data)}")
                    self.logger.debug(f"Frame data shape: {getattr(frame_data, 'shape', 'N/A')}")
                    self.logger.debug(f"Frame data dtype: {getattr(frame_data, 'dtype', 'N/A')}")
                    
                    # Ensure frame_data is a numpy array before saving
                    if not isinstance(frame_data, np.ndarray):
                        self.logger.error(f"Frame data is not a numpy array before saving: {type(frame_data)}")
                        continue
                    
                    save_status = self.video_capture._save_fits_unified(frame_with_details, filepath)
                    
                    if save_status is None:
                        self.logger.warning(f"Failed to save dark {i+1}: save_status is None")
                        continue
                    
                    if save_status.is_success:
                        captured_files.append(filepath)
                        self.logger.debug(f"Captured dark {i+1}/{self.num_darks}: {filename} (exposure: {exposure_time:.3f}s)")
                        # Verify file was actually created
                        if os.path.exists(filepath):
                            file_size = os.path.getsize(filepath)
                            self.logger.debug(f"File created successfully: {filepath} ({file_size} bytes)")
                        else:
                            self.logger.warning(f"File was not created despite success status: {filepath}")
                    else:
                        self.logger.warning(f"Failed to save dark {i+1}: {save_status.message}")
                
                                    # Small delay between captures
                    time.sleep(0.1)
                    
                    # Debug: Print progress every 10 frames
                    if (i + 1) % 10 == 0:
                        self.logger.info(f"Dark capture progress: {i + 1}/{self.num_darks} frames processed")
            
            self.logger.info(f"Dark series for {exposure_time:.3f}s completed: {len(captured_files)}/{self.num_darks} frames")
            
            # Ensure captured_files is a list
            if not isinstance(captured_files, list):
                self.logger.warning(f"captured_files is not a list: {type(captured_files)}, converting to empty list")
                captured_files = []
            
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
            
            # Set minimum exposure time on camera if possible
            if hasattr(self.video_capture, 'camera') and self.video_capture.camera:
                if hasattr(self.video_capture.camera, 'exposure_time'):
                    self.video_capture.camera.exposure_time = self.min_exposure
                    self.logger.debug(f"Set camera exposure time to {self.min_exposure}s")
                elif hasattr(self.video_capture.camera, 'set_exposure_time'):
                    self.video_capture.camera.set_exposure_time(self.min_exposure)
                    self.logger.debug(f"Set camera exposure time to {self.min_exposure}s")
            
            time.sleep(0.2)  # Allow camera to adjust
            
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
            
            # Set science exposure time on camera if possible
            if hasattr(self.video_capture, 'camera') and self.video_capture.camera:
                if hasattr(self.video_capture.camera, 'exposure_time'):
                    self.video_capture.camera.exposure_time = self.science_exposure_time
                    self.logger.debug(f"Set camera exposure time to {self.science_exposure_time}s")
                elif hasattr(self.video_capture.camera, 'set_exposure_time'):
                    self.video_capture.camera.set_exposure_time(self.science_exposure_time)
                    self.logger.debug(f"Set camera exposure time to {self.science_exposure_time}s")
            
            time.sleep(0.2)  # Allow camera to adjust
            
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