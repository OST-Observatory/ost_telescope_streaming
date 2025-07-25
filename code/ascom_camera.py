#!/usr/bin/env python3
"""
ASCOM Camera integration for QHY, ZWO and other ASCOM-compatible cameras.
Provides methods to connect, configure, expose, and download images.
"""

from status import CameraStatus, success_status, error_status
from exceptions import CameraError
from typing import Optional, Any

class ASCOMCamera:
    def __init__(self, driver_id: str, config=None, logger=None):
        from config_manager import config as default_config
        import logging
        self.config = config or default_config
        
        # Use provided logger or get logger with proper name
        if logger:
            self.logger = logger
        else:
            # Get logger with module name for better identification
            self.logger = logging.getLogger(__name__)
            # Ensure logger has proper level if root logger is configured
            if logging.getLogger().handlers:
                self.logger.setLevel(logging.getLogger().level)
        
        self.driver_id = driver_id
        self.camera = None
        
        # Store last known cooling values to bypass ASCOM driver cache issues
        self.last_cooling_info = {
            'temperature': None,
            'cooler_power': None,
            'cooler_on': None,
            'target_temperature': None
        }
        
        # Cache file path for persistent storage
        import os
        cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, f'cooling_cache_{driver_id.replace(".", "_").replace(":", "_")}.json')
        
        # Load existing cache if available
        self.load_cooling_cache()
        
        # Optional separate filter wheel driver
        self.filter_wheel = None
        self.filter_wheel_driver_id = None
        self._setup_filter_wheel()

    def load_cooling_cache(self) -> None:
        """Load cooling cache from persistent storage."""
        try:
            import json
            import os
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cached_data = json.load(f)
                    # Check if cache is recent (less than 5 minutes old)
                    import time
                    if 'timestamp' in cached_data:
                        cache_age = time.time() - cached_data['timestamp']
                        if cache_age < 300:  # 5 minutes
                            self.last_cooling_info.update(cached_data.get('cooling_info', {}))
                            self.logger.debug(f"Loaded cooling cache from {self.cache_file}")
                        else:
                            self.logger.debug(f"Cache too old ({cache_age:.1f}s), not loading")
                    else:
                        # Legacy cache without timestamp
                        self.last_cooling_info.update(cached_data)
                        self.logger.debug(f"Loaded legacy cooling cache from {self.cache_file}")
        except Exception as e:
            self.logger.debug(f"Failed to load cooling cache: {e}")

    def save_cooling_cache(self) -> None:
        """Save cooling cache to persistent storage."""
        try:
            import json
            import time
            cache_data = {
                'timestamp': time.time(),
                'cooling_info': self.last_cooling_info.copy()
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            self.logger.debug(f"Saved cooling cache to {self.cache_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save cooling cache: {e}")

    def connect(self) -> CameraStatus:
        try:
            import win32com.client
            self.camera = win32com.client.Dispatch(self.driver_id)
            self.camera.Connected = True
            
            # Connect to filter wheel if configured
            if self.filter_wheel_driver_id:
                filter_wheel_status = self._connect_filter_wheel()
                if not filter_wheel_status.is_success:
                    self.logger.warning(f"Filter wheel connection failed: {filter_wheel_status.message}")
            
            return success_status("ASCOM camera connected")
        except Exception as e:
            return error_status(f"Failed to connect to ASCOM camera: {e}")

    def disconnect(self) -> CameraStatus:
        try:
            # Disconnect filter wheel first
            if self.filter_wheel_driver_id:
                self._disconnect_filter_wheel()
            
            # Disconnect camera
            if self.camera and self.camera.Connected:
                self.camera.Connected = False
            return success_status("ASCOM camera disconnected")
        except Exception as e:
            return error_status(f"Failed to disconnect: {e}")

    def expose(self, exposure_time_s: float, gain: Optional[int] = None, binning: int = 1) -> CameraStatus:
        """Starte eine Belichtung mit der angegebenen Zeit in Sekunden."""
        try:
            self.camera.BinX = binning
            self.camera.BinY = binning
            if gain is not None and hasattr(self.camera, 'Gain'):
                self.camera.Gain = gain
            self.camera.StartExposure(exposure_time_s, False)
            while not self.camera.ImageReady:
                import time; time.sleep(0.1)
            return success_status("Exposure complete")
        except Exception as e:
            return error_status(f"Exposure failed: {e}")

    def get_image(self) -> CameraStatus:
        try:
            img_array = self.camera.ImageArray
            return success_status("Image downloaded", data=img_array)
        except Exception as e:
            return error_status(f"Failed to get image: {e}")

    def has_cooling(self) -> bool:
        return hasattr(self.camera, 'CanSetCCDTemperature') and self.camera.CanSetCCDTemperature

    def set_cooling(self, target_temp: float) -> CameraStatus:
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        try:
            # Get current temperature before setting
            current_temp = self.camera.CCDTemperature
            current_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            current_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            # First, turn on the cooler if it's not already on
            if hasattr(self.camera, 'CoolerOn') and not self.camera.CoolerOn:
                self.camera.CoolerOn = True
                self.logger.info("Cooler turned on")
            
            # Set target temperature
            self.camera.SetCCDTemperature = target_temp
            
            # Get values after setting
            new_temp = self.camera.CCDTemperature
            new_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            new_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            details = {
                'target_temp': target_temp,
                'current_temp': current_temp,
                'new_temp': new_temp,
                'current_power': current_power,
                'new_power': new_power,
                'current_cooler_on': current_cooler_on,
                'new_cooler_on': new_cooler_on
            }
            
            # Update cache with new values
            self.update_cooling_cache({
                'temperature': new_temp,
                'cooler_power': new_power,
                'cooler_on': new_cooler_on,
                'target_temperature': target_temp
            })
            
            return success_status(f"Cooling set to {target_temp}°C", details=details)
        except Exception as e:
            return error_status(f"Failed to set cooling: {e}")

    def set_cooler_on(self, on: bool = True) -> CameraStatus:
        """Turn the cooler on or off.
        Args:
            on: True to turn on, False to turn off
        Returns:
            CameraStatus: Status of the operation
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        if not hasattr(self.camera, 'CoolerOn'):
            return error_status("Cooler on/off control not available")
        try:
            # Get current values before changing
            current_temp = self.camera.CCDTemperature
            current_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            current_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            # Set cooler state
            self.camera.CoolerOn = on
            
            # Get values after changing
            new_temp = self.camera.CCDTemperature
            new_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            new_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            # Update cache with new values
            self.update_cooling_cache({
                'temperature': new_temp,
                'cooler_power': new_power,
                'cooler_on': new_cooler_on,
                'target_temperature': self.last_cooling_info.get('target_temperature')
            })
            
            status = "on" if on else "off"
            return success_status(f"Cooler turned {status}")
        except Exception as e:
            return error_status(f"Failed to turn cooler {'on' if on else 'off'}: {e}")

    def turn_cooling_off(self) -> CameraStatus:
        """Turn off the cooling system.
        Returns:
            CameraStatus: Status of the operation
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        try:
            # Get current values before turning off
            current_temp = self.camera.CCDTemperature
            current_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            current_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            # Turn off the cooler
            if hasattr(self.camera, 'CoolerOn'):
                self.camera.CoolerOn = False
            
            # Set target temperature to ambient (or a high value to stop cooling)
            # Some cameras need this to actually stop cooling
            if hasattr(self.camera, 'SetCCDTemperature'):
                self.camera.SetCCDTemperature = 50.0  # High temperature to stop cooling
            
            # Get values after turning off
            new_temp = self.camera.CCDTemperature
            new_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            new_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            # Update cache with new values
            self.update_cooling_cache({
                'temperature': new_temp,
                'cooler_power': new_power,
                'cooler_on': new_cooler_on,
                'target_temperature': 50.0
            })
            
            details = {
                'current_temp': current_temp,
                'new_temp': new_temp,
                'current_power': current_power,
                'new_power': new_power,
                'current_cooler_on': current_cooler_on,
                'new_cooler_on': new_cooler_on
            }
            
            return success_status("Cooling turned off", details=details)
        except Exception as e:
            return error_status(f"Failed to turn off cooling: {e}")

    def get_temperature(self) -> CameraStatus:
        try:
            temp = self.camera.CCDTemperature
            return success_status("Current temperature read", data=temp)
        except Exception as e:
            return error_status(f"Failed to read temperature: {e}")

    def get_cooler_power(self) -> CameraStatus:
        """Get the current cooler power in percentage.
        Returns:
            CameraStatus: Status with cooler power percentage (0-100)
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        try:
            power = self.camera.CoolerPower
            return success_status("Current cooler power read", data=power)
        except Exception as e:
            return error_status(f"Failed to read cooler power: {e}")

    def get_cooling_info(self) -> CameraStatus:
        """Get comprehensive cooling information.
        Returns:
            CameraStatus: Status with detailed cooling information
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        try:
            info = {}
            
            # Try to force a refresh by reading properties multiple times
            # Some ASCOM drivers cache values and need multiple reads to update
            import time
            
            # Read temperature multiple times to ensure we get the latest value
            temp_reads = []
            for i in range(3):
                temp_reads.append(self.camera.CCDTemperature)
                time.sleep(0.1)
            info['temperature'] = temp_reads[-1]  # Use the last reading
            
            # Read cooler power multiple times
            if hasattr(self.camera, 'CoolerPower'):
                power_reads = []
                for i in range(3):
                    power_reads.append(self.camera.CoolerPower)
                    time.sleep(0.1)
                info['cooler_power'] = power_reads[-1]
            else:
                info['cooler_power'] = None
            
            # Read cooler on/off status multiple times
            if hasattr(self.camera, 'CoolerOn'):
                cooler_on_reads = []
                for i in range(3):
                    cooler_on_reads.append(self.camera.CoolerOn)
                    time.sleep(0.1)
                info['cooler_on'] = cooler_on_reads[-1]
            else:
                info['cooler_on'] = None
            
            # Check if we can control cooler power directly
            info['can_set_cooler_power'] = hasattr(self.camera, 'SetCoolerPower')
            
            # Check target temperature
            info['target_temperature'] = self.camera.SetCCDTemperature if hasattr(self.camera, 'SetCCDTemperature') else None
            
            return success_status("Cooling information retrieved", data=info)
        except Exception as e:
            return error_status(f"Failed to get cooling info: {e}")

    def get_fresh_cooling_info(self) -> CameraStatus:
        """Get fresh cooling information by simulating a cooling operation.
        This bypasses the ASCOM driver cache issue.
        Returns:
            CameraStatus: Status with fresh cooling information
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        try:
            info = {}
            
            # Get current target temperature first
            current_target = self.camera.SetCCDTemperature if hasattr(self.camera, 'SetCCDTemperature') else None
            
            # Simulate a cooling operation to force driver to update values
            # This is the same logic as set_cooling() but without changing anything
            current_temp = self.camera.CCDTemperature
            current_power = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            current_cooler_on = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            
            # Force a refresh by setting the same target temperature
            if hasattr(self.camera, 'SetCCDTemperature'):
                self.camera.SetCCDTemperature = current_target
            
            # Read fresh values after the "operation"
            info['temperature'] = self.camera.CCDTemperature
            info['cooler_power'] = self.camera.CoolerPower if hasattr(self.camera, 'CoolerPower') else None
            info['cooler_on'] = self.camera.CoolerOn if hasattr(self.camera, 'CoolerOn') else None
            info['target_temperature'] = current_target
            info['can_set_cooler_power'] = hasattr(self.camera, 'SetCoolerPower')
            
            self.logger.debug(f"Fresh cooling info - Temp: {info['temperature']}°C, Power: {info['cooler_power']}%, On: {info['cooler_on']}")
            
            return success_status("Fresh cooling information retrieved", data=info)
        except Exception as e:
            return error_status(f"Failed to get fresh cooling info: {e}")

    def get_cached_cooling_info(self) -> CameraStatus:
        """Get cooling information from cached values (bypasses ASCOM driver cache).
        Returns:
            CameraStatus: Status with cached cooling information
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        
        # Use cached values if available, otherwise try to get from ASCOM
        if self.last_cooling_info['temperature'] is not None:
            info = self.last_cooling_info.copy()
            info['can_set_cooler_power'] = hasattr(self.camera, 'SetCoolerPower')
            self.logger.debug(f"Using cached cooling info - Temp: {info['temperature']}°C, Power: {info['cooler_power']}%, On: {info['cooler_on']}")
            return success_status("Cached cooling information retrieved", data=info)
        else:
            # Fallback to ASCOM values if no cache available
            return self.get_cooling_info()

    def get_smart_cooling_info(self) -> CameraStatus:
        """Get cooling information using the best available method for this camera.
        Automatically detects and uses the most reliable method based on driver type.
        Returns:
            CameraStatus: Status with cooling information
        """
        if not self.has_cooling():
            return error_status("Cooling not supported by this camera")
        
        try:
            # Check if this is a QHY camera (known for caching issues)
            is_qhy = 'QHYCCD' in self.driver_id or 'QHY' in self.driver_id
            
            # Check if we have valid cached data
            has_valid_cache = (
                self.last_cooling_info['temperature'] is not None and
                self.last_cooling_info['cooler_power'] is not None and
                self.last_cooling_info['cooler_on'] is not None
            )
            
            # Debug output
            self.logger.debug(f"Smart cooling info - QHY: {is_qhy}, Valid cache: {has_valid_cache}")
            self.logger.debug(f"Cache state: {self.last_cooling_info}")
            
            if is_qhy:
                # For QHY cameras, use cached values if available, otherwise use fresh method
                if has_valid_cache:
                    self.logger.info("QHY camera detected - using cached cooling info")
                    return self.get_cached_cooling_info()
                else:
                    self.logger.info("QHY camera detected - no valid cache, using fresh cooling info method")
                    return self.get_fresh_cooling_info()
            else:
                # For other cameras, try normal method first, then fresh if needed
                self.logger.info("Non-QHY camera - trying normal cooling info method")
                return self.get_cooling_info()
                
        except Exception as e:
            self.logger.warning(f"Smart cooling info failed: {e}, falling back to normal method")
            return self.get_cooling_info()

    def update_cooling_cache(self, info: dict) -> None:
        """Update the internal cooling cache with fresh values.
        Args:
            info: Dictionary with cooling information
        """
        if info and isinstance(info, dict):
            self.last_cooling_info.update({
                'temperature': info.get('temperature'),
                'cooler_power': info.get('cooler_power'),
                'cooler_on': info.get('cooler_on'),
                'target_temperature': info.get('target_temperature')
            })
            self.logger.debug(f"Updated cooling cache: {self.last_cooling_info}")
            
            # Save cache to persistent storage
            self.save_cooling_cache()

    def has_filter_wheel(self) -> bool:
        """Check if filter wheel is available (integrated or separate)."""
        # Check integrated filter wheel
        if hasattr(self.camera, 'FilterNames'):
            return True
        
        # Check separate filter wheel
        if self.filter_wheel_driver_id and self.filter_wheel:
            return True
        
        return False

    def _get_filter_wheel_device(self):
        """Get the appropriate filter wheel device (integrated or separate)."""
        # Try integrated filter wheel first
        if hasattr(self.camera, 'FilterNames'):
            return self.camera, "integrated"
        
        # Try separate filter wheel
        if self.filter_wheel_driver_id and self.filter_wheel:
            return self.filter_wheel, "separate"
        
        return None, None

    def _is_qhy_filter_wheel(self, device_type: str) -> bool:
        """Check if this is a QHY filter wheel."""
        return (device_type == "separate" and 
                self.filter_wheel_driver_id and 
                ('QHY' in self.filter_wheel_driver_id or 'QHYCFW' in self.filter_wheel_driver_id))

    def get_filter_names(self) -> CameraStatus:
        if not self.has_filter_wheel():
            return error_status("No filter wheel present")
        
        device, device_type = self._get_filter_wheel_device()
        if not device:
            return error_status("No filter wheel device available")
        
        try:
            # Handle QHY filter wheels differently
            if self._is_qhy_filter_wheel(device_type):
                # QHY filter wheels might not have FilterNames property
                # Try alternative properties or return default names
                try:
                    names = list(device.FilterNames)
                except:
                    # QHY default filter names (common setup)
                    names = ['Halpha', 'OIII', 'SII', 'U', 'B', 'V', 'R', 'I', 'Clear']
                    self.logger.info("Using default QHY filter names")
                
                self.logger.debug(f"Filter names retrieved from QHY filter wheel: {names}")
                return success_status(f"Filter names retrieved from QHY filter wheel", data=names)
            else:
                # Standard ASCOM filter wheel
                names = list(device.FilterNames)
                self.logger.debug(f"Filter names retrieved from {device_type} filter wheel")
                return success_status(f"Filter names retrieved from {device_type} filter wheel", data=names)
        except Exception as e:
            return error_status(f"Failed to get filter names from {device_type} filter wheel: {e}")

    def set_filter_position(self, position: int) -> CameraStatus:
        if not self.has_filter_wheel():
            return error_status("No filter wheel present")
        
        device, device_type = self._get_filter_wheel_device()
        if not device:
            return error_status("No filter wheel device available")
        
        try:
            # Handle QHY filter wheels with position validation
            if self._is_qhy_filter_wheel(device_type):
                # QHY filter wheels might need position validation
                if position < 0:
                    return error_status(f"Invalid filter position for QHY filter wheel: {position}")
                
                # Set position
                device.Position = position
                
                # Wait a bit for QHY filter wheel to settle
                import time
                time.sleep(0.5)
                
                self.logger.info(f"Filter position set to {position} on QHY filter wheel")
                return success_status(f"Filter position set to {position} on QHY filter wheel")
            else:
                # Standard ASCOM filter wheel
                device.Position = position
                self.logger.info(f"Filter position set to {position} on {device_type} filter wheel")
                return success_status(f"Filter position set to {position} on {device_type} filter wheel")
        except Exception as e:
            return error_status(f"Failed to set filter position on {device_type} filter wheel: {e}")

    def get_filter_position(self) -> CameraStatus:
        if not self.has_filter_wheel():
            return error_status("No filter wheel present")
        
        device, device_type = self._get_filter_wheel_device()
        if not device:
            return error_status("No filter wheel device available")
        
        try:
            pos = device.Position
            
            # Handle QHY filter wheel position -1 (unknown/not set)
            if self._is_qhy_filter_wheel(device_type) and pos == -1:
                self.logger.warning("QHY filter wheel position is -1 (unknown/not set)")
                
                # Try multiple approaches for QHY filter wheels
                import time
                
                # Method 1: Wait and retry
                time.sleep(0.2)
                pos = device.Position
                
                # Method 2: Try to read from alternative properties
                if pos == -1:
                    try:
                        # Some QHY filter wheels have different property names
                        if hasattr(device, 'CurrentPosition'):
                            pos = device.CurrentPosition
                            self.logger.info("Using CurrentPosition property for QHY filter wheel")
                        elif hasattr(device, 'FilterPosition'):
                            pos = device.FilterPosition
                            self.logger.info("Using FilterPosition property for QHY filter wheel")
                    except:
                        pass
                
                # Method 3: Final retry
                if pos == -1:
                    time.sleep(0.3)
                    pos = device.Position
                
                if pos == -1:
                    self.logger.warning("QHY filter wheel still reporting position -1 after multiple attempts")
                    # For QHY filter wheels, -1 might be acceptable if we can't get the real position
                    self.logger.info("QHY filter wheel position -1 is acceptable (common QHY behavior)")
            
            self.logger.debug(f"Current filter position from {device_type} filter wheel: {pos}")
            return success_status(f"Current filter position from {device_type} filter wheel", data=pos)
        except Exception as e:
            return error_status(f"Failed to get filter position from {device_type} filter wheel: {e}")

    def is_color_camera(self) -> bool:
        # Heuristik: SensorType oder BayerPattern vorhanden
        return hasattr(self.camera, 'SensorType') and 'color' in str(self.camera.SensorType).lower()

    def debayer(self, img_array: Any, pattern: Optional[str] = None) -> CameraStatus:
        """Debayer an image with automatic pattern detection.
        Args:
            img_array: Raw image array
            pattern: Optional manual pattern override ('RGGB', 'GRBG', 'GBRG', 'BGGR')
        Returns:
            CameraStatus: Status with debayered image data
        """
        try:
            # Use provided pattern or auto-detect from sensor_type
            if pattern is None:
                pattern = self.sensor_type
            
            if pattern is None:
                return error_status("No Bayer pattern available and none provided")
            
            # Apply debayering based on detected pattern
            if pattern == 'RGGB':
                bayer_pattern = cv2.COLOR_BayerRG2BGR
            elif pattern == 'GRBG':
                bayer_pattern = cv2.COLOR_BayerGR2BGR
            elif pattern == 'GBRG':
                bayer_pattern = cv2.COLOR_BayerGB2BGR
            elif pattern == 'BGGR':
                bayer_pattern = cv2.COLOR_BayerBG2BGR
            else:
                return error_status(f"Unsupported Bayer pattern: {pattern}")
            
            # Convert to numpy array and apply debayering
            image_array = np.array(img_array)
            debayered_image = cv2.cvtColor(image_array, bayer_pattern)
            
            return success_status(f"Image debayered with {pattern} pattern", data=debayered_image)
            
        except Exception as e:
            return error_status(f"Debayering failed: {e}")

    @property
    def sensor_type(self) -> Optional[str]:
        """Get the sensor type (Bayer pattern) for color cameras.
        Returns:
            str: Bayer pattern ('RGGB', 'GRBG', 'GBRG', 'BGGR') or None for monochrome
        """
        try:
            if not self.camera or not self.camera.Connected:
                return None

            # Try to get Bayer pattern from ASCOM camera
            if hasattr(self.camera, 'SensorType'):
                sensor_type = self.camera.SensorType
                # ASCOM SensorType enum values: 0=Monochrome, 1=Color, 2=RgGg, 3=RGGB, etc.
                if sensor_type == 0:  # Monochrome
                    return None
                elif sensor_type == 1:  # Color (generic)
                    return 'RGGB'  # Default assumption
                elif sensor_type == 2:  # RgGg
                    return 'RGGB'
                elif sensor_type == 3:  # RGGB
                    return 'RGGB'
                elif sensor_type == 4:  # GRBG
                    return 'GRBG'
                elif sensor_type == 5:  # GBRG
                    return 'GBRG'
                elif sensor_type == 6:  # BGGR
                    return 'BGGR'

            # Fallback: check if camera is color
            if hasattr(self.camera, 'IsColor') and self.camera.IsColor:
                return 'RGGB'  # Default assumption for color cameras

            return None  # Assume monochrome

        except Exception as e:
            self.logger.warning(f"Could not determine sensor type: {e}")
            return None 

    def _setup_filter_wheel(self) -> None:
        """Setup optional separate filter wheel driver."""
        try:
            # Get filter wheel driver from config
            video_config = self.config.get_video_config()
            if 'filter_wheel_driver' in video_config.get('ascom', {}):
                self.filter_wheel_driver_id = video_config['ascom']['filter_wheel_driver']
                self.logger.info(f"Filter wheel driver configured: {self.filter_wheel_driver_id}")
            else:
                self.logger.debug("No separate filter wheel driver configured")
        except Exception as e:
            self.logger.debug(f"Failed to setup filter wheel: {e}")

    def _connect_filter_wheel(self) -> CameraStatus:
        """Connect to separate filter wheel driver if configured."""
        if not self.filter_wheel_driver_id:
            return error_status("No filter wheel driver configured")
        
        try:
            if self.filter_wheel is None:
                import win32com.client
                self.filter_wheel = win32com.client.Dispatch(self.filter_wheel_driver_id)
            
            if not self.filter_wheel.Connected:
                self.filter_wheel.Connected = True
                self.logger.info(f"Connected to filter wheel: {self.filter_wheel_driver_id}")
            
            return success_status(f"Filter wheel connected: {self.filter_wheel_driver_id}")
        except Exception as e:
            return error_status(f"Failed to connect to filter wheel: {e}")

    def _disconnect_filter_wheel(self) -> CameraStatus:
        """Disconnect from separate filter wheel driver."""
        try:
            if self.filter_wheel and self.filter_wheel.Connected:
                self.filter_wheel.Connected = False
                self.logger.info("Filter wheel disconnected")
            return success_status("Filter wheel disconnected")
        except Exception as e:
            return error_status(f"Failed to disconnect filter wheel: {e}") 