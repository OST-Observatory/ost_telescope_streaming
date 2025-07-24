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
        self.logger = logger or logging.getLogger(__name__)
        self.driver_id = driver_id
        self.camera = None

    def connect(self) -> CameraStatus:
        try:
            import win32com.client
            self.camera = win32com.client.Dispatch(self.driver_id)
            self.camera.Connected = True
            return success_status("ASCOM camera connected")
        except Exception as e:
            return error_status(f"Failed to connect to ASCOM camera: {e}")

    def disconnect(self) -> CameraStatus:
        try:
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
            self.camera.CoolerOn = on
            status = "on" if on else "off"
            return success_status(f"Cooler turned {status}")
        except Exception as e:
            return error_status(f"Failed to turn cooler {'on' if on else 'off'}: {e}")

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
            
            # Log the readings for debugging
            print(f"DEBUG: Temperature readings: {temp_reads}")
            if hasattr(self.camera, 'CoolerPower'):
                print(f"DEBUG: Cooler power readings: {power_reads}")
            if hasattr(self.camera, 'CoolerOn'):
                print(f"DEBUG: Cooler on readings: {cooler_on_reads}")
            
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
            
            print(f"DEBUG: Fresh cooling info - Temp: {info['temperature']}°C, Power: {info['cooler_power']}%, On: {info['cooler_on']}")
            
            return success_status("Fresh cooling information retrieved", data=info)
        except Exception as e:
            return error_status(f"Failed to get fresh cooling info: {e}")

    def has_filter_wheel(self) -> bool:
        return hasattr(self.camera, 'FilterNames')

    def get_filter_names(self) -> CameraStatus:
        if not self.has_filter_wheel():
            return error_status("No filter wheel present")
        try:
            names = list(self.camera.FilterNames)
            return success_status("Filter names retrieved", data=names)
        except Exception as e:
            return error_status(f"Failed to get filter names: {e}")

    def set_filter_position(self, position: int) -> CameraStatus:
        if not self.has_filter_wheel():
            return error_status("No filter wheel present")
        try:
            self.camera.Position = position
            return success_status(f"Filter position set to {position}")
        except Exception as e:
            return error_status(f"Failed to set filter position: {e}")

    def get_filter_position(self) -> CameraStatus:
        if not self.has_filter_wheel():
            return error_status("No filter wheel present")
        try:
            pos = self.camera.Position
            return success_status("Current filter position", data=pos)
        except Exception as e:
            return error_status(f"Failed to get filter position: {e}")

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