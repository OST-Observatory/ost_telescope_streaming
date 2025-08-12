#!/usr/bin/env python3
"""
Camera adapter interface (Protocol) to unify different camera backends.
"""

from __future__ import annotations

from typing import Protocol, Optional, Tuple, Any


class CameraInterface(Protocol):
    """Abstract interface that camera adapters should implement."""

    # Connection
    def connect(self) -> Any:  # Status-like object
        ...

    def disconnect(self) -> None:
        ...

    # Exposure
    def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
        ...

    @property
    def image_ready(self) -> bool:
        ...

    def get_image_array(self) -> Any:
        ...

    # Properties / controls (optional on some cameras)
    @property
    def gain(self) -> Optional[float]:
        ...

    @gain.setter
    def gain(self, value: float) -> None:
        ...

    @property
    def offset(self) -> Optional[int]:
        ...

    @offset.setter
    def offset(self, value: int) -> None:
        ...

    @property
    def readout_mode(self) -> Optional[int]:
        ...

    @readout_mode.setter
    def readout_mode(self, value: int) -> None:
        ...

    @property
    def bin_x(self) -> Optional[int]:
        ...

    @bin_x.setter
    def bin_x(self, value: int) -> None:
        ...

    @property
    def bin_y(self) -> Optional[int]:
        ...

    @bin_y.setter
    def bin_y(self, value: int) -> None:
        ...

    # Capabilities / info
    def is_color_camera(self) -> bool:
        ...

    @property
    def sensor_type(self) -> Optional[str]:
        ...

    @property
    def camera_x_size(self) -> int:
        ...

    @property
    def camera_y_size(self) -> int:
        ...

    @property
    def name(self) -> Optional[str]:
        ...
