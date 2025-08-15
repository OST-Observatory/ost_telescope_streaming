"""Camera image format conversion helpers (to OpenCV)."""

from __future__ import annotations

from typing import Any, Tuple

import numpy as np

try:
    import cv2  # optional for environments without OpenCV during tests
except Exception:  # pragma: no cover
    cv2 = None

from processing.normalization import normalize_to_uint8


def _detect_color_and_pattern(camera: Any, config: Any) -> Tuple[bool, str | None]:
    """Detect if camera is color and return Bayer pattern if available.

    Returns (is_color, bayer_pattern|None)
    """
    is_color_camera = False
    bayer_pattern: str | None = None

    def _get_any(obj: Any, names: list[str]) -> Any:
        for name in names:
            try:
                return getattr(obj, name)
            except Exception:
                continue
        return None

    sensor_type_attr = _get_any(
        camera, ["sensor_type", "SensorType", "cfa_pattern", "BayerPattern"]
    )
    if isinstance(sensor_type_attr, str):
        upper = sensor_type_attr.upper()
        if upper in ["RGGB", "GRBG", "GBRG", "BGGR"]:
            is_color_camera = True
            bayer_pattern = upper

    if not is_color_camera:
        color_hint = _get_any(camera, ["is_color", "IsColor", "colour", "Color"])
        try:
            is_color_camera = bool(color_hint)
        except Exception:
            pass

    try:
        camera_cfg = config.get_camera_config()
        frame_cfg = config.get_frame_processing_config()
        if not is_color_camera and str(camera_cfg.get("type", "")).lower() == "color":
            is_color_camera = True
        if bayer_pattern is None:
            debayer_method = frame_cfg.get("debayer_method", "RGGB")
            if isinstance(debayer_method, str) and debayer_method in [
                "RGGB",
                "GRBG",
                "GBRG",
                "BGGR",
            ]:
                bayer_pattern = debayer_method
    except Exception:
        pass

    return is_color_camera, bayer_pattern


def debayer_to_color_and_green(
    image_data: Any, camera: Any, config: Any, logger: Any = None
) -> Tuple[np.ndarray | None, np.ndarray | None, str | None]:
    """Debayer once and return (color16 BGR, green16, bayer_pattern).

    If conversion is not possible, returns (grayscale, same grayscale, None).
    """
    try:
        image_array = np.array(image_data)
        if image_array.ndim == 0 or image_array.size == 0:
            return None, None, None

        # Promote to uint16 for consistent demosaic
        if image_array.dtype != np.uint16:
            if image_array.dtype in (np.float32, np.float64):
                vmin, vmax = float(np.min(image_array)), float(np.max(image_array))
                if vmax > vmin:
                    image_array = ((image_array - vmin) / (vmax - vmin) * 65535).astype(np.uint16)
                else:
                    image_array = image_array.astype(np.uint16)
            else:
                image_array = image_array.astype(np.uint16)

        is_color, pattern = _detect_color_and_pattern(camera, config)

        if cv2 is None:
            # No OpenCV: cannot demosaic properly; return grayscale for both
            gray8 = normalize_to_uint8(image_array, config, logger)
            gray16 = gray8.astype(np.uint16) * 257
            return gray16, gray16, None

        if is_color and image_array.ndim == 2:
            if pattern == "RGGB":
                code = cv2.COLOR_BayerRG2BGR
            elif pattern == "GRBG":
                code = cv2.COLOR_BayerGR2BGR
            elif pattern == "GBRG":
                code = cv2.COLOR_BayerGB2BGR
            elif pattern == "BGGR":
                code = cv2.COLOR_BayerBG2BGR
            else:
                code = cv2.COLOR_BayerRG2BGR
            try:
                color16 = cv2.cvtColor(image_array, code)
            except Exception as e:
                if logger:
                    logger.warning(f"Debayer failed: {e}; using grayscale")
                color16 = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            green16 = color16[:, :, 1].copy()
            return color16, green16, pattern

        # Already 3-channel or mono
        if image_array.ndim == 3 and image_array.shape[2] >= 3:
            color16 = image_array[:, :, :3].astype(np.uint16, copy=False)
            green16 = color16[:, :, 1].copy()
            return color16, green16, pattern
        else:
            gray = image_array.astype(np.uint16, copy=False)
            color16 = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if cv2 is not None else gray
            return color16, gray.copy(), pattern
    except Exception:
        return None, None, None


