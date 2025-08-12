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

from status import Status, success_status, error_status, warning_status
from exceptions import CalibrationError


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
        from config_manager import ConfigManager
        
        # Only create default config if no config is provided
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
            
        self.config = config or default_config
        self.logger = logger or logging.getLogger(__name__)
        
        # Load configurations with fallback when config lacks get_master_config
        try:
            master_config = self.config.get_master_config()
        except Exception:
            master_config = {
                'output_dir': 'master_frames',
                'enable_calibration': True,
                'auto_load_masters': True,
                'calibration_tolerance': 0.1,
            }
        self.master_dir = master_config.get('output_dir', 'master_frames')
        
        # Cache for loaded master frames
        self.master_bias_cache = None
        self.master_dark_cache = {}
        self.master_flat_cache = None
        
        # Calibration settings
        self.enable_calibration = master_config.get('enable_calibration', True)
        self.auto_load_masters = master_config.get('auto_load_masters', True)
        self.calibration_tolerance = master_config.get('calibration_tolerance', 0.1)  # 10% tolerance
        
        # Initialize master frames if auto-load is enabled
        if self.auto_load_masters:
            self._load_master_frames()
    
    def _load_master_frames(self) -> None:
        """Load master frames from the master frames directory."""
        try:
            try:
                master_config = self.config.get_master_config()
            except Exception:
                master_config = {'output_dir': 'master_frames'}
            master_dir = Path(master_config.get('output_dir', 'master_frames'))
            
            # Create master frames directory if it doesn't exist
            if not master_dir.exists():
                self.logger.info(f"Creating master frames directory: {master_dir}")
                master_dir.mkdir(parents=True, exist_ok=True)
            
            if not master_dir.exists():
                self.logger.warning(f"Master frames directory does not exist: {master_dir}")
                return
            
            self.logger.info(f"Loading master frames from: {master_dir}")
            
            # Load master bias (support timestamped filenames)
            bias_path = master_dir / master_config.get('master_bias_filename', 'master_bias.fits')
            if not bias_path.exists():
                # Fallback: pick latest timestamped file
                candidates = sorted(master_dir.glob('master_bias_*.fits'), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    bias_path = candidates[0]
            if bias_path.exists():
                self.master_bias_cache = {
                    'data': self._load_fits_file(bias_path),
                    'file': str(bias_path),
                    'gain': self._extract_camera_setting(bias_path, 'GAIN'),
                    'offset': self._extract_camera_setting(bias_path, 'OFFSET'),
                    'readout_mode': self._extract_camera_setting(bias_path, 'READOUT')
                }
                self.logger.info(f"Loaded master bias: {bias_path}")
            else:
                self.logger.info(f"Master bias not found: {bias_path}")
            
            # Load master darks (by exposure time) from root dir (and legacy 'darks' subdir)
            self.master_dark_cache = {}
            dark_sources = [master_dir]
            legacy_dark_dir = master_dir / 'darks'
            if legacy_dark_dir.exists():
                dark_sources.append(legacy_dark_dir)
            for source_dir in dark_sources:
                for dark_file in source_dir.glob('master_dark_*.fits'):
                    try:
                        # Extract exposure time from filename like master_dark_1.000s_YYYYMMDD_*.fits
                        filename = dark_file.stem
                        import re
                        m = re.match(r'^master_dark_(\d+(?:\.\d+)?)s(?:_.*)?$', filename)
                        if m:
                            exposure_time = float(m.group(1))
                            self.master_dark_cache[exposure_time] = {
                                'data': self._load_fits_file(dark_file),
                                'file': str(dark_file),
                                'exposure_time': exposure_time,
                                'gain': self._extract_camera_setting(dark_file, 'GAIN'),
                                'offset': self._extract_camera_setting(dark_file, 'OFFSET'),
                                'readout_mode': self._extract_camera_setting(dark_file, 'READOUT')
                            }
                            self.logger.info(f"Loaded master dark for {exposure_time}s: {dark_file}")
                        else:
                            self.logger.warning(f"Unexpected master dark filename format: {dark_file.name}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load master dark {dark_file}: {e}")
            
            # Load master flat (support timestamped filenames)
            flat_path = master_dir / master_config.get('master_flat_filename', 'master_flat.fits')
            if not flat_path.exists():
                candidates = sorted(master_dir.glob('master_flat_*.fits'), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    flat_path = candidates[0]
            if flat_path.exists():
                self.master_flat_cache = {
                    'data': self._load_fits_file(flat_path),
                    'file': str(flat_path),
                    'gain': self._extract_camera_setting(flat_path, 'GAIN'),
                    'offset': self._extract_camera_setting(flat_path, 'OFFSET'),
                    'readout_mode': self._extract_camera_setting(flat_path, 'READOUT')
                }
                self.logger.info(f"Loaded master flat: {flat_path}")
            else:
                self.logger.info(f"Master flat not found: {flat_path}")
                
            total_masters = (1 if self.master_bias_cache else 0) + \
                          len(self.master_dark_cache) + \
                          (1 if self.master_flat_cache else 0)
            
            self.logger.info(f"Loaded {total_masters} master frames total")
            
        except Exception as e:
            self.logger.error(f"Error loading master frames: {e}")
            raise CalibrationError(f"Error loading master frames: {e}")

    def _extract_camera_setting(self, fits_file: Path, keyword: str) -> Optional[Union[float, int]]:
        """Extract camera setting from FITS header.
        
        Args:
            fits_file: Path to FITS file
            keyword: Header keyword to extract
            
        Returns:
            Extracted value or None if not found
        """
        try:
            import astropy.io.fits as fits
            with fits.open(fits_file) as hdul:
                header = hdul[0].header
                if keyword in header:
                    value = header[keyword]
                    # Convert to appropriate type
                    if isinstance(value, (int, float)):
                        return value
                    elif isinstance(value, str):
                        try:
                            return float(value)
                        except ValueError:
                            return None
                    return None
                return None
        except Exception as e:
            self.logger.debug(f"Could not extract {keyword} from {fits_file.name}: {e}")
            return None
    
    def _find_best_master_dark(self, exposure_time: Optional[float], gain: Optional[float] = None, 
                              offset: Optional[int] = None, readout_mode: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Find the best matching master dark for the given exposure time and camera settings.
        
        Args:
            exposure_time: Frame exposure time in seconds
            gain: Camera gain setting (optional)
            offset: Camera offset setting (optional)
            readout_mode: Camera readout mode (optional)
            
        Returns:
            Dict with master dark data or None if no match found
        """
        # Guard against missing exposure time
        try:
            if exposure_time is not None:
                exposure_time = float(exposure_time)
        except Exception:
            exposure_time = None

        if exposure_time is None or not self.master_dark_cache:
            return None
        
        best_match = None
        best_score = float('inf')
        # Track nearest by exposure as fallback if none within tolerance
        nearest_dark = None
        nearest_exp_diff = float('inf')
        
        for dark_info in self.master_dark_cache.values():
            # Check exposure time match
            try:
                exp_diff = abs(float(dark_info['exposure_time']) - float(exposure_time))
            except Exception:
                # If exposure time cannot be compared, skip this dark
                continue

            # Track nearest by exposure regardless of full score
            if exp_diff < nearest_exp_diff:
                nearest_exp_diff = exp_diff
                nearest_dark = dark_info
            
            # Check gain match (if both have gain info)
            gain_diff = 0
            if gain is not None:
                dark_gain = dark_info.get('gain')
                if dark_gain is not None:
                    try:
                        gain_diff = abs(float(dark_gain) - float(gain))
                    except Exception:
                        gain_diff = 1000
                else:
                    # If dark doesn't have gain info, use a high penalty
                    gain_diff = 1000
            
            # Check offset match (if both have offset info)
            offset_diff = 0
            if offset is not None:
                dark_offset = dark_info.get('offset')
                if dark_offset is not None:
                    try:
                        offset_diff = abs(float(dark_offset) - float(offset))
                    except Exception:
                        offset_diff = 1000
                else:
                    # If dark doesn't have offset info, use a high penalty
                    offset_diff = 1000
            
            # Check readout mode match (if both have readout mode info)
            readout_diff = 0
            if readout_mode is not None:
                dark_readout = dark_info.get('readout_mode')
                if dark_readout is not None:
                    try:
                        readout_diff = abs(float(dark_readout) - float(readout_mode))
                    except Exception:
                        readout_diff = 1000
                else:
                    # If dark doesn't have readout mode info, use a high penalty
                    readout_diff = 1000
            
            # Calculate weighted score (exposure time is most important)
            score = (exp_diff * 10.0 +  # Exposure time weight: 10
                    gain_diff * 1.0 +   # Gain weight: 1
                    offset_diff * 1.0 + # Offset weight: 1
                    readout_diff * 1.0) # Readout mode weight: 1
            
            # Check if within tolerance
            tolerance = self.calibration_tolerance
            exp_within_tolerance = exp_diff <= tolerance
            
            if exp_within_tolerance and score < best_score:
                best_match = dark_info
                best_score = score
        
        if best_match:
            self.logger.debug(f"Found master dark: {best_match['file']} "
                            f"(exp: {best_match['exposure_time']:.3f}s, "
                            f"gain: {best_match.get('gain', 'N/A')}, "
                            f"offset: {best_match.get('offset', 'N/A')}, "
                            f"readout: {best_match.get('readout_mode', 'N/A')})")
            return best_match
        
        # Fallback: use nearest by exposure time if nothing within tolerance
        if nearest_dark is not None:
            self.logger.warning(
                f"No master dark within tolerance for exp={exposure_time:.3f}s; "
                f"using nearest exposure {nearest_dark['exposure_time']:.3f}s (Δ={nearest_exp_diff:.3f}s)"
            )
            return nearest_dark
        
        self.logger.warning(f"No suitable master dark found for exp={exposure_time}, gain={gain}, offset={offset}, readout={readout_mode}")
        return None

    def _find_best_master_flat(self, gain: Optional[float] = None, offset: Optional[int] = None, 
                              readout_mode: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Find the best matching master flat for the given camera settings.
        
        Args:
            gain: Camera gain setting (optional)
            offset: Camera offset setting (optional)
            readout_mode: Camera readout mode (optional)
            
        Returns:
            Dict with master flat data or None if no match found
        """
        if not self.master_flat_cache:
            return None
        
        flat_info = self.master_flat_cache
        
        # Check if flat has matching settings (robust to None/strings)
        gain_match = True
        if gain is not None:
            flat_gain = flat_info.get('gain')
            if flat_gain is not None:
                try:
                    gain_diff = abs(float(flat_gain) - float(gain))
                    gain_match = gain_diff <= self.calibration_tolerance
                except Exception:
                    gain_match = False
            else:
                gain_match = False
        
        offset_match = True
        if offset is not None:
            flat_offset = flat_info.get('offset')
            if flat_offset is not None:
                try:
                    offset_diff = abs(float(flat_offset) - float(offset))
                    offset_match = offset_diff <= self.calibration_tolerance
                except Exception:
                    offset_match = False
            else:
                offset_match = False
        
        readout_match = True
        if readout_mode is not None:
            flat_readout = flat_info.get('readout_mode')
            if flat_readout is not None:
                try:
                    readout_diff = abs(float(flat_readout) - float(readout_mode))
                    readout_match = readout_diff <= self.calibration_tolerance
                except Exception:
                    readout_match = False
            else:
                readout_match = False
        
        if gain_match and offset_match and readout_match:
            self.logger.debug(f"Using master flat: {flat_info['file']} "
                            f"(gain: {flat_info.get('gain', 'N/A')}, "
                            f"offset: {flat_info.get('offset', 'N/A')}, "
                            f"readout: {flat_info.get('readout_mode', 'N/A')})")
            return flat_info
        else:
            self.logger.warning(f"Master flat settings don't match: "
                              f"flat(gain={flat_info.get('gain', 'N/A')}, "
                              f"offset={flat_info.get('offset', 'N/A')}, "
                              f"readout={flat_info.get('readout_mode', 'N/A')}) vs "
                              f"frame(gain={gain}, offset={offset}, readout={readout_mode})")
            return None
    
    def calibrate_frame(
        self,
        frame_data: np.ndarray,
        exposure_time: Optional[float] = None,
        frame_info: Optional[Dict[str, Any]] = None,
        *,
        exposure_time_s: Optional[float] = None,
        frame_details: Optional[Dict[str, Any]] = None,
    ) -> Status:
        """Apply dark and flat calibration to a frame.
        
        Args:
            frame_data: Raw frame data as numpy array
            exposure_time: Frame exposure time in seconds
            frame_info: Additional frame information including gain, offset, readout_mode (optional)
            
        Returns:
            Status: Success or error status with calibrated frame data
        """
        try:
            # Backward-compat: allow exposure_time_s/frame_details keyword names
            if exposure_time is None and exposure_time_s is not None:
                exposure_time = exposure_time_s
            if frame_info is None and frame_details is not None:
                frame_info = frame_details
            if not self.enable_calibration:
                self.logger.debug("Calibration disabled, returning original frame")
                return success_status(
                    "Calibration disabled",
                    data=frame_data,
                    details={'calibration_applied': False}
                )
            
            if not self.master_dark_cache and not self.master_flat_cache:
                # For robustness (and tests), return original frame as success when no masters exist
                self.logger.warning("No master frames available for calibration")
                return success_status(
                    "No master frames available",
                    data=frame_data,
                    details={'calibration_applied': False, 'reason': 'no_master_frames'}
                )
            
            # Extract camera settings from frame_info
            gain = None
            offset = None
            readout_mode = None
            
            if frame_info:
                gain = frame_info.get('gain')
                offset = frame_info.get('offset')
                readout_mode = frame_info.get('readout_mode')
            
            self.logger.debug(f"Calibrating frame with exp={exposure_time}, gain={gain}, offset={offset}, readout={readout_mode}")
            self.logger.debug(f"Incoming frame_data type: {type(frame_data)}")
            
            # Unwrap Status objects or nested data
            raw = frame_data
            for _ in range(5):
                if raw is None:
                    break
                if isinstance(raw, np.ndarray):
                    break
                if hasattr(raw, 'data'):
                    raw = raw.data
                    continue
                if isinstance(raw, list):
                    raw = np.array(raw)
                break

            if raw is None:
                return error_status("No frame data provided for calibration")

            # Start with original frame as float32
            # Ensure numeric ndarray for calibrated_frame
            try:
                calibrated_frame = np.asarray(raw, dtype=np.float32)
            except Exception as conv_err:
                self.logger.warning(f"Could not convert frame to float32 array: {conv_err}")
                return warning_status(
                    "No calibration applied (invalid frame data)",
                    data=raw if isinstance(raw, np.ndarray) else None,
                    details={'calibration_applied': False, 'reason': 'invalid_frame_dtype'}
                )
            # Standardize orientation to long-side horizontal BEFORE calibration
            try:
                oriented = False
                if calibrated_frame.ndim == 2:
                    h, w = calibrated_frame.shape
                    if h > w:
                        calibrated_frame = calibrated_frame.T
                        oriented = True
                elif calibrated_frame.ndim == 3:
                    h, w = calibrated_frame.shape[:2]
                    if h > w:
                        calibrated_frame = np.transpose(calibrated_frame, (1, 0, 2))
                        oriented = True
                if oriented:
                    self.logger.debug("Standardized frame orientation to long-side horizontal before calibration")
            except Exception as e_orient:
                self.logger.debug(f"Orientation standardization skipped: {e_orient}")
            try:
                self.logger.debug(
                    f"Frame array ok: shape={calibrated_frame.shape}, dtype={calibrated_frame.dtype}, "
                    f"min={float(np.nanmin(calibrated_frame)) if calibrated_frame.size else 'n/a'}, "
                    f"max={float(np.nanmax(calibrated_frame)) if calibrated_frame.size else 'n/a'}"
                )
            except Exception:
                pass
            calibration_details = {
                'original_exposure_time': exposure_time,
                'original_gain': gain,
                'original_offset': offset,
                'original_readout_mode': readout_mode,
                'dark_subtraction_applied': False,
                'flat_correction_applied': False,
                'master_dark_used': None,
                'master_flat_used': None,
                'master_dark_settings': None,
                'master_flat_settings': None
            }
            
            # Apply dark subtraction with matching settings
            master_dark = self._find_best_master_dark(exposure_time, gain, offset, readout_mode)
            if master_dark:
                dark_data = master_dark.get('data')
                if dark_data is None:
                    self.logger.warning(f"Selected master dark has no data: {master_dark.get('file')}")
                else:
                    try:
                        dark_arr = np.asarray(dark_data, dtype=np.float32)
                    except Exception as conv_err:
                        self.logger.warning(f"Could not convert master dark to float32 array: {conv_err}")
                        dark_arr = None
                    if dark_arr is not None:
                        self.logger.debug(
                            f"Master dark selected: file={master_dark.get('file')}, exp={master_dark.get('exposure_time')}, "
                            f"shape={getattr(dark_arr, 'shape', None)}, dtype={getattr(dark_arr, 'dtype', None)}"
                        )
                        # Try to resolve residual orientation mismatch in 2D case
                        applied_dark = False
                        if dark_arr.shape != calibrated_frame.shape:
                            if dark_arr.ndim == 2 and calibrated_frame.ndim == 2:
                                if dark_arr.T.shape == calibrated_frame.shape:
                                    self.logger.debug("Transposing master dark to match frame orientation (2D)")
                                    dark_arr = dark_arr.T
                                elif calibrated_frame.T.shape == dark_arr.shape:
                                    self.logger.debug("Transposing frame to match master dark orientation (2D)")
                                    calibrated_frame = calibrated_frame.T
                        if dark_arr.shape == calibrated_frame.shape:
                            calibrated_frame = calibrated_frame - dark_arr
                            applied_dark = True
                            # Debug: summarize frame after dark subtraction
                            try:
                                self.logger.debug(
                                    f"After dark subtraction: shape={calibrated_frame.shape}, dtype={calibrated_frame.dtype}, "
                                    f"min={float(np.nanmin(calibrated_frame)) if calibrated_frame.size else 'n/a'}, "
                                    f"max={float(np.nanmax(calibrated_frame)) if calibrated_frame.size else 'n/a'}"
                                )
                            except Exception:
                                pass
                        else:
                            self.logger.warning(
                                f"Master dark shape {dark_arr.shape} != frame shape {calibrated_frame.shape}; skipping dark subtraction"
                            )
                calibration_details['dark_subtraction_applied'] = bool('applied_dark' in locals() and applied_dark)
                calibration_details['master_dark_used'] = master_dark['file']
                calibration_details['master_dark_settings'] = {
                    'exposure_time': master_dark['exposure_time'],
                    'gain': master_dark.get('gain'),
                    'offset': master_dark.get('offset'),
                    'readout_mode': master_dark.get('readout_mode')
                }
                if calibration_details['dark_subtraction_applied']:
                    self.logger.debug(
                        f"Applied dark subtraction using {master_dark['file']} "
                        f"(exp: {master_dark['exposure_time']:.3f}s, "
                        f"gain: {master_dark.get('gain', 'N/A')}, "
                        f"offset: {master_dark.get('offset', 'N/A')}, "
                        f"readout: {master_dark.get('readout_mode', 'N/A')})"
                    )
            else:
                self.logger.warning(f"No suitable master dark found for exp={exposure_time:.3f}s, "
                                  f"gain={gain}, offset={offset}, readout={readout_mode}")
            
            # Validate calibrated_frame before flat correction
            if not isinstance(calibrated_frame, np.ndarray):
                self.logger.error(f"Calibrated frame has invalid type before flat correction: {type(calibrated_frame)}")
                try:
                    calibrated_frame = np.asarray(calibrated_frame, dtype=np.float32)
                    self.logger.debug(f"Recovered calibrated frame to ndarray: shape={calibrated_frame.shape}, dtype={calibrated_frame.dtype}")
                except Exception as conv_err:
                    self.logger.error(f"Failed to recover calibrated frame to ndarray: {conv_err}")
                    return error_status("Calibration failed: invalid frame after dark subtraction")

            try:
                self.logger.debug(
                    f"Pre-flat: frame shape={calibrated_frame.shape}, dtype={calibrated_frame.dtype}, "
                    f"min={float(np.nanmin(calibrated_frame)) if calibrated_frame.size else 'n/a'}, "
                    f"max={float(np.nanmax(calibrated_frame)) if calibrated_frame.size else 'n/a'}"
                )
            except Exception:
                pass

            # Apply flat correction with matching settings
            master_flat = self._find_best_master_flat(gain, offset, readout_mode)
            if master_flat:
                # Avoid division by zero
                flat_data = master_flat['data']
                try:
                    flat_data = np.asarray(flat_data, dtype=np.float32)
                except Exception as conv_err:
                    self.logger.warning(f"Could not convert master flat to float32 array: {conv_err}")
                    flat_data = None
                if flat_data is None:
                    self.logger.warning(f"Selected master flat has no data: {master_flat.get('file')}")
                    flat_data_safe = None
                else:
                    self.logger.debug(
                        f"Master flat selected: file={master_flat.get('file')}, shape={flat_data.shape}, dtype={flat_data.dtype}"
                    )
                    # Try orientation fix similar to dark (only for 2D)
                    if flat_data.shape != calibrated_frame.shape:
                        if flat_data.ndim == 2 and calibrated_frame.ndim == 2:
                            if flat_data.T.shape == calibrated_frame.shape:
                                self.logger.debug("Transposing master flat to match frame orientation (2D)")
                                flat_data = flat_data.T
                            elif calibrated_frame.T.shape == flat_data.shape:
                                self.logger.debug("Transposing frame to match master flat orientation (2D)")
                                calibrated_frame = calibrated_frame.T
                    flat_data_safe = None
                    if flat_data.shape == calibrated_frame.shape:
                        flat_data_safe = np.where(flat_data > 0, flat_data, 1.0)
                        try:
                            self.logger.debug(
                                f"Flat safe stats: min={float(np.nanmin(flat_data_safe)) if flat_data_safe.size else 'n/a'}, "
                                f"max={float(np.nanmax(flat_data_safe)) if flat_data_safe.size else 'n/a'}"
                            )
                        except Exception:
                            pass
                if flat_data_safe is not None:
                    calibrated_frame = calibrated_frame / flat_data_safe
                    calibration_details['flat_correction_applied'] = True
                    try:
                        self.logger.debug(
                            f"After flat: shape={calibrated_frame.shape}, dtype={calibrated_frame.dtype}, "
                            f"min={float(np.nanmin(calibrated_frame)) if calibrated_frame.size else 'n/a'}, "
                            f"max={float(np.nanmax(calibrated_frame)) if calibrated_frame.size else 'n/a'}"
                        )
                    except Exception:
                        pass
                calibration_details['master_flat_used'] = master_flat['file']
                calibration_details['master_flat_settings'] = {
                    'gain': master_flat.get('gain'),
                    'offset': master_flat.get('offset'),
                    'readout_mode': master_flat.get('readout_mode')
                }
                if calibration_details['flat_correction_applied']:
                    self.logger.debug(
                        f"Applied flat correction using {master_flat['file']} "
                        f"(gain: {master_flat.get('gain', 'N/A')}, "
                        f"offset: {master_flat.get('offset', 'N/A')}, "
                        f"readout: {master_flat.get('readout_mode', 'N/A')})"
                    )
            else:
                self.logger.warning(f"No suitable master flat found for gain={gain}, "
                                  f"offset={offset}, readout={readout_mode}")
            
            # Determine if calibration was applied
            calibration_applied = (
                calibration_details['dark_subtraction_applied'] or
                calibration_details['flat_correction_applied']
            )
            # Persist this as an explicit flag for downstream consumers
            calibration_details['calibration_applied'] = calibration_applied
            
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
    
    def _load_fits_file(self, file_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Load FITS file and return data as numpy array.
        
        Args:
            file_path: Path to FITS file (string or Path object)
            
        Returns:
            Image data as numpy array or None
        """
        try:
            import astropy.io.fits as fits
            
            # Convert to string if Path object
            file_path_str = str(file_path)
            
            with fits.open(file_path_str) as hdul:
                # Get data from first HDU
                data = hdul[0].data
                
                # Convert to float32 for processing
                if data is not None:
                    return data.astype(np.float32)
                else:
                    self.logger.warning(f"FITS file {file_path_str} contains no data")
                    return None
                    
        except ImportError:
            self.logger.warning("astropy not available, cannot load FITS files")
            return None
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
            self.master_bias_cache = None
            self.master_dark_cache.clear()
            self.master_flat_cache = None
            
            # Reload master frames
            self._load_master_frames()
            
            # Check if any frames were loaded
            total_masters = (1 if self.master_bias_cache else 0) + \
                          len(self.master_dark_cache) + \
                          (1 if self.master_flat_cache else 0)
            
            if total_masters > 0:
                self.logger.info(f"Master frames reloaded successfully: {total_masters} frames")
                return True
            else:
                self.logger.warning("No master frames found during reload")
                return False
            
        except Exception as e:
            self.logger.error(f"Error reloading master frames: {e}")
            return False
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """Get current calibration system status.
        
        Returns:
            Dict containing calibration status
        """
        # Get master frame settings info
        dark_settings = {}
        for exp_time, dark_data in self.master_dark_cache.items():
            dark_settings[f"{exp_time:.3f}s"] = {
                'gain': dark_data.get('gain'),
                'offset': dark_data.get('offset'),
                'readout_mode': dark_data.get('readout_mode')
            }
        
        flat_settings = None
        if self.master_flat_cache:
            flat_settings = {
                'gain': self.master_flat_cache.get('gain'),
                'offset': self.master_flat_cache.get('offset'),
                'readout_mode': self.master_flat_cache.get('readout_mode')
            }
        
        return {
            'enable_calibration': self.enable_calibration,
            'auto_load_masters': self.auto_load_masters,
            'calibration_tolerance': self.calibration_tolerance,
            'master_directory': self.master_dir,
            'master_bias_loaded': self.master_bias_cache is not None,
            'master_darks_loaded': len(self.master_dark_cache),
            'master_flat_loaded': self.master_flat_cache is not None,
            'available_exposure_times': list(self.master_dark_cache.keys()) if self.master_dark_cache else [],
            'dark_settings': dark_settings,
            'flat_settings': flat_settings,
            'settings_matching_enabled': True  # New feature
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
                'dtype': str(dark_data['data'].dtype),
                'gain': dark_data.get('gain'),
                'offset': dark_data.get('offset'),
                'readout_mode': dark_data.get('readout_mode')
            }
        
        flat_info = None
        if self.master_flat_cache:
            flat_info = {
                'file': self.master_flat_cache['file'],
                'shape': self.master_flat_cache['data'].shape,
                'dtype': str(self.master_flat_cache['data'].dtype),
                'gain': self.master_flat_cache.get('gain'),
                'offset': self.master_flat_cache.get('offset'),
                'readout_mode': self.master_flat_cache.get('readout_mode')
            }
        
        bias_info = None
        if self.master_bias_cache:
            bias_info = {
                'file': self.master_bias_cache['file'],
                'shape': self.master_bias_cache['data'].shape,
                'dtype': str(self.master_bias_cache['data'].dtype),
                'gain': self.master_bias_cache.get('gain'),
                'offset': self.master_bias_cache.get('offset'),
                'readout_mode': self.master_bias_cache.get('readout_mode')
            }
        
        return {
            'master_bias': bias_info,
            'master_darks': dark_info,
            'master_flat': flat_info
        } 