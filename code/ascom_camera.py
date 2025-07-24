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
            self.camera.SetCCDTemperature = target_temp
            return success_status(f"Cooling set to {target_temp}°C")
        except Exception as e:
            return error_status(f"Failed to set cooling: {e}")

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