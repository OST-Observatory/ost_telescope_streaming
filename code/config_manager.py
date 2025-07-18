# config_manager.py
import yaml
import os
from typing import Dict, Any, Optional

class ConfigManager:
    """Manages configuration settings for the telescope streaming system."""
    
    def __init__(self, config_path: str = "config.yaml"):
        # If relative path, make it relative to the project root
        if not os.path.isabs(config_path):
            # Try to find config.yaml in the project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # Go up one level from code/
            config_path = os.path.join(project_root, config_path)
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                print(f"Warning: Configuration file {self.config_path} not found. Using defaults.")
                return self._get_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            # Validate and merge with defaults
            default_config = self._get_default_config()
            merged_config = self._merge_configs(default_config, config)
            
            print(f"Configuration loaded from {self.config_path}")
            return merged_config
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            print("Using default configuration.")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
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
            'video': {
                'camera_index': 0,
                'frame_width': 1920,
                'frame_height': 1080,
                'fps': 30,
                'auto_exposure': True,
                'exposure_time': 100,
                'gain': 1.0,
                'plate_solving_enabled': False,
                'plate_solving_interval': 60,
                'save_plate_solve_frames': True,
                'plate_solve_dir': 'plate_solve_frames'
            },
            'plate_solve': {
                'default_solver': 'platesolve2',
                'auto_solve': True,
                'min_solve_interval': 30,
                'platesolve2_path': 'C:/Program Files (x86)/PlaneWave Instruments/PWI3/PlateSolve2/PlateSolve2.exe',
                'working_directory': 'C:/Users/BP34_Admin/AppData/Local/Temp',
                'timeout': 60,
                'verbose': False,
                'use_gui_mode': True,
                'auto_mode': True,
                'silent_mode': True,
                'result_file_pattern': '*.txt',
                'number_of_regions': 999,
                'search_radius': 15,
                'min_stars': 20,
                'max_stars': 200,
                'astrometry_api_key': '',
                'astrometry_api_url': 'http://nova.astrometry.net/api/'
            },
            'overlay': {
                'field_of_view': 1.5,
                'magnitude_limit': 10.0,
                'include_no_magnitude': True,
                'object_types': [],
                'image_size': [800, 800],
                'font_size': 14,
                'output_format': 'png',
                'default_filename': 'overlay.png',
                # 'simbad_timeout': 30,  # Not used in newer astroquery versions
                'max_name_length': 15
            },
            'streaming': {
                'update_interval': 30,
                'max_retries': 3,
                'retry_delay': 5,
                'use_timestamps': True,
                'timestamp_format': '%Y%m%d_%H%M%S'
            },
            'display': {
                'object_color': [255, 0, 0],
                'text_color': [255, 255, 255],
                'marker_size': 5,
                'text_offset': [8, -8]
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
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge user configuration with defaults."""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'mount.driver_id')."""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_mount_config(self) -> Dict[str, Any]:
        """Get mount configuration section."""
        return self.config.get('mount', {})
    
    def get_telescope_config(self) -> Dict[str, Any]:
        """Get telescope configuration section."""
        return self.config.get('telescope', {})
    
    def get_camera_config(self) -> Dict[str, Any]:
        """Get camera configuration section."""
        return self.config.get('camera', {})
    
    def get_video_config(self) -> Dict[str, Any]:
        """Get video configuration section."""
        return self.config.get('video', {})
    
    def get_plate_solve_config(self) -> Dict[str, Any]:
        """Get plate-solving configuration section."""
        return self.config.get('plate_solve', {})
    
    def get_overlay_config(self) -> Dict[str, Any]:
        """Get overlay configuration section."""
        return self.config.get('overlay', {})
    
    def get_streaming_config(self) -> Dict[str, Any]:
        """Get streaming configuration section."""
        return self.config.get('streaming', {})
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration section."""
        return self.config.get('display', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration section."""
        return self.config.get('logging', {})
    
    def get_platform_config(self) -> Dict[str, Any]:
        """Get platform configuration section."""
        return self.config.get('platform', {})
    
    def get_advanced_config(self) -> Dict[str, Any]:
        """Get advanced configuration section."""
        return self.config.get('advanced', {})
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self.config = self._load_config()
    
    def save_default_config(self, path: Optional[str] = None) -> None:
        """Save default configuration to file."""
        if path is None:
            path = f"{self.config_path}.default"
        
        try:
            with open(path, 'w', encoding='utf-8') as file:
                yaml.dump(self._get_default_config(), file, default_flow_style=False, allow_unicode=True)
            print(f"Default configuration saved to {path}")
        except Exception as e:
            print(f"Error saving default configuration: {e}")

# Global configuration instance
config = ConfigManager() 