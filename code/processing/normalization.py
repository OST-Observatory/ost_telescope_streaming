"""Image normalization strategies for display/preview pipelines."""

from __future__ import annotations

from typing import Any

import numpy as np


def scale_16bit_to_8bit(image_16bit: np.ndarray) -> np.ndarray:
    """Histogram-based scaling from 16-bit to 8-bit.

    Uses 1% and 99% percentiles; falls back to min/max if necessary.
    """
    try:
        # Calculate histogram percentiles
        hist, bins = np.histogram(image_16bit.flatten(), bins=256, range=(0, 65535))
        cumulative = np.cumsum(hist)
        total = cumulative[-1]
        lower_idx = np.searchsorted(cumulative, total * 0.01)
        upper_idx = np.searchsorted(cumulative, total * 0.99)
        lower = bins[lower_idx] if lower_idx < len(bins) else 0
        upper = bins[upper_idx] if upper_idx < len(bins) else 65535
        if upper <= lower:
            lower = int(image_16bit.min())
            upper = int(image_16bit.max())
            if upper <= lower:
                lower, upper = 0, 65535
        rng = upper - lower
        if rng > 0:
            out = ((image_16bit.astype(np.float32) - lower) / rng) * 255.0
        else:
            out = (image_16bit / 256.0).astype(np.float32)
        return np.clip(out, 0, 255).astype(np.uint8)
    except Exception:
        return (image_16bit / 256).astype(np.uint8)


def normalize_to_uint8(image: np.ndarray, config: Any, logger: Any = None) -> np.ndarray:
    """Normalize image (2D/3D) to uint8 using config-driven method.

    Supported methods:
      - zscale (default): astropy ZScaleInterval(contrast)
      - hist: histogram/percentile-based scaling
    """
    method = "zscale"
    contrast = 0.15
    try:
        norm_cfg = config.get_frame_processing_config().get("normalization", {})
        method = str(norm_cfg.get("method", "zscale")).lower()
        contrast = float(norm_cfg.get("contrast", 0.15))
    except Exception:
        pass

    if method == "zscale":
        try:
            from astropy.visualization import ImageNormalize, ZScaleInterval

            def zscale_channel(ch: np.ndarray) -> np.ndarray:
                norm = ImageNormalize(
                    ch.astype(np.float32), interval=ZScaleInterval(contrast=contrast)
                )
                arr = norm(ch.astype(np.float32))
                return np.clip(arr * 255.0, 0, 255).astype(np.uint8)

            if image.ndim == 2:
                return zscale_channel(image)
            if image.ndim == 3 and image.shape[2] in (3, 4):
                out = np.empty_like(image, dtype=np.uint8)
                for c in range(image.shape[2]):
                    out[:, :, c] = zscale_channel(image[:, :, c])
                return out
            # Fallback to hist if shapes unexpected
            method = "hist"
        except Exception as e:
            if logger:
                logger.debug(f"ZScale normalization failed, falling back to hist: {e}")
            method = "hist"

    # Histogram/percentile fallback
    if method in ("hist", "histogram", "percentile"):
        if image.ndim == 2:
            img16 = image.astype(np.uint16) if image.dtype != np.uint16 else image
            return scale_16bit_to_8bit(img16)
        if image.ndim == 3 and image.shape[2] in (3, 4):
            out = np.empty_like(image, dtype=np.uint8)
            for c in range(image.shape[2]):
                ch = image[:, :, c]
                img16 = ch.astype(np.uint16) if ch.dtype != np.uint16 else ch
                out[:, :, c] = scale_16bit_to_8bit(img16)
            return out
        return (image / 256).astype(np.uint8)

    # Final fallback
    return (image / 256).astype(np.uint8)