def convert_camera_data_to_opencv(
    image_data: Any, camera: Any, config: Any, logger: Any = None
) -> np.ndarray | None:
    """Convert camera image data (Status or raw) to OpenCV BGR8.

    Handles:
      - Status-like wrappers (uses .data)
      - Bayer debayer decision via camera sensor type or config
      - Orientation fix (transpose long-side vertical)
      - 16-bit to 8-bit normalization for display
    """
    try:
        # Unwrap data if Status-like
        raw_data = image_data.data if hasattr(image_data, "data") else image_data
        if raw_data is None:
            if logger:
                logger.error("Image data is None")
            return None

        image_array = np.array(raw_data)
        if image_array.size == 0:
            if logger:
                logger.error("Image array is empty")
            return None

        # Determine color / Bayer pattern from camera and config
        is_color_camera = False
        bayer_pattern = None

        # Helper to normalize various property names from drivers
        def _get_any(obj: Any, names: list[str]) -> Any:
            for name in names:
                try:
                    return getattr(obj, name)
                except Exception:
                    continue
            return None

        # Probe camera attributes (handles Alpaca/ASCOM naming variants)
        sensor_type_attr = _get_any(
            camera, ["sensor_type", "SensorType", "cfa_pattern", "BayerPattern"]
        )
        if isinstance(sensor_type_attr, str):
            upper = sensor_type_attr.upper()
            if upper in ["RGGB", "GRBG", "GBRG", "BGGR"]:
                is_color_camera = True
                bayer_pattern = upper
        # Generic color hints
        if not is_color_camera:
            color_hint = _get_any(camera, ["is_color", "IsColor", "colour", "Color"])
            try:
                is_color_camera = bool(color_hint)
            except Exception:
                pass

        # Probe config for color type and debayer method (correct section: frame_processing)
        try:
            camera_cfg = config.get_camera_config()
            frame_cfg = config.get_frame_processing_config()
            if not is_color_camera and str(camera_cfg.get("type", "")).lower() == "color":
                is_color_camera = True
            # If no pattern found, take method from frame config
            if bayer_pattern is None:
                debayer_method = frame_cfg.get("debayer_method", "RGGB")
                if isinstance(debayer_method, str) and debayer_method in [
                    "RGGB",
                    "GRBG",
                    "GBRG",
                    "BGGR",
                ]:
                    bayer_pattern = debayer_method
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
            return normalize_to_uint8(image_array, config, logger)

        if is_color_camera and len(image_array.shape) == 2:
            if bayer_pattern == "RGGB":
                code = cv2.COLOR_BayerRG2BGR
            elif bayer_pattern == "GRBG":
                code = cv2.COLOR_BayerGR2BGR
            elif bayer_pattern == "GBRG":
                code = cv2.COLOR_BayerGB2BGR
            elif bayer_pattern == "BGGR":
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
                elif image_array.shape[2] == 3:
                    result_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                else:
                    # Unknown channel layout; convert each channel to uint8 and stack
                    ch = [
                        normalize_to_uint8(image_array[:, :, i], config, logger)
                        for i in range(image_array.shape[2])
                    ]
                    result_image = np.dstack(ch)
            else:
                result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)

        # Orientation correction: long side horizontal
        if len(result_image.shape) == 3:
            h, w = result_image.shape[:2]
        else:
            h, w = result_image.shape
        if h > w:
            result_image = (
                np.transpose(result_image, (1, 0, 2))
                if result_image.ndim == 3
                else np.transpose(result_image, (1, 0))
            )
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
