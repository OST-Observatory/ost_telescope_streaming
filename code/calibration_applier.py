#!/usr/bin/env python3
"""
Calibration Applier Module for Telescope Streaming System

This module provides functionality to apply dark and flat calibration
to captured frames using the best matching master frames based on exposure time.

The system automatically:
- Finds the best matching master dark for the frame's exposure time
- Applies dark subtraction
- Applies flat field correction
- Returns calibrated frame ready for further processing
"""

import os
import logging
import numpy as np
from typing import Optional, Tuple, Dict, Any, Union
from pathlib import Path
import glob
import re

from .status import Status, success_status, error_status, warning_status
from .exceptions import CalibrationError


class CalibrationApplier:
    """
    Automatic calibration application system.
    
    This class manages the application of dark and flat calibration
    to captured frames using the best matching master frames.
    """
    
    def __init__(self, config=None, logger=None):
        """Initialize the calibration applier.
        
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
        
        # Load configurations
        master_config = self.config.get_master_config()
        self.master_dir = master_config.get('output_dir', 'master_frames')
        
        # Cache for loaded master frames
        self.master_dark_cache = {}
        self.master_flat_cache = None
        
        # Calibration settings
        self.enable_calibration = master_config.get('enable_calibration', True)
        self.auto_load_masters = master_config.get('auto_load_masters', True)
        self.calibration_tolerance = master_config.get('calibration_tolerance', 0.1)  # 10% tolerance
        
        # Initialize master frames if auto-load is enabled
        if self.auto_load_masters:
            self._load_master_frames()
    
    def _load_master_frames(self) -> bool:
        """Load all available master frames into cache.
        
        Returns:
            bool: True if master frames loaded successfully
        """
        try:
            if not os.path.exists(self.master_dir):
                self.logger.warning(f"Master frames directory not found: {self.master_dir}")
                return False
            
            # Load master darks
            dark_files = glob.glob(os.path.join(self.master_dir, "master_dark_*.fits"))
            for dark_file in dark_files:
                exposure_time = self._extract_exposure_time(dark_file)
                if exposure_time is not None:
                    master_dark = self._load_fits_file(dark_file)
                    if master_dark is not None:
                        self.master_dark_cache[exposure_time] = {
                            'data': master_dark,
                            'file': dark_file
                        }
                        self.logger.debug(f"Loaded master dark: {exposure_time:.3f}s from {dark_file}")
            
            # Load master flat
            flat_files = glob.glob(os.path.join(self.master_dir, "master_flat_*.fits"))
            if flat_files:
                # Use the first master flat found
                flat_file = flat_files[0]
                master_flat = self._load_fits_file(flat_file)
                if master_flat is not None:
                    self.master_flat_cache = {
                        'data': master_flat,
                        'file': flat_file
                    }
                    self.logger.debug(f"Loaded master flat from {flat_file}")
            
            self.logger.info(f"Loaded {len(self.master_dark_cache)} master darks and "
                           f"{'1' if self.master_flat_cache else '0'} master flat")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading master frames: {e}")
            return False
    
    def _extract_exposure_time(self, file_path: str) -> Optional[float]:
        """Extract exposure time from master frame filename.
        
        Args:
            file_path: Path to master frame file
            
        Returns:
            Exposure time in seconds or None
        """
        # Extract from filename like "master_dark_1.000s_20250729_143022.fits"
        match = re.search(r'master_dark_(\d+\.?\d*)s_', file_path)
        if match:
            return float(match.group(1))
        
        # Extract from filename like "master_flat_1.000s_20250729_143022.fits"
        match = re.search(r'master_flat_(\d+\.?\d*)s_', file_path)
        if match:
            return float(match.group(1))
        
        return None
    
    def _find_best_master_dark(self, exposure_time: float) -> Optional[Dict[str, Any]]:
        """Find the best matching master dark for a given exposure time.
        
        Args:
            exposure_time: Frame exposure time in seconds
            
        Returns:
            Master dark data and metadata or None
        """
        if not self.master_dark_cache:
            return None
        
        # Find exact match first
        if exposure_time in self.master_dark_cache:
            return self.master_dark_cache[exposure_time]
        
        # Find closest match within tolerance
        closest_dark = None
        min_diff = float('inf')
        tolerance = exposure_time * self.calibration_tolerance
        
        for dark_exp_time, dark_data in self.master_dark_cache.items():
            diff = abs(dark_exp_time - exposure_time)
            if diff <= tolerance and diff < min_diff:
                min_diff = diff
                closest_dark = dark_data
        
        if closest_dark:
            self.logger.debug(f"Using master dark {min_diff:.3f}s different from frame exposure {exposure_time:.3f}s")
        
        return closest_dark
    
    def calibrate_frame(self, frame_data: np.ndarray, exposure_time: float, 
                       frame_info: Optional[Dict[str, Any]] = None) -> Status:
        """Apply dark and flat calibration to a frame.
        
        Args:
            frame_data: Raw frame data as numpy array
            exposure_time: Frame exposure time in seconds
            frame_info: Additional frame information (optional)
            
        Returns:
            Status: Success or error status with calibrated frame data
        """
        try:
            if not self.enable_calibration:
                self.logger.debug("Calibration disabled, returning original frame")
                return success_status(
                    "Calibration disabled",
                    data=frame_data,
                    details={'calibration_applied': False}
                )
            
            if not self.master_dark_cache and not self.master_flat_cache:
                self.logger.warning("No master frames available for calibration")
                return warning_status(
                    "No master frames available",
                    data=frame_data,
                    details={'calibration_applied': False, 'reason': 'no_master_frames'}
                )
            
            self.logger.debug(f"Calibrating frame with {exposure_time:.3f}s exposure")
            
            # Start with original frame
            calibrated_frame = frame_data.astype(np.float32)
            calibration_details = {
                'original_exposure_time': exposure_time,
                'dark_subtraction_applied': False,
                'flat_correction_applied': False,
                'master_dark_used': None,
                'master_flat_used': None
            }
            
            # Apply dark subtraction
            master_dark = self._find_best_master_dark(exposure_time)
            if master_dark:
                calibrated_frame = calibrated_frame - master_dark['data'].astype(np.float32)
                calibration_details['dark_subtraction_applied'] = True
                calibration_details['master_dark_used'] = master_dark['file']
                self.logger.debug(f"Applied dark subtraction using {master_dark['file']}")
            else:
                self.logger.warning(f"No suitable master dark found for {exposure_time:.3f}s exposure")
            
            # Apply flat correction
            if self.master_flat_cache:
                # Avoid division by zero
                flat_data = self.master_flat_cache['data'].astype(np.float32)
                flat_data_safe = np.where(flat_data > 0, flat_data, 1.0)
                calibrated_frame = calibrated_frame / flat_data_safe
                calibration_details['flat_correction_applied'] = True
                calibration_details['master_flat_used'] = self.master_flat_cache['file']
                self.logger.debug(f"Applied flat correction using {self.master_flat_cache['file']}")
            else:
                self.logger.warning("No master flat available for flat correction")
            
            # Determine if calibration was applied
            calibration_applied = (calibration_details['dark_subtraction_applied'] or 
                                 calibration_details['flat_correction_applied'])
            
            if calibration_applied:
                self.logger.info(f"Frame calibrated successfully: "
                               f"Dark={calibration_details['dark_subtraction_applied']}, "
                               f"Flat={calibration_details['flat_correction_applied']}")
            else:
                self.logger.warning("No calibration applied to frame")
            
            return success_status(
                "Frame calibration completed",
                data=calibrated_frame,
                details=calibration_details
            )
            
        except Exception as e:
            self.logger.error(f"Error calibrating frame: {e}")
            return error_status(f"Frame calibration failed: {e}")
    
    def calibrate_frame_from_file(self, frame_file: str, exposure_time: float) -> Status:
        """Apply calibration to a frame loaded from file.
        
        Args:
            frame_file: Path to frame file
            exposure_time: Frame exposure time in seconds
            
        Returns:
            Status: Success or error status with calibrated frame data
        """
        try:
            # Load frame from file
            frame_data = self._load_fits_file(frame_file)
            if frame_data is None:
                return error_status(f"Failed to load frame from {frame_file}")
            
            # Apply calibration
            return self.calibrate_frame(frame_data, exposure_time, {'file': frame_file})
            
        except Exception as e:
            self.logger.error(f"Error calibrating frame from file {frame_file}: {e}")
            return error_status(f"Frame calibration from file failed: {e}")
    
    def _load_fits_file(self, file_path: str) -> Optional[np.ndarray]:
        """Load FITS file and return data as numpy array.
        
        Args:
            file_path: Path to FITS file
            
        Returns:
            Image data as numpy array or None
        """
        try:
            # Simplified FITS loading - in real implementation use astropy.io.fits
            # For now, create dummy data for demonstration
            import numpy as np
            # This is a placeholder - replace with actual FITS loading
            dummy_data = np.random.normal(1000, 100, (2048, 2048)).astype(np.float32)
            return dummy_data
            
        except Exception as e:
            self.logger.warning(f"Failed to load FITS file {file_path}: {e}")
            return None
    
    def reload_master_frames(self) -> bool:
        """Reload master frames from disk.
        
        Returns:
            bool: True if reload successful
        """
        try:
            self.logger.info("Reloading master frames...")
            
            # Clear existing cache
            self.master_dark_cache.clear()
            self.master_flat_cache = None
            
            # Reload master frames
            success = self._load_master_frames()
            
            if success:
                self.logger.info("Master frames reloaded successfully")
            else:
                self.logger.warning("Failed to reload master frames")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error reloading master frames: {e}")
            return False
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """Get current calibration system status.
        
        Returns:
            Dict containing calibration status
        """
        return {
            'enable_calibration': self.enable_calibration,
            'auto_load_masters': self.auto_load_masters,
            'calibration_tolerance': self.calibration_tolerance,
            'master_directory': self.master_dir,
            'master_darks_loaded': len(self.master_dark_cache),
            'master_flat_loaded': self.master_flat_cache is not None,
            'available_exposure_times': list(self.master_dark_cache.keys()) if self.master_dark_cache else []
        }
    
    def get_master_frame_info(self) -> Dict[str, Any]:
        """Get detailed information about loaded master frames.
        
        Returns:
            Dict containing master frame information
        """
        dark_info = {}
        for exp_time, dark_data in self.master_dark_cache.items():
            dark_info[f"{exp_time:.3f}s"] = {
                'file': dark_data['file'],
                'shape': dark_data['data'].shape,
                'dtype': str(dark_data['data'].dtype)
            }
        
        flat_info = None
        if self.master_flat_cache:
            flat_info = {
                'file': self.master_flat_cache['file'],
                'shape': self.master_flat_cache['data'].shape,
                'dtype': str(self.master_flat_cache['data'].dtype)
            }
        
        return {
            'master_darks': dark_info,
            'master_flat': flat_info
        } 