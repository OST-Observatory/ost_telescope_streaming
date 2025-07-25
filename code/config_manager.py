# config_manager.py
import yaml
import os
from typing import Dict, Any, Optional

class ConfigManager:
    """Verwaltet Konfigurationseinstellungen für das Teleskop-Streaming-System."""
    
    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialisiert den ConfigManager.
        Args:
            config_path: Pfad zur Konfigurationsdatei.
        """
        # If relative path, make it relative to the project root
        if not os.path.isabs(config_path):
            # Try to find config.yaml in the project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # Go up one level from code/
            config_path = os.path.join(project_root, config_path)
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> dict[str, Any]:
        """Lädt die Konfiguration aus der YAML-Datei.
        Returns:
            dict: Die geladene Konfiguration.
        """
        try:
            if not os.path.exists(self.config_path):
                print(f"Warning: Configuration file {self.config_path} not found. Using defaults.")
                return self._get_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            # Validate and merge with defaults
            default_config = self._get_default_config()
            merged_config = self._merge_configs(default_config, config)
            
            # Use logger if available, otherwise print
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Configuration loaded from {self.config_path}")
            except:
                print(f"Configuration loaded from {self.config_path}")
            return merged_config
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            print("Using default configuration.")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict[str, Any]:
        """Gibt die Standardkonfiguration zurück."""
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
                'video_enabled': True,
                'camera_type': 'opencv',
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
                'use_timestamps': False,  # Enable timestamps in frame filenames
                'timestamp_format': '%Y%m%d_%H%M%S',  # Timestamp format for filenames
                'use_capture_count': False,  # Enable capture count in frame filenames
                'file_format': 'png'  # File format for saved frames (jpg, png, tiff, etc.)
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
    
    def _merge_configs(self, default: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        """Führt die Benutzerkonfiguration rekursiv mit den Defaults zusammen."""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Liest einen Konfigurationswert per Dot-Notation aus."""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_mount_config(self) -> dict[str, Any]:
        """Gibt die Montierungs-Konfiguration zurück."""
        return self.config.get('mount', {})
    
    def get_telescope_config(self) -> dict[str, Any]:
        """Gibt die Teleskop-Konfiguration zurück."""
        return self.config.get('telescope', {})
    
    def get_camera_config(self) -> dict[str, Any]:
        """Gibt die Kamera-Konfiguration zurück."""
        return self.config.get('camera', {})
    
    def get_video_config(self) -> dict[str, Any]:
        """Gibt die Video-Konfiguration zurück."""
        return self.config.get('video', {})
    
    def get_plate_solve_config(self) -> dict[str, Any]:
        """Gibt die Plate-Solving-Konfiguration zurück."""
        return self.config.get('plate_solve', {})
    
    def get_overlay_config(self) -> dict[str, Any]:
        """Gibt die Overlay-Konfiguration zurück."""
        return self.config.get('overlay', {})
    
    def get_streaming_config(self) -> dict[str, Any]:
        """Gibt die Streaming-Konfiguration zurück."""
        return self.config.get('overlay', {}).get('update', {})
    
    def get_display_config(self) -> dict[str, Any]:
        """Gibt die Anzeige-Konfiguration zurück."""
        return self.config.get('overlay', {}).get('display', {})
    
    def get_logging_config(self) -> dict[str, Any]:
        """Gibt die Logging-Konfiguration zurück."""
        return self.config.get('logging', {})
    
    def get_platform_config(self) -> dict[str, Any]:
        """Gibt die Plattform-Konfiguration zurück."""
        return self.config.get('platform', {})
    
    def get_advanced_config(self) -> dict[str, Any]:
        """Gibt die erweiterten Konfigurationseinstellungen zurück."""
        return self.config.get('advanced', {})
    
    def reload(self) -> None:
        """Lädt die Konfiguration neu."""
        self.config = self._load_config()
    
    def save_default_config(self, path: Optional[str] = None) -> None:
        """Speichert die Standardkonfiguration in eine Datei."""
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