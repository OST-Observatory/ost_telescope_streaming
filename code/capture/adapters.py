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
        # Structured debug: exposure start
        try:
            import logging

            logging.getLogger(__name__).debug(
                f"Alpaca: start_exposure exp={exposure_time_s} light={light}"
            )
        except Exception:
            pass
        self._cam.start_exposure(exposure_time_s, light=light)

    @property
    def image_ready(self) -> bool:
        return bool(getattr(self._cam, "image_ready", False))

    def get_image_array(self) -> Any:
        return self._cam.get_image_array()

    # Convenience: wait until image_ready or timeout
    def wait_for_image_ready(self, timeout_s: float) -> bool:
        import time

        start = time.time()
        while not self.image_ready:
            time.sleep(0.1)
            if time.time() - start > timeout_s:
                return False
        try:
            import logging

            logging.getLogger(__name__).debug(f"Alpaca: image ready in {time.time() - start:.2f}s")
        except Exception:
            pass
        return True

    @property
    def gain(self) -> Optional[float]:
        return getattr(self._cam, "gain", None)

    @gain.setter
    def gain(self, value: float) -> None:
        self._cam.gain = value

    @property
    def offset(self) -> Optional[int]:
        return getattr(self._cam, "offset", None)

    @offset.setter
    def offset(self, value: int) -> None:
        self._cam.offset = value

    @property
    def readout_mode(self) -> Optional[int]:
        return getattr(self._cam, "readout_mode", None)

    @readout_mode.setter
    def readout_mode(self, value: int) -> None:
        self._cam.readout_mode = value

    @property
    def bin_x(self) -> Optional[int]:
        return getattr(self._cam, "bin_x", None)

    @bin_x.setter
    def bin_x(self, value: int) -> None:
        self._cam.bin_x = value

    @property
    def bin_y(self) -> Optional[int]:
        return getattr(self._cam, "bin_y", None)

    @bin_y.setter
    def bin_y(self, value: int) -> None:
        self._cam.bin_y = value

    def is_color_camera(self) -> bool:
        return bool(self._cam.is_color_camera())

    @property
    def sensor_type(self) -> Optional[str]:
        return getattr(self._cam, "sensor_type", None)

    @property
    def camera_x_size(self) -> int:
        return int(getattr(self._cam, "camera_x_size", 0))

    @property
    def camera_y_size(self) -> int:
        return int(getattr(self._cam, "camera_y_size", 0))

    @property
    def name(self) -> Optional[str]:
        return getattr(self._cam, "name", None)

    # --- Cooling passthrough (needed by CoolingManager) ---
    @property
    def can_set_ccd_temperature(self) -> bool:
        return bool(getattr(self._cam, "can_set_ccd_temperature", False))

    @property
    def can_get_cooler_power(self) -> bool:
        return bool(getattr(self._cam, "can_get_cooler_power", False))

    @property
    def ccd_temperature(self) -> Optional[float]:
        return getattr(self._cam, "ccd_temperature", None)

    @property
    def set_ccd_temperature(self) -> Optional[float]:
        return getattr(self._cam, "set_ccd_temperature", None)

    @set_ccd_temperature.setter
    def set_ccd_temperature(self, value: float) -> None:
        self._cam.set_ccd_temperature = value

    @property
    def cooler_on(self) -> Optional[bool]:
        return getattr(self._cam, "cooler_on", None)

    @cooler_on.setter
    def cooler_on(self, value: bool) -> None:
        self._cam.cooler_on = value

    @property
    def cooler_power(self) -> Optional[float]:
        return getattr(self._cam, "cooler_power", None)

    @property
    def heat_sink_temperature(self) -> Optional[float]:
        return getattr(self._cam, "heat_sink_temperature", None)


