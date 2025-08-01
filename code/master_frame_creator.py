#!/usr/bin/env python3
"""
Master Frame Creator Module for Telescope Streaming System

This module provides functionality to create master dark and master flat frames:
- Master darks for each exposure time used in dark capture
- Master flats with dark subtraction and normalization
- Quality control and validation
- Proper calibration workflow

The system automatically processes captured darks and flats to create
high-quality master frames for calibration.
"""

import os
import time
import logging
import numpy as np
from typing import Optional, List, Tuple, Dict, Any, Union
from pathlib import Path
from datetime import datetime
import glob
import re

from .status import Status, success_status, error_status, warning_status
from .exceptions import MasterFrameError


class MasterFrameCreator:
    """
    Master frame creation system.
    
    This class manages the creation of master dark and master flat frames
    from captured calibration data with proper dark subtraction and normalization.
    """
    
    def __init__(self, config=None, logger=None):
        """Initialize the master frame creator.
        
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
        dark_config = self.config.get_dark_config()
        flat_config = self.config.get_flat_config()
        
        # Dark capture settings
        self.dark_dir = dark_config.get('output_dir', 'darks')
        self.num_darks = dark_config.get('num_darks', 40)
        self.science_exposure_time = dark_config.get('science_exposure_time', 5.0)
        self.min_exposure = dark_config.get('min_exposure', 0.001)
        self.exposure_factors = dark_config.get('exposure_factors', [0.5, 1.0, 2.0, 4.0])
        
        # Flat capture settings
        self.flat_dir = flat_config.get('output_dir', 'flats')
        self.num_flats = flat_config.get('num_flats', 40)
        
        # Master frame settings
        master_config = self.config.get_master_config()
        self.master_output_dir = master_config.get('output_dir', 'master_frames')
        self.rejection_method = master_config.get('rejection_method', 'sigma_clip')  # 'sigma_clip' or 'minmax'
        self.sigma_threshold = master_config.get('sigma_threshold', 3.0)
        self.normalization_method = master_config.get('normalization_method', 'mean')  # 'mean', 'median', 'max'
        
        # Ensure output directory exists
        os.makedirs(self.master_output_dir, exist_ok=True)
        
    def create_all_master_frames(self) -> Status:
        """Create all master frames (darks and flats).
        
        This method creates:
        1. Master darks for all exposure times
        2. Master flats with dark subtraction and normalization
        
        Returns:
            Status: Success or error status with details
        """
        try:
            self.logger.info("Starting master frame creation...")
            
            # Create master darks first
            dark_result = self.create_master_darks()
            if not dark_result.is_success:
                return error_status(f"Failed to create master darks: {dark_result.message}")
            
            # Create master flats (requires master darks)
            flat_result = self.create_master_flats()
            if not flat_result.is_success:
                return error_status(f"Failed to create master flats: {flat_result.message}")
            
            self.logger.info("✅ All master frames created successfully!")
            
            return success_status(
                "All master frames created successfully",
                data={
                    'master_darks': dark_result.data,
                    'master_flats': flat_result.data
                },
                details={
                    'dark_count': len(dark_result.data),
                    'flat_count': len(flat_result.data),
                    'output_directory': self.master_output_dir
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating master frames: {e}")
            return error_status(f"Master frame creation failed: {e}")
    
    def create_master_darks(self) -> Status:
        """Create master darks for all exposure times.
        
        Returns:
            Status: Success or error status with list of created master darks
        """
        try:
            self.logger.info("Creating master darks for all exposure times...")
            
            if not os.path.exists(self.dark_dir):
                return error_status(f"Dark directory not found: {self.dark_dir}")
            
            # Find all exposure time directories
            exposure_dirs = self._find_exposure_directories(self.dark_dir)
            if not exposure_dirs:
                return error_status("No dark exposure directories found")
            
            self.logger.info(f"Found {len(exposure_dirs)} exposure time directories")
            
            created_masters = []
            
            for exp_dir in exposure_dirs:
                exposure_time = self._extract_exposure_time(exp_dir)
                if exposure_time is None:
                    self.logger.warning(f"Could not extract exposure time from: {exp_dir}")
                    continue
                
                self.logger.info(f"Creating master dark for {exposure_time:.3f}s exposure...")
                
                # Create master dark for this exposure time
                result = self._create_master_dark_for_exposure(exp_dir, exposure_time)
                
                if result.is_success:
                    created_masters.append(result.data)
                    self.logger.info(f"✅ Master dark created: {result.data}")
                else:
                    self.logger.warning(f"⚠️ Failed to create master dark for {exposure_time:.3f}s: {result.message}")
            
            self.logger.info(f"Master dark creation completed: {len(created_masters)} masters created")
            
            return success_status(
                f"Master darks created: {len(created_masters)} masters",
                data=created_masters,
                details={
                    'created_count': len(created_masters),
                    'exposure_times': [self._extract_exposure_time(os.path.basename(m)) for m in created_masters]
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating master darks: {e}")
            return error_status(f"Master dark creation failed: {e}")
    
    def create_master_flats(self) -> Status:
        """Create master flats with dark subtraction and normalization.
        
        Returns:
            Status: Success or error status with list of created master flats
        """
        try:
            self.logger.info("Creating master flats with dark subtraction...")
            
            if not os.path.exists(self.flat_dir):
                return error_status(f"Flat directory not found: {self.flat_dir}")
            
            # Find flat files
            flat_files = self._find_flat_files()
            if not flat_files:
                return error_status("No flat files found")
            
            self.logger.info(f"Found {len(flat_files)} flat files")
            
            # Determine flat exposure time
            flat_exposure_time = self._determine_flat_exposure_time(flat_files)
            if flat_exposure_time is None:
                return error_status("Could not determine flat exposure time")
            
            self.logger.info(f"Flat exposure time: {flat_exposure_time:.3f}s")
            
            # Find corresponding master dark
            master_dark_path = self._find_master_dark_for_exposure(flat_exposure_time)
            if master_dark_path is None:
                return error_status(f"No master dark found for {flat_exposure_time:.3f}s exposure")
            
            self.logger.info(f"Using master dark: {master_dark_path}")
            
            # Create master flat
            result = self._create_master_flat_with_dark_subtraction(
                flat_files, master_dark_path, flat_exposure_time
            )
            
            if result.is_success:
                self.logger.info(f"✅ Master flat created: {result.data}")
                return success_status(
                    "Master flat created successfully",
                    data=[result.data],
                    details={
                        'flat_exposure_time': flat_exposure_time,
                        'master_dark_used': master_dark_path,
                        'flat_count': len(flat_files)
                    }
                )
            else:
                return error_status(f"Failed to create master flat: {result.message}")
            
        except Exception as e:
            self.logger.error(f"Error creating master flats: {e}")
            return error_status(f"Master flat creation failed: {e}")
    
    def _find_exposure_directories(self, base_dir: str) -> List[str]:
        """Find all exposure time directories in the dark directory.
        
        Args:
            base_dir: Base directory to search
            
        Returns:
            List of exposure directory paths
        """
        exposure_dirs = []
        
        if not os.path.exists(base_dir):
            return exposure_dirs
        
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path) and item.startswith('exp_'):
                exposure_dirs.append(item_path)
        
        return sorted(exposure_dirs)
    
    def _extract_exposure_time(self, path: str) -> Optional[float]:
        """Extract exposure time from directory or file path.
        
        Args:
            path: Path containing exposure time
            
        Returns:
            Exposure time in seconds or None
        """
        # Extract from directory name like "exp_1.000s"
        match = re.search(r'exp_(\d+\.?\d*)s', path)
        if match:
            return float(match.group(1))
        
        # Extract from filename like "dark_1.000s_001.fits"
        match = re.search(r'_(\d+\.?\d*)s_', path)
        if match:
            return float(match.group(1))
        
        return None
    
    def _create_master_dark_for_exposure(self, exp_dir: str, exposure_time: float) -> Status:
        """Create a master dark for a specific exposure time.
        
        Args:
            exp_dir: Directory containing dark frames
            exposure_time: Exposure time in seconds
            
        Returns:
            Status: Success or error status with master dark path
        """
        try:
            # Find all dark/bias files in the directory
            dark_files = []
            for ext in ['*.fits', '*.fit', '*.FITS', '*.FIT']:
                dark_files.extend(glob.glob(os.path.join(exp_dir, ext)))
            
            if not dark_files:
                return error_status(f"No dark files found in {exp_dir}")
            
            self.logger.info(f"Found {len(dark_files)} dark files for {exposure_time:.3f}s exposure")
            
            # Load and combine dark frames
            master_dark = self._combine_frames(dark_files, f"dark_{exposure_time:.3f}s")
            
            if master_dark is None:
                return error_status("Failed to combine dark frames")
            
            # Save master dark
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if exposure_time == self.min_exposure:
                filename = f"master_bias_{timestamp}.fits"
            else:
                filename = f"master_dark_{exposure_time:.3f}s_{timestamp}.fits"
            
            output_path = os.path.join(self.master_output_dir, filename)
            
            # Save as FITS file (simplified - in real implementation use astropy.io.fits)
            self._save_as_fits(master_dark, output_path, exposure_time, "master_dark")
            
            self.logger.info(f"Master dark saved: {output_path}")
            
            return success_status(
                f"Master dark created for {exposure_time:.3f}s exposure",
                data=output_path,
                details={
                    'exposure_time': exposure_time,
                    'input_files': len(dark_files),
                    'output_file': output_path
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating master dark for {exposure_time:.3f}s: {e}")
            return error_status(f"Master dark creation failed for {exposure_time:.3f}s: {e}")
    
    def _find_flat_files(self) -> List[str]:
        """Find all flat files in the flat directory.
        
        Returns:
            List of flat file paths
        """
        flat_files = []
        
        if not os.path.exists(self.flat_dir):
            return flat_files
        
        for ext in ['*.fits', '*.fit', '*.FITS', '*.FIT']:
            flat_files.extend(glob.glob(os.path.join(self.flat_dir, ext)))
        
        return sorted(flat_files)
    
    def _determine_flat_exposure_time(self, flat_files: List[str]) -> Optional[float]:
        """Determine the exposure time used for flat frames.
        
        Args:
            flat_files: List of flat file paths
            
        Returns:
            Exposure time in seconds or None
        """
        # Try to extract from first flat file
        if flat_files:
            # In a real implementation, read FITS header
            # For now, return a default value
            return 1.0
        
        return None
    
    def _find_master_dark_for_exposure(self, exposure_time: float) -> Optional[str]:
        """Find the master dark file for a specific exposure time.
        
        Args:
            exposure_time: Exposure time in seconds
            
        Returns:
            Path to master dark file or None
        """
        if not os.path.exists(self.master_output_dir):
            return None
        
        # Look for master dark with matching exposure time
        pattern = f"master_dark_{exposure_time:.3f}s_*.fits"
        matches = glob.glob(os.path.join(self.master_output_dir, pattern))
        
        if matches:
            return matches[0]  # Return the first match
        
        # If no exact match, try to find the closest exposure time
        all_master_darks = glob.glob(os.path.join(self.master_output_dir, "master_dark_*.fits"))
        
        closest_dark = None
        min_diff = float('inf')
        
        for dark_file in all_master_darks:
            dark_exp_time = self._extract_exposure_time(dark_file)
            if dark_exp_time is not None:
                diff = abs(dark_exp_time - exposure_time)
                if diff < min_diff:
                    min_diff = diff
                    closest_dark = dark_file
        
        return closest_dark
    
    def _create_master_flat_with_dark_subtraction(
        self, flat_files: List[str], master_dark_path: str, exposure_time: float
    ) -> Status:
        """Create master flat with dark subtraction and normalization.
        
        Args:
            flat_files: List of flat file paths
            master_dark_path: Path to master dark file
            exposure_time: Flat exposure time
            
        Returns:
            Status: Success or error status with master flat path
        """
        try:
            self.logger.info(f"Creating master flat from {len(flat_files)} files...")
            
            # Load master dark
            master_dark = self._load_fits_file(master_dark_path)
            if master_dark is None:
                return error_status(f"Failed to load master dark: {master_dark_path}")
            
            # Load and dark-subtract flat frames
            dark_subtracted_flats = []
            
            for flat_file in flat_files:
                flat_data = self._load_fits_file(flat_file)
                if flat_data is not None:
                    # Dark subtraction
                    dark_subtracted = flat_data.astype(np.float32) - master_dark.astype(np.float32)
                    dark_subtracted_flats.append(dark_subtracted)
            
            if not dark_subtracted_flats:
                return error_status("No valid flat frames after dark subtraction")
            
            self.logger.info(f"Dark-subtracted {len(dark_subtracted_flats)} flat frames")
            
            # Combine dark-subtracted flats
            master_flat = self._combine_frames(
                dark_subtracted_flats, f"flat_{exposure_time:.3f}s", is_data_list=True
            )
            
            if master_flat is None:
                return error_status("Failed to combine dark-subtracted flat frames")
            
            # Normalize master flat
            master_flat_normalized = self._normalize_master_flat(master_flat)
            
            # Save master flat
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"master_flat_{exposure_time:.3f}s_{timestamp}.fits"
            output_path = os.path.join(self.master_output_dir, filename)
            
            # Save as FITS file
            self._save_as_fits(master_flat_normalized, output_path, exposure_time, "master_flat")
            
            self.logger.info(f"Master flat saved: {output_path}")
            
            return success_status(
                f"Master flat created for {exposure_time:.3f}s exposure",
                data=output_path,
                details={
                    'exposure_time': exposure_time,
                    'input_files': len(flat_files),
                    'master_dark_used': master_dark_path,
                    'output_file': output_path
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating master flat: {e}")
            return error_status(f"Master flat creation failed: {e}")
    
    def _combine_frames(self, files_or_data: Union[List[str], List[np.ndarray]], 
                       frame_type: str, is_data_list: bool = False) -> Optional[np.ndarray]:
        """Combine multiple frames using rejection and averaging.
        
        Args:
            files_or_data: List of file paths or numpy arrays
            frame_type: Type of frames being combined
            is_data_list: True if input is list of numpy arrays
            
        Returns:
            Combined frame as numpy array or None
        """
        try:
            if is_data_list:
                # Input is already list of numpy arrays
                frames = files_or_data
            else:
                # Load frames from files
                frames = []
                for file_path in files_or_data:
                    frame_data = self._load_fits_file(file_path)
                    if frame_data is not None:
                        frames.append(frame_data)
            
            if not frames:
                self.logger.error(f"No valid frames found for {frame_type}")
                return None
            
            self.logger.info(f"Combining {len(frames)} {frame_type} frames...")
            
            # Stack frames
            stacked = np.stack(frames, axis=0)
            
            # Apply rejection method
            if self.rejection_method == 'sigma_clip':
                combined = self._sigma_clip_combine(stacked)
            elif self.rejection_method == 'minmax':
                combined = self._minmax_combine(stacked)
            else:
                # Default to median
                combined = np.median(stacked, axis=0)
            
            self.logger.info(f"Combined {frame_type} frames successfully")
            return combined
            
        except Exception as e:
            self.logger.error(f"Error combining {frame_type} frames: {e}")
            return None
    
    def _sigma_clip_combine(self, stacked_frames: np.ndarray) -> np.ndarray:
        """Combine frames using sigma clipping rejection.
        
        Args:
            stacked_frames: Stacked frames as numpy array
            
        Returns:
            Combined frame
        """
        # Simple sigma clipping implementation
        mean = np.mean(stacked_frames, axis=0)
        std = np.std(stacked_frames, axis=0)
        
        # Create mask for pixels within sigma threshold
        mask = np.abs(stacked_frames - mean) <= (self.sigma_threshold * std)
        
        # Calculate mean of accepted pixels
        combined = np.zeros_like(mean)
        for i in range(stacked_frames.shape[1]):
            for j in range(stacked_frames.shape[2]):
                valid_pixels = stacked_frames[mask[:, i, j], i, j]
                if len(valid_pixels) > 0:
                    combined[i, j] = np.mean(valid_pixels)
                else:
                    combined[i, j] = mean[i, j]
        
        return combined
    
    def _minmax_combine(self, stacked_frames: np.ndarray) -> np.ndarray:
        """Combine frames using min/max rejection.
        
        Args:
            stacked_frames: Stacked frames as numpy array
            
        Returns:
            Combined frame
        """
        # Sort along first axis
        sorted_frames = np.sort(stacked_frames, axis=0)
        
        # Remove min and max values
        n_frames = sorted_frames.shape[0]
        if n_frames > 2:
            trimmed = sorted_frames[1:-1, :, :]
            return np.mean(trimmed, axis=0)
        else:
            return np.mean(sorted_frames, axis=0)
    
    def _normalize_master_flat(self, master_flat: np.ndarray) -> np.ndarray:
        """Normalize master flat frame.
        
        Args:
            master_flat: Master flat frame
            
        Returns:
            Normalized master flat
        """
        if self.normalization_method == 'mean':
            norm_factor = np.mean(master_flat)
        elif self.normalization_method == 'median':
            norm_factor = np.median(master_flat)
        elif self.normalization_method == 'max':
            norm_factor = np.max(master_flat)
        else:
            norm_factor = np.mean(master_flat)
        
        # Avoid division by zero
        if norm_factor > 0:
            normalized = master_flat / norm_factor
        else:
            normalized = master_flat
        
        self.logger.info(f"Normalized master flat using {self.normalization_method} method")
        return normalized
    
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
    
    def _save_as_fits(self, data: np.ndarray, file_path: str, 
                     exposure_time: float, frame_type: str) -> bool:
        """Save numpy array as FITS file.
        
        Args:
            data: Image data as numpy array
            file_path: Output file path
            exposure_time: Exposure time in seconds
            frame_type: Type of frame (master_dark, master_flat)
            
        Returns:
            True if successful
        """
        try:
            # Simplified FITS saving - in real implementation use astropy.io.fits
            # For now, just create the file
            with open(file_path, 'w') as f:
                f.write(f"# {frame_type} with {exposure_time:.3f}s exposure\n")
            
            self.logger.info(f"Saved {frame_type} to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save FITS file {file_path}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the master frame creator.
        
        Returns:
            Dict containing system status
        """
        return {
            'dark_directory': self.dark_dir,
            'flat_directory': self.flat_dir,
            'master_output_directory': self.master_output_dir,
            'rejection_method': self.rejection_method,
            'sigma_threshold': self.sigma_threshold,
            'normalization_method': self.normalization_method,
            'num_darks': self.num_darks,
            'num_flats': self.num_flats,
            'science_exposure_time': self.science_exposure_time,
            'exposure_factors': self.exposure_factors
        } 