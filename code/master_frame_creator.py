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

from status import Status, success_status, error_status, warning_status
from exceptions import MasterFrameError


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
        
        # Load configurations
        dark_config = self.config.get_dark_config()
        flat_config = self.config.get_flat_config()
        
        # Dark capture settings
        # Resolve darks directory (support legacy key)
        self.dark_dir = (
            dark_config.get('output_dir')
            or dark_config.get('output_directory')
            or 'darks'
        )
        self.num_darks = dark_config.get('num_darks', 40)
        self.science_exposure_time = dark_config.get('science_exposure_time', 5.0)
        self.min_exposure = dark_config.get('min_exposure', 0.001)
        self.exposure_factors = dark_config.get('exposure_factors', [0.5, 1.0, 2.0, 4.0])
        
        # Flat capture settings
        # Resolve flats directory (support legacy key)
        self.flat_dir = (
            flat_config.get('output_dir')
            or flat_config.get('output_directory')
            or 'flats'
        )
        self.num_flats = flat_config.get('num_flats', 40)
        
        # Master frame settings
        master_config = self.config.get_master_config()
        # Resolve master output directory (support legacy key)
        self.master_output_dir = (
            master_config.get('output_dir')
            or master_config.get('output_directory')
            or 'master_frames'
        )
        self.rejection_method = master_config.get('rejection_method', 'sigma_clip')  # 'sigma_clip' or 'minmax'
        self.sigma_threshold = master_config.get('sigma_threshold', 3.0)
        self.normalization_method = master_config.get('normalization_method', 'mean')  # 'mean', 'median', 'max'
        
        # Ensure output directory exists
        os.makedirs(self.master_output_dir, exist_ok=True)
        
    def _create_output_directories(self):
        """Create necessary output directories."""
        try:
            # Only ensure the master output directory exists; no unused subfolders
            output_dir = Path(self.master_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Master frames directory ready: {output_dir}")
        except Exception as e:
            self.logger.warning(f"Failed to create master output directory: {e}")
    
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
            
            # Determine flat exposure time from FITS headers
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
            # Find all dark/bias files in the directory (case-insensitive, de-duplicated)
            dark_files = self._list_fits_files(exp_dir)
            
            if not dark_files:
                return error_status(f"No dark files found in {exp_dir}")
            
            self.logger.info(f"Found {len(dark_files)} dark files for {exposure_time:.3f}s exposure")
            
            # Load and combine dark frames (streaming to avoid high memory usage)
            master_dark = self._combine_frames_streaming_files(
                dark_files,
                frame_type=f"dark_{exposure_time:.3f}s",
                rejection_method=self.rejection_method,
                sigma_threshold=self.sigma_threshold
            )
            
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
        if not os.path.exists(self.flat_dir):
            return []

        return self._list_fits_files(self.flat_dir)

    def _list_fits_files(self, directory: str) -> List[str]:
        """List FITS files in a directory (case-insensitive, unique).

        Args:
            directory: Directory to scan

        Returns:
            Sorted list of unique file paths
        """
        try:
            if not os.path.isdir(directory):
                return []

            # Accept both .fits and .fit, case-insensitive
            valid_exts = {'.fits', '.fit'}
            seen = set()
            files: List[str] = []

            for entry in os.scandir(directory):
                if not entry.is_file():
                    continue
                _, ext = os.path.splitext(entry.name)
                if ext.lower() in valid_exts:
                    # Normalize path for uniqueness (lowercase on Windows)
                    norm = os.path.normcase(os.path.abspath(entry.path))
                    if norm not in seen:
                        seen.add(norm)
                        files.append(entry.path)

            return sorted(files)
        except Exception as e:
            self.logger.warning(f"Failed to list FITS files in {directory}: {e}")
            return []
    
    def _determine_flat_exposure_time(self, flat_files: List[str]) -> Optional[float]:
        """Determine the exposure time used for flat frames.
        
        Args:
            flat_files: List of flat file paths
            
        Returns:
            Exposure time in seconds or None
        """
        # Read EXPTIME from the first few flat files using astropy
        try:
            import astropy.io.fits as fits
        except Exception as e:
            self.logger.warning(f"Astropy not available to read flat EXPTIME: {e}")
            return None

        for file_path in flat_files[:5]:
            try:
                with fits.open(file_path) as hdul:
                    header = hdul[0].header
                    exp = header.get('EXPTIME')
                    if exp is not None:
                        try:
                            exp_val = float(exp)
                            self.logger.info(f"Detected flat exposure from header {os.path.basename(file_path)}: {exp_val:.3f}s")
                            return exp_val
                        except Exception:
                            continue
            except Exception as e:
                self.logger.debug(f"Failed to read EXPTIME from {file_path}: {e}")
        
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
            
            # Combine dark-subtracted flats via streaming (apply subtraction on the fly)
            master_flat = self._combine_flats_with_dark_streaming(
                flat_files,
                master_dark,
                frame_type=f"flat_{exposure_time:.3f}s",
                rejection_method=self.rejection_method,
                sigma_threshold=self.sigma_threshold
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
    
    def _combine_frames_streaming_files(
        self,
        files: List[str],
        frame_type: str,
        rejection_method: str,
        sigma_threshold: float
    ) -> Optional[np.ndarray]:
        """Combine frames from file paths using streaming to reduce memory.

        Supports 'sigma_clip' (two-pass Welford) and 'minmax' (two-pass exclude one
        min and one max per pixel). Falls back to simple mean if frames < 3 or
        unknown method.
        """
        try:
            if not files:
                self.logger.error(f"No valid frames found for {frame_type}")
                return None
            
            # Peek first file for shape
            first = self._load_fits_file(files[0])
            if first is None:
                return None
            shape = first.shape

            if rejection_method == 'sigma_clip':
                return self._sigma_clip_combine_files(files, sigma_threshold, shape)
            elif rejection_method == 'minmax':
                return self._minmax_combine_files(files, shape)
            else:
                # Simple mean (one pass)
                self.logger.info(f"Combining {len(files)} {frame_type} frames with simple mean")
                sum_img = np.zeros(shape, dtype=np.float64)
                count = 0
                for fp in files:
                    arr = self._load_fits_file(fp)
                    if arr is None:
                        continue
                    sum_img += arr
                    count += 1
                if count == 0:
                    return None
                return (sum_img / float(count)).astype(np.float32)
        except Exception as e:
            self.logger.error(f"Error combining {frame_type} frames: {e}")
            return None
    
    def _sigma_clip_combine_files(self, files: List[str], sigma: float, shape: Tuple[int, int]) -> Optional[np.ndarray]:
        """Two-pass sigma clipping combine from files using Welford streaming."""
        try:
            self.logger.info(f"Sigma-clip combining {len(files)} frames (sigma={sigma})")
            # First pass: mean and variance (Welford)
            n = 0
            mean = np.zeros(shape, dtype=np.float64)
            M2 = np.zeros(shape, dtype=np.float64)
            for fp in files:
                arr = self._load_fits_file(fp)
                if arr is None:
                    continue
                n += 1
                delta = arr - mean
                mean += delta / n
                delta2 = arr - mean
                M2 += delta * delta2
            if n == 0:
                return None
            std = np.sqrt(np.maximum(M2 / max(n - 1, 1), 0.0))

            # Second pass: accumulate within clip
            sum_img = np.zeros(shape, dtype=np.float64)
            count_img = np.zeros(shape, dtype=np.uint32)
            threshold = sigma * std
            for fp in files:
                arr = self._load_fits_file(fp)
                if arr is None:
                    continue
                mask = np.less_equal(np.abs(arr - mean), threshold)
                sum_img += np.where(mask, arr, 0.0)
                count_img += mask.astype(np.uint32)
            count_nonzero = np.maximum(count_img, 1)
            combined = (sum_img / count_nonzero.astype(np.float64)).astype(np.float32)
        return combined
        except Exception as e:
            self.logger.error(f"Sigma-clip combine failed: {e}")
            return None
    
    def _minmax_combine_files(self, files: List[str], shape: Tuple[int, int]) -> Optional[np.ndarray]:
        """Two-pass min/max rejection combine from files (exclude one min and one max per pixel)."""
        try:
            self.logger.info(f"MinMax combining {len(files)} frames")
            # First pass: per-pixel min and max
            min_img = np.full(shape, np.inf, dtype=np.float32)
            max_img = np.full(shape, -np.inf, dtype=np.float32)
            n = 0
            for fp in files:
                arr = self._load_fits_file(fp)
                if arr is None:
                    continue
                n += 1
                np.minimum(min_img, arr, out=min_img)
                np.maximum(max_img, arr, out=max_img)
            if n == 0:
                return None
            if n <= 2:
                # Not enough frames to reject extremes; simple mean
                sum_img = np.zeros(shape, dtype=np.float64)
                cnt = 0
                for fp in files:
                    arr = self._load_fits_file(fp)
                    if arr is None:
                        continue
                    sum_img += arr
                    cnt += 1
                if cnt == 0:
                    return None
                return (sum_img / float(cnt)).astype(np.float32)

            # Second pass: accumulate excluding exactly one min and one max per pixel
            sum_img = np.zeros(shape, dtype=np.float64)
            count_img = np.zeros(shape, dtype=np.uint32)
            min_used = np.zeros(shape, dtype=bool)
            max_used = np.zeros(shape, dtype=bool)
            for fp in files:
                arr = self._load_fits_file(fp)
                if arr is None:
                    continue
                is_min = (arr == min_img) & (~min_used)
                is_max = (arr == max_img) & (~max_used)
                include = ~(is_min | is_max)
                sum_img += np.where(include, arr, 0.0)
                count_img += include.astype(np.uint32)
                # Mark min/max used only where they occurred
                min_used |= is_min
                max_used |= is_max
            # Avoid division by zero
            count_nonzero = np.maximum(count_img, 1)
            combined = (sum_img / count_nonzero.astype(np.float64)).astype(np.float32)
            return combined
        except Exception as e:
            self.logger.error(f"MinMax combine failed: {e}")
            return None

    def _combine_flats_with_dark_streaming(
        self,
        flat_files: List[str],
        master_dark: np.ndarray,
        frame_type: str,
        rejection_method: str,
        sigma_threshold: float
    ) -> Optional[np.ndarray]:
        """Streaming combine for flats with on-the-fly dark subtraction."""
        try:
            if not flat_files:
                return None
            shape = master_dark.shape
            if rejection_method == 'sigma_clip':
                # First pass Welford on (flat - dark)
                n = 0
                mean = np.zeros(shape, dtype=np.float64)
                M2 = np.zeros(shape, dtype=np.float64)
                for fp in flat_files:
                    flat = self._load_fits_file(fp)
                    if flat is None:
                        continue
                    arr = flat - master_dark
                    n += 1
                    delta = arr - mean
                    mean += delta / n
                    delta2 = arr - mean
                    M2 += delta * delta2
                if n == 0:
                    return None
                std = np.sqrt(np.maximum(M2 / max(n - 1, 1), 0.0))

                # Second pass accumulate
                sum_img = np.zeros(shape, dtype=np.float64)
                count_img = np.zeros(shape, dtype=np.uint32)
                threshold = sigma_threshold * std
                for fp in flat_files:
                    flat = self._load_fits_file(fp)
                    if flat is None:
                        continue
                    arr = flat - master_dark
                    mask = np.less_equal(np.abs(arr - mean), threshold)
                    sum_img += np.where(mask, arr, 0.0)
                    count_img += mask.astype(np.uint32)
                count_nonzero = np.maximum(count_img, 1)
                return (sum_img / count_nonzero.astype(np.float64)).astype(np.float32)
            elif rejection_method == 'minmax':
                # First pass min/max
                min_img = np.full(shape, np.inf, dtype=np.float32)
                max_img = np.full(shape, -np.inf, dtype=np.float32)
                n = 0
                for fp in flat_files:
                    flat = self._load_fits_file(fp)
                    if flat is None:
                        continue
                    arr = flat - master_dark
                    n += 1
                    np.minimum(min_img, arr, out=min_img)
                    np.maximum(max_img, arr, out=max_img)
                if n == 0:
                    return None
                if n <= 2:
                    sum_img = np.zeros(shape, dtype=np.float64)
                    cnt = 0
                    for fp in flat_files:
                        flat = self._load_fits_file(fp)
                        if flat is None:
                            continue
                        arr = flat - master_dark
                        sum_img += arr
                        cnt += 1
                    if cnt == 0:
                        return None
                    return (sum_img / float(cnt)).astype(np.float32)

                sum_img = np.zeros(shape, dtype=np.float64)
                count_img = np.zeros(shape, dtype=np.uint32)
                min_used = np.zeros(shape, dtype=bool)
                max_used = np.zeros(shape, dtype=bool)
                for fp in flat_files:
                    flat = self._load_fits_file(fp)
                    if flat is None:
                        continue
                    arr = flat - master_dark
                    is_min = (arr == min_img) & (~min_used)
                    is_max = (arr == max_img) & (~max_used)
                    include = ~(is_min | is_max)
                    sum_img += np.where(include, arr, 0.0)
                    count_img += include.astype(np.uint32)
                    min_used |= is_min
                    max_used |= is_max
                count_nonzero = np.maximum(count_img, 1)
                return (sum_img / count_nonzero.astype(np.float64)).astype(np.float32)
        else:
                # Simple mean
                sum_img = np.zeros(shape, dtype=np.float64)
                cnt = 0
                for fp in flat_files:
                    flat = self._load_fits_file(fp)
                    if flat is None:
                        continue
                    sum_img += (flat - master_dark)
                    cnt += 1
                if cnt == 0:
                    return None
                return (sum_img / float(cnt)).astype(np.float32)
        except Exception as e:
            self.logger.error(f"Combine flats with dark (streaming) failed: {e}")
            return None
    
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
            import astropy.io.fits as fits
            with fits.open(file_path) as hdul:
                data = hdul[0].data
                if data is None:
                    return None
                # Ensure float32 for processing
                return data.astype(np.float32, copy=False)
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
            import astropy.io.fits as fits
            # Convert to 32-bit float if not already
            data_to_save = data.astype(np.float32, copy=False)
            header = fits.Header()
            header['EXPTIME'] = float(exposure_time)
            header['FRAMETYP'] = frame_type
            hdu = fits.PrimaryHDU(data_to_save, header=header)
            hdu.writeto(file_path, overwrite=True)
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