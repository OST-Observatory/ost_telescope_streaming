"""Camera image format conversion helpers (to OpenCV)."""

from __future__ import annotations

from typing import Any
import numpy as np
try:
    import cv2  # optional for environments without OpenCV during tests
except Exception:  # pragma: no cover
    cv2 = None

from processing.normalization import normalize_to_uint8


def convert_camera_data_to_opencv(image_data: Any, camera: Any, config: Any, logger: Any = None) -> np.ndarray | None:
    """Convert camera image data (Status or raw) to OpenCV BGR8.

    Handles:
      - Status-like wrappers (uses .data)
      - Bayer debayer decision via camera sensor type or config
      - Orientation fix (transpose long-side vertical)
      - 16-bit to 8-bit normalization for display
    """
    try:
        # Unwrap data if Status-like
        raw_data = image_data.data if hasattr(image_data, 'data') else image_data
        if raw_data is None:
            if logger:
                logger.error("Image data is None")
            return None

        image_array = np.array(raw_data)
        if image_array.size == 0:
            if logger:
                logger.error("Image array is empty")
            return None

        # Determine color
        is_color_camera = False
        bayer_pattern = None
        if hasattr(camera, 'sensor_type'):
            sensor_type = camera.sensor_type
            if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                is_color_camera = True
                bayer_pattern = sensor_type
                if logger:
                    logger.debug(f"Detected color camera with Bayer pattern: {bayer_pattern}")

        if not is_color_camera:
            try:
                camera_config = config.get_camera_config()
                if camera_config.get('auto_debayer', False):
                    debayer_method = camera_config.get('debayer_method', 'RGGB')
                    if debayer_method in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
                        is_color_camera = True
                        bayer_pattern = debayer_method
                        if logger:
                            logger.debug(f"Color camera via config, Bayer: {bayer_pattern}")
            except Exception:
                pass

        # Convert to uint16 for processing consistency
        if image_array.dtype != np.uint16:
            if image_array.dtype in (np.float32, np.float64):
                # Normalize to 16-bit range
                vmin, vmax = image_array.min(), image_array.max()
                if vmax > vmin:
                    image_array = ((image_array - vmin) / (vmax - vmin) * 65535).astype(np.uint16)
                else:
                    image_array = image_array.astype(np.uint16)
            else:
                image_array = image_array.astype(np.uint16)

        # Debayer or grayscale to BGR
        if cv2 is None:
            # Without cv2 we cannot do color conversion; return a safe uint8 grayscale image
            from processing.normalization import normalize_to_uint8
            return normalize_to_uint8(image_array, config, logger)

        if is_color_camera and len(image_array.shape) == 2:
            if bayer_pattern == 'RGGB':
                code = cv2.COLOR_BayerRG2BGR
            elif bayer_pattern == 'GRBG':
                code = cv2.COLOR_BayerGR2BGR
            elif bayer_pattern == 'GBRG':
                code = cv2.COLOR_BayerGB2BGR
            elif bayer_pattern == 'BGGR':
                code = cv2.COLOR_BayerBG2BGR
            else:
                code = cv2.COLOR_BayerRG2BGR
            try:
                result_image = cv2.cvtColor(image_array, code)
            except Exception as e:
                if logger:
                    logger.warning(f"Debayering failed: {e}, fallback to grayscale conversion")
                result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
        else:
            # Non color or already RGB
            if len(image_array.shape) == 2:
                result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            elif len(image_array.shape) == 3:
                if image_array.shape[2] == 4:
                    result_image = cv2.cvtColor(image_array, cv2.COLOR_RGBA2BGR)
                else:
                    result_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            else:
                result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)

        # Orientation correction: long side horizontal
        if len(result_image.shape) == 3:
            h, w = result_image.shape[:2]
        else:
            h, w = result_image.shape
        if h > w:
            result_image = np.transpose(result_image, (1, 0, 2)) if result_image.ndim == 3 else np.transpose(result_image, (1, 0))
            if logger:
                logger.info(f"Image orientation corrected: {(h, w)} -> {result_image.shape[:2]}")

        # Normalize to 8-bit for display
        if result_image.dtype != np.uint8:
            result_image = normalize_to_uint8(result_image, config, logger)

        return result_image
    except Exception as e:
        if logger:
            logger.error(f"Error converting image: {e}")
        return None