class AscomCameraAdapter(CameraInterface):
    def __init__(self, camera) -> None:
        self._cam = camera

    def connect(self) -> Any:
        return self._cam.connect()

    def disconnect(self) -> None:
        self._cam.disconnect()

    def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
        # ASCOM wrapper exposes expose() and get_image() pattern; start_exposure not used
        try:
            import logging

            logging.getLogger(__name__).debug(
                "ASCOM: expose exp=%s gain=%s offset=%s readout=%s",
                exposure_time_s,
                getattr(self._cam, "gain", None),
                getattr(self._cam, "offset", None),
                getattr(self._cam, "readout_mode", None),
            )
        except Exception:
            pass
        self._cam.expose(
            exposure_time_s,
            getattr(self._cam, "gain", None),
            1,
            getattr(self._cam, "offset", None),
            getattr(self._cam, "readout_mode", None),
        )

    @property
    def image_ready(self) -> bool:
        # Fallback: assume ready after expose+get_image used by caller
        return True

    def get_image_array(self) -> Any:
        status = self._cam.get_image()
        return status.data if hasattr(status, "data") else None

    def wait_for_image_ready(self, timeout_s: float) -> bool:
        # ASCOM pattern: expose + short wait before get_image
        import logging
        import time

        t0 = time.time()
        time.sleep(min(max(timeout_s, 0.0), timeout_s))
        try:
            logging.getLogger(__name__).debug(
                f"ASCOM: image assumed ready after {time.time() - t0:.2f}s"
            )
        except Exception:
            pass
        return True

    @property
    def gain(self) -> Optional[float]:
        return getattr(self._cam, "gain", None)

    @gain.setter
    def gain(self, value: float) -> None:
        self._cam.gain = value

    @property
    def offset(self) -> Optional[int]:
        return getattr(self._cam, "offset", None)

    @offset.setter
    def offset(self, value: int) -> None:
        self._cam.offset = value

    @property
    def readout_mode(self) -> Optional[int]:
        return getattr(self._cam, "readout_mode", None)

    @readout_mode.setter
    def readout_mode(self, value: int) -> None:
        self._cam.readout_mode = value

    @property
    def bin_x(self) -> Optional[int]:
        return getattr(self._cam, "bin_x", None)

    @bin_x.setter
    def bin_x(self, value: int) -> None:
        self._cam.bin_x = value

    @property
    def bin_y(self) -> Optional[int]:
        return getattr(self._cam, "bin_y", None)

    @bin_y.setter
    def bin_y(self, value: int) -> None:
        self._cam.bin_y = value

    def is_color_camera(self) -> bool:
        if hasattr(self._cam, "is_color_camera"):
            return bool(self._cam.is_color_camera())
        return False

    @property
    def sensor_type(self) -> Optional[str]:
        return getattr(self._cam, "sensor_type", None)

    @property
    def camera_x_size(self) -> int:
        return int(getattr(getattr(self._cam, "camera", None), "CameraXSize", 0))

    @property
    def camera_y_size(self) -> int:
        return int(getattr(getattr(self._cam, "camera", None), "CameraYSize", 0))

    @property
    def name(self) -> Optional[str]:
        return getattr(self._cam, "name", None)


class OpenCVCameraAdapter(CameraInterface):
    """Adapter for OpenCV cameras to match CameraInterface for live view and snapshots."""

    def __init__(self, cap) -> None:
        self._cap = cap
        self._last_frame = None

    def connect(self) -> Any:
        return True

    def disconnect(self) -> None:
        try:
            if self._cap:
                self._cap.release()
        except Exception:
            pass

    def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
        # For OpenCV, we simulate immediate exposure and grab a frame
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._last_frame = frame

    @property
    def image_ready(self) -> bool:
        return self._last_frame is not None

    def get_image_array(self) -> Any:
        img = self._last_frame
        self._last_frame = None
        return img

    def wait_for_image_ready(self, timeout_s: float) -> bool:
        return self._last_frame is not None

    @property
    def gain(self) -> Optional[float]:
        return None

    @gain.setter
    def gain(self, value: float) -> None:
        pass

    @property
    def offset(self) -> Optional[int]:
        return None

    @offset.setter
    def offset(self, value: int) -> None:
        pass

    @property
    def readout_mode(self) -> Optional[int]:
        return None

    @readout_mode.setter
    def readout_mode(self, value: int) -> None:
        pass

    @property
    def bin_x(self) -> Optional[int]:
        return None

    @bin_x.setter
    def bin_x(self, value: int) -> None:
        pass

    @property
    def bin_y(self) -> Optional[int]:
        return None

    @bin_y.setter
    def bin_y(self, value: int) -> None:
        pass

    def is_color_camera(self) -> bool:
        return True

    @property
    def sensor_type(self) -> Optional[str]:
        return None

    @property
    def camera_x_size(self) -> int:
        try:
            return int(self._cap.get(3))  # CAP_PROP_FRAME_WIDTH
        except Exception:
            return 0

    @property
    def camera_y_size(self) -> int:
        try:
            return int(self._cap.get(4))  # CAP_PROP_FRAME_HEIGHT
        except Exception:
            return 0

    @property
    def name(self) -> Optional[str]:
        return "OpenCV Camera"
