#!/usr/bin/env python3
"""
Camera adapters wrapping existing ASCOM/Alpaca camera classes to the common interface.
"""

from __future__ import annotations

from typing import Any, Optional

from .interface import CameraInterface


class AlpacaCameraAdapter(CameraInterface):
    def __init__(self, camera) -> None:
        self._cam = camera

    def connect(self) -> Any:
        return self._cam.connect()

    def disconnect(self) -> None:
        self._cam.disconnect()

    def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
        self._cam.start_exposure(exposure_time_s, light=light)

    @property
    def image_ready(self) -> bool:
        return bool(getattr(self._cam, 'image_ready', False))

    def get_image_array(self) -> Any:
        return self._cam.get_image_array()

    @property
    def gain(self) -> Optional[float]:
        return getattr(self._cam, 'gain', None)

    @gain.setter
    def gain(self, value: float) -> None:
        setattr(self._cam, 'gain', value)

    @property
    def offset(self) -> Optional[int]:
        return getattr(self._cam, 'offset', None)

    @offset.setter
    def offset(self, value: int) -> None:
        setattr(self._cam, 'offset', value)

    @property
    def readout_mode(self) -> Optional[int]:
        return getattr(self._cam, 'readout_mode', None)

    @readout_mode.setter
    def readout_mode(self, value: int) -> None:
        setattr(self._cam, 'readout_mode', value)

    @property
    def bin_x(self) -> Optional[int]:
        return getattr(self._cam, 'bin_x', None)

    @bin_x.setter
    def bin_x(self, value: int) -> None:
        setattr(self._cam, 'bin_x', value)

    @property
    def bin_y(self) -> Optional[int]:
        return getattr(self._cam, 'bin_y', None)

    @bin_y.setter
    def bin_y(self, value: int) -> None:
        setattr(self._cam, 'bin_y', value)

    def is_color_camera(self) -> bool:
        return bool(self._cam.is_color_camera())

    @property
    def sensor_type(self) -> Optional[str]:
        return getattr(self._cam, 'sensor_type', None)

    @property
    def camera_x_size(self) -> int:
        return int(getattr(self._cam, 'camera_x_size', 0))

    @property
    def camera_y_size(self) -> int:
        return int(getattr(self._cam, 'camera_y_size', 0))

    @property
    def name(self) -> Optional[str]:
        return getattr(self._cam, 'name', None)


class AscomCameraAdapter(CameraInterface):
    def __init__(self, camera) -> None:
        self._cam = camera

    def connect(self) -> Any:
        return self._cam.connect()

    def disconnect(self) -> None:
        self._cam.disconnect()

    def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
        # ASCOM wrapper exposes expose() and get_image() pattern; start_exposure not used
        self._cam.expose(exposure_time_s, getattr(self._cam, 'gain', None), 1, getattr(self._cam, 'offset', None), getattr(self._cam, 'readout_mode', None))

    @property
    def image_ready(self) -> bool:
        # Fallback: assume ready after expose+get_image used by caller
        return True

    def get_image_array(self) -> Any:
        status = self._cam.get_image()
        return status.data if hasattr(status, 'data') else None

    @property
    def gain(self) -> Optional[float]:
        return getattr(self._cam, 'gain', None)

    @gain.setter
    def gain(self, value: float) -> None:
        setattr(self._cam, 'gain', value)

    @property
    def offset(self) -> Optional[int]:
        return getattr(self._cam, 'offset', None)

    @offset.setter
    def offset(self, value: int) -> None:
        setattr(self._cam, 'offset', value)

    @property
    def readout_mode(self) -> Optional[int]:
        return getattr(self._cam, 'readout_mode', None)

    @readout_mode.setter
    def readout_mode(self, value: int) -> None:
        setattr(self._cam, 'readout_mode', value)

    @property
    def bin_x(self) -> Optional[int]:
        return getattr(self._cam, 'bin_x', None)

    @bin_x.setter
    def bin_x(self, value: int) -> None:
        setattr(self._cam, 'bin_x', value)

    @property
    def bin_y(self) -> Optional[int]:
        return getattr(self._cam, 'bin_y', None)

    @bin_y.setter
    def bin_y(self, value: int) -> None:
        setattr(self._cam, 'bin_y', value)

    def is_color_camera(self) -> bool:
        if hasattr(self._cam, 'is_color_camera'):
            return bool(self._cam.is_color_camera())
        return False

    @property
    def sensor_type(self) -> Optional[str]:
        return getattr(self._cam, 'sensor_type', None)

    @property
    def camera_x_size(self) -> int:
        return int(getattr(getattr(self._cam, 'camera', None), 'CameraXSize', 0))

    @property
    def camera_y_size(self) -> int:
        return int(getattr(getattr(self._cam, 'camera', None), 'CameraYSize', 0))

    @property
    def name(self) -> Optional[str]:
        return getattr(self._cam, 'name', None)
