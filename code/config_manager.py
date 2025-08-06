#!/usr/bin/env python3
"""
Configuration Manager Module for Telescope Streaming System

This module provides a centralized configuration management system for the
telescope streaming application. It handles loading, merging, and accessing
configuration settings from YAML files with support for defaults and overrides.

Key Features:
- YAML-based configuration files
- Default configuration with user overrides
- Lazy loading to prevent double loading
- Section-based configuration access
- Environment variable support
- Configuration validation

Architecture:
- Singleton pattern for global configuration access
- Deep merge for configuration overrides
- Section-based organization for different components
- Error handling for missing or invalid configurations

Dependencies:
- PyYAML for YAML file parsing
- Path handling for file operations
- Logging for configuration events
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """
    Manages configuration settings for the telescope streaming system.
    
    This class provides a centralized way to manage all configuration
    settings for the telescope streaming application. It supports
    loading from YAML files, merging with defaults, and providing
    easy access to configuration sections.
    
    Key Design Decisions:
    - Lazy loading prevents automatic config.yaml loading when config is passed from tests
    - Deep merge ensures user settings override defaults without losing structure
    - Section-based access provides organized configuration retrieval
    - Error handling ensures graceful fallback to defaults
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Optional path to configuration file. If None, uses default.
            
        Note:
            Uses lazy loading to prevent automatic loading of config.yaml
            when a specific config is passed from test scripts.
        """
        self.config_path = config_path or "config.yaml"
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file with defaults.
        
        Loads the configuration file and merges it with default settings.
        If the file doesn't exist, uses only defaults. This ensures the
        system always has a working configuration.
        """
        # Default configuration provides sensible defaults
        # This ensures the system works even without a config file
        default_config = self._get_default_config()
        
        # Try to load user configuration
        user_config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    user_config = yaml.safe_load(file) or {}
                self.logger.info(f"Configuration loaded from {self.config_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load configuration from {self.config_path}: {e}")
                self.logger.info("Using default configuration")
        else:
            self.logger.warning(f"Configuration file {self.config_path} not found. Using defaults.")
        
        # Merge user configuration with defaults
        # This ensures user settings override defaults while preserving structure
        self.config = self._deep_merge(default_config, user_config)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration.
        
        Returns a comprehensive default configuration that ensures
        the system can operate even without a user configuration file.
        
        Returns:
            Dict[str, Any]: Default configuration dictionary
        """
        return {
            'mount': {
                'driver_id': 'ASCOM.tenmicron_mount.Telescope',
                'connection_timeout': 10,
                'validate_coordinates': True
            },
            'telescope': {
                'focal_length': 1000,
                'aperture': 200,
                'type': 'reflector',
                'focal_ratio': 5.0
            },
            'camera': {
                'sensor_width': 6.17,
                'sensor_height': 4.55,
                'pixel_size': 3.75,
                'type': 'color',
                'bit_depth': 8
            },
            'camera': {
                'camera_type': 'opencv',
                'sensor_width': 6.17,
                'sensor_height': 4.55,
                'pixel_size': 3.75,
                'type': 'color',
                'bit_depth': 8,
                'opencv': {
                    'camera_index': 0,
                    'frame_width': 1920,  # Frame width in pixels
                    'frame_height': 1080,  # Frame height in pixels
                    'fps': 30,  # Frames per second
                    'auto_exposure': True,  # Enable auto exposure
                    'exposure_time': 0.1,  # Manual exposure time in seconds
                    'gain': 1.0  # Gain setting
                },
                'ascom': {
                    'ascom_driver': 'ASCOM.MyCamera.Camera',  # ASCOM driver ID for astro cameras
                    'exposure_time': 0.1,  # Manual exposure time in seconds
                    'gain': 1.0,  # Gain setting
                    'binning': 1  # Binning factor (1x1, 2x2, etc.)
                },
                'alpaca': {
                    'host': 'localhost',
                    'port': 11111,
                    'device_id': 0,
                    'exposure_time': 0.1,  # Manual exposure time in seconds
                    'gain': 1.0,  # Gain setting
                    'binning': [1, 1]  # Binning factor [x, y] for Alpaca
                }
            },
            'frame_processing': {
                'enabled': True,
                'use_timestamps': False,  # Enable timestamps in frame filenames
                'timestamp_format': '%Y%m%d_%H%M%S',  # Timestamp format for filenames
                'use_capture_count': False,  # Enable capture count in frame filenames
                'auto_debayer': False,  # Auto-debayer color images
                'debayer_method': 'RGGB',  # Debayer pattern (RGGB, BGGR, GRBG, GBRG)
                'output_dir': 'captured_frames',  # Directory for captured frames
                'cache_dir': 'cache',  # Directory for temporary files
                'file_format': 'PNG'  # File format for saved frames (fits, jpg, png, tiff, etc.)
            },
            'plate_solve': {
                'auto_solve': True,
                'min_solve_interval': 30,
                'save_plate_solve_frames': True,
                'plate_solve_dir': 'plate_solve_frames',
                'default_solver': 'platesolve2',
                'platesolve2': {
                    'executable_path': 'C:/Program Files (x86)/PlaneWave Instruments/PWI3/PlateSolve2/PlateSolve2.exe',
                    'working_directory': 'C:/Users/BP34_Admin/AppData/Local/Temp',
                    'timeout': 60,
                    'verbose': True,
                    'auto_mode': True,
                    'number_of_regions': 999,
                    'min_stars': 20,
                    'max_stars': 200
                },
                'astrometry': {
                    'api_key': '',
                    'api_url': 'http://nova.astrometry.net/api/'
                }
            },
            'overlay': {
                'wait_for_plate_solve': True,
                'field_of_view': 1.5,
                'magnitude_limit': 9.0,
                'include_no_magnitude': False,
                'object_types': [],
                'image_size': [1920, 1080],
                'font_size': 14,
                'output_format': 'png',
                'default_filename': 'overlay.png',
                'max_name_length': 15,
                'use_timestamps': False,
                'timestamp_format': '%Y%m%d_%H%M%S',
                'update': {
                    'update_interval': 30,
                    'max_retries': 3,
                    'retry_delay': 5
                },
                'display': {
                    'object_color': [255, 0, 0],
                    'text_color': [255, 255, 255],
                    'marker_size': 5,
                    'text_offset': [8, -8]
                }
            },
            'logging': {
                'verbose': True,
                'level': 'INFO',
                'show_emojis': False,
                'log_to_file': False,
                'log_file': 'telescope_streaming.log'
            },
            'platform': {
                'fonts': {
                    'windows': ['arial.ttf', 'C:/Windows/Fonts/arial.ttf'],
                    'linux': ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/TTF/arial.ttf'],
                    'macos': ['/System/Library/Fonts/Arial.ttf', '/Library/Fonts/Arial.ttf']
                }
            },
            'advanced': {
                'debug_coordinates': False,
                'debug_simbad': False,
                'save_empty_overlays': True,
                'auto_recovery': True
            }
        }
    
    def _deep_merge(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Deeply merge user configuration with default settings.
        
        Recursively merges user-defined settings into the default configuration.
        If a key exists in both, the user's value is used.
        If a key exists only in default, it's added.
        If a key exists only in user, it's added.
        """
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a configuration value by dot notation.
        
        Retrieves a value from the configuration dictionary using a dot notation
        for nested keys. If the key is not found, returns the default value.
        
        Args:
            key_path: String representing the path to the value (e.g., 'video.opencv.camera_index')
            default: Value to return if the key is not found.
            
        Returns:
            Any: The value found or the default value.
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_mount_config(self) -> Dict[str, Any]:
        """Get the mount configuration.
        
        Retrieves the configuration for the telescope mount.
        
        Returns:
            Dict[str, Any]: The mount configuration.
        """
        return self.config.get('mount', {})
    
    def get_telescope_config(self) -> Dict[str, Any]:
        """Get the telescope configuration.
        
        Retrieves the configuration for the telescope itself.
        
        Returns:
            Dict[str, Any]: The telescope configuration.
        """
        return self.config.get('telescope', {})
    
    def get_camera_config(self):
        """Get camera configuration."""
        camera_config = self.config.get('camera', {})
        
        # Set defaults for missing values
        defaults = {
            'camera_type': 'opencv',
            
            'sensor_width': 23.5,    # Sensor width in mm
            'sensor_height': 15.7,   # Sensor height in mm
            'pixel_size': 3.76,      # Pixel size in micrometers
            'type': 'color',         # Camera type (mono, color)
            'bit_depth': 16,         # Bit depth
            'cooling': {
                'enable_cooling': False,
                'target_temperature': -10.0,
                'wait_for_cooling': True,
                'cooling_timeout': 300,
                'stabilization_tolerance': 1.0,
                'warmup_rate': 2.0,
                'warmup_final_temp': 15.0,
                'warmup_at_end': True
            },
            'ascom': {
                'ascom_driver': 'ASCOM.ZWOASI.Camera',
                'exposure_time': 5.0,
                'gain': 100.0,
                'offset': 50.0,
                'readout_mode': 0,
                'binning': 1,
                'filter_wheel_driver': None
            },
            'alpaca': {
                'host': 'localhost',
                'port': 11111,
                'device_id': 0,
                'exposure_time': 5.0,
                'gain': 100.0,
                'offset': 50.0,
                'readout_mode': 0,
                'binning': [1, 1]
            },
            'opencv': {
                'camera_index': 0,
                'exposure_time': 1.0,
                'gain': 100.0,
                'resolution': [1920, 1080],
                'frame_rate': 30
            }
        }
        
        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in camera_config:
                camera_config[key] = default_value
            elif isinstance(default_value, dict) and isinstance(camera_config[key], dict):
                # Recursively merge nested dictionaries
                for sub_key, sub_default in default_value.items():
                    if sub_key not in camera_config[key]:
                        camera_config[key][sub_key] = sub_default
        
        return camera_config
    
    def get_frame_processing_config(self):
        """Get frame processing configuration."""
        frame_config = self.config.get('frame_processing', {})
        
        # Set defaults for missing values
        defaults = {
            'enabled': True,
            'use_timestamps': False,
            'timestamp_format': '%Y%m%d_%H%M%S',
            'use_capture_count': False,
            'auto_debayer': False,
            'debayer_method': 'RGGB',
            'output_dir': 'captured_frames',
            'cache_dir': 'cache'
        }
        
        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in frame_config:
                frame_config[key] = default_value
        
        return frame_config
    
    def get_video_config(self):
        """DEPRECATED: Use get_frame_processing_config() instead.
        
        This method is kept for backward compatibility but will be removed
        in a future version.
        """
        import warnings
        warnings.warn("get_video_config() is deprecated, use get_frame_processing_config() instead", 
                     DeprecationWarning, stacklevel=2)
        return self.get_frame_processing_config()
    
    def get_plate_solve_config(self) -> Dict[str, Any]:
        """Get the plate solving configuration.
        
        Retrieves the configuration for the plate solving process.
        
        Returns:
            Dict[str, Any]: The plate solving configuration.
        """
        return self.config.get('plate_solve', {})
    
    def get_overlay_config(self) -> Dict[str, Any]:
        """Get the overlay configuration.
        
        Retrieves the configuration for the overlay display.
        
        Returns:
            Dict[str, Any]: The overlay configuration.
        """
        return self.config.get('overlay', {})
    
    def get_streaming_config(self) -> Dict[str, Any]:
        """Get the streaming update configuration.
        
        Retrieves the configuration for how often the overlay updates.
        
        Returns:
            Dict[str, Any]: The streaming update configuration.
        """
        return self.config.get('overlay', {}).get('update', {})
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get the display configuration.
        
        Retrieves the configuration for the overlay display settings.
        
        Returns:
            Dict[str, Any]: The display configuration.
        """
        return self.config.get('overlay', {}).get('display', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get the logging configuration.
        
        Retrieves the configuration for logging settings.
        
        Returns:
            Dict[str, Any]: The logging configuration.
        """
        return self.config.get('logging', {})
    
    def get_platform_config(self) -> Dict[str, Any]:
        """Get the platform configuration.
        
        Retrieves the configuration for platform-specific settings.
        
        Returns:
            Dict[str, Any]: The platform configuration.
        """
        return self.config.get('platform', {})
    
    def get_advanced_config(self) -> Dict[str, Any]:
        """Get the advanced configuration.
        
        Retrieves the configuration for advanced settings.
        
        Returns:
            Dict[str, Any]: The advanced configuration.
        """
        return self.config.get('advanced', {})
    
    def get_flat_config(self) -> dict[str, Any]:
        """Get flat capture configuration.
        
        Returns:
            dict: Flat capture configuration settings
        """
        return self.config.get('flat_capture', {
            'target_count_rate': 0.5,      # 50% of maximum count
            'count_tolerance': 0.1,        # 10% tolerance
            'num_flats': 40,               # Number of flat frames to capture
            'min_exposure': 0.001,         # Minimum exposure time (1ms)
            'max_exposure': 10.0,          # Maximum exposure time (10s)
            'exposure_step_factor': 1.5,   # Factor for exposure adjustment
            'max_adjustment_attempts': 10,  # Maximum attempts to adjust exposure
            'output_dir': 'flats'          # Output directory for flat frames
        })
    
    def get_dark_config(self) -> dict[str, Any]:
        """Get dark capture configuration.
        
        Returns:
            dict: Dark capture configuration settings
        """
        return self.config.get('dark_capture', {
            'num_darks': 40,                    # Number of dark frames per exposure time
            'flat_exposure_time': None,         # Flat exposure time (auto-detected if None)
            'science_exposure_time': 5.0,       # Science image exposure time
            'min_exposure': 0.001,              # Minimum exposure time for bias frames
            'max_exposure': 60.0,               # Maximum exposure time
            'exposure_factors': [0.5, 1.0, 2.0, 4.0],  # Factors for extended range
            'output_dir': 'darks'               # Output directory for dark frames
        })
    
    def get_master_config(self) -> dict[str, Any]:
        """Get master frame creation configuration.
        
        Returns:
            dict: Master frame creation configuration settings
        """
        return self.config.get('master_frames', {
            'output_dir': 'master_frames',           # Output directory for master frames
            'rejection_method': 'sigma_clip',        # 'sigma_clip' or 'minmax'
            'sigma_threshold': 3.0,                  # Sigma threshold for rejection
            'normalization_method': 'mean',          # 'mean', 'median', 'max'
            'quality_control': True,                 # Enable quality control
            'save_individual_masters': True,         # Save individual master frames
            'create_master_bias': True,              # Create master bias frame
            'create_master_darks': True,             # Create master dark frames
            'create_master_flats': True,             # Create master flat frames
            'enable_calibration': True,              # Enable automatic calibration
            'auto_load_masters': True,               # Auto-load master frames on startup
            'calibration_tolerance': 0.1             # 10% tolerance for exposure time matching
        })
    
    def reload(self) -> None:
        """Reload the configuration from the file.
        
        Forces the configuration manager to reload the configuration
        from the YAML file, effectively re-merging with defaults.
        """
        self.config = {} # Clear current config to force reload
        self._load_config()
    
    def save_default_config(self, path: Optional[str] = None) -> None:
        """Save the default configuration to a file.
        
        Saves the current default configuration to a new file.
        If no path is provided, it saves to a file named config.yaml.default.
        
        Args:
            path: Optional path to save the default configuration.
        """
        if path is None:
            path = f"{self.config_path}.default"
        
        try:
            with open(path, 'w', encoding='utf-8') as file:
                yaml.dump(self._get_default_config(), file, default_flow_style=False, allow_unicode=True)
            self.logger.info(f"Default configuration saved to {path}")
        except Exception as e:
            self.logger.error(f"Error saving default configuration: {e}") 