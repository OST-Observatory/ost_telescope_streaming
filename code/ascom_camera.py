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

    def debayer(self, img_array: Any, pattern: str = 'RGGB') -> CameraStatus:
        try:
            import cv2
            import numpy as np
            if pattern == 'RGGB':
                rgb = cv2.cvtColor(np.array(img_array, dtype=np.uint16), cv2.COLOR_BAYER_RG2RGB)
            # Weitere Patterns nach Bedarf
            else:
                return error_status(f"Unsupported Bayer pattern: {pattern}")
            return success_status("Debayering successful", data=rgb)
        except Exception as e:
            return error_status(f"Debayering failed: {e}") 