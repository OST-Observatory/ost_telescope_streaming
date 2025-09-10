"""Image normalization strategies for display/preview pipelines."""

from __future__ import annotations

from typing import Any, Optional, Tuple

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


def normalize_to_uint8(
    image: np.ndarray, config: Any, logger: Any = None, override_method: Optional[str] = None
) -> np.ndarray:
    """Normalize image (2D/3D) to uint8 using config-driven method.

    Supported methods:
      - none: no additional stretching (safe 16->8 mapping)
      - linear: min/max or percentile window
      - gamma: linear + gamma correction
      - log: logarithmic stretch
      - asinh: astronomical asinh stretch
      - zscale: astropy ZScaleInterval(contrast)
      - hist: histogram/percentile-based scaling
      - planetary: ROI-weighted scaling for bright bodies
      - moon: planetary-like with extra midtone/shadow emphasis
    """

    # Helpers
    def _to_uint8_no_scale(img: np.ndarray) -> np.ndarray:
        if img.dtype == np.uint8:
            return img
        if img.dtype == np.uint16:
            return (img >> 8).astype(np.uint8)
        # Float or other types
        arr = img.astype(np.float32)
        # Assume [0,1] range if float-like
        if np.issubdtype(img.dtype, np.floating):
            arr = np.clip(arr, 0.0, 1.0) * 255.0
        else:
            arr = arr / 256.0
        return np.clip(arr, 0, 255).astype(np.uint8)

    def _compute_percentiles(
        arr: np.ndarray, black_p: float, white_p: float
    ) -> Tuple[float, float]:
        try:
            lo = float(np.percentile(arr, black_p))
            hi = float(np.percentile(arr, white_p))
            if hi <= lo:
                # Fallback to min/max
                lo = float(np.min(arr))
                hi = float(np.max(arr))
            if hi <= lo:
                lo, hi = 0.0, 1.0
            return lo, hi
        except Exception:
            return 0.0, 1.0

    def _linear_scale_to_uint8(ch: np.ndarray, black: float, white: float) -> np.ndarray:
        rng = float(white - black)
        if rng <= 0.0 or not np.isfinite(rng):
            return _to_uint8_no_scale(ch)
        arr = (ch.astype(np.float32) - float(black)) / rng
        arr = np.clip(arr, 0.0, 1.0)
        return (arr * 255.0).astype(np.uint8)

    def _linear_to_unit(ch: np.ndarray, black: float, white: float) -> np.ndarray:
        rng = float(white - black)
        if rng <= 0.0 or not np.isfinite(rng):
            arr = ch.astype(np.float32)
            if arr.size == 0:
                return arr
            # Normalize by max to avoid NaN
            m = float(np.max(arr))
            return (arr / m) if m > 0 else arr
        arr = (ch.astype(np.float32) - float(black)) / rng
        return np.clip(arr, 0.0, 1.0)

    def _apply_gamma01(unit_arr: np.ndarray, gamma: float) -> np.ndarray:
        try:
            g = float(gamma)
            g = 1e-6 if g <= 0 else g
            return np.power(unit_arr, g)
        except Exception:
            return unit_arr

    def _apply_log(unit_arr: np.ndarray, log_gain: float) -> np.ndarray:
        try:
            a = float(log_gain)
            a = max(a, 1.0)
            return np.log1p(a * unit_arr) / np.log1p(a)
        except Exception:
            return unit_arr

    def _apply_asinh(unit_arr: np.ndarray, soften: float) -> np.ndarray:
        try:
            s = float(soften)
            s = max(s, 1e-6)
            return np.arcsinh(s * unit_arr) / np.arcsinh(s)
        except Exception:
            return unit_arr

    # Read config
    method = "zscale"
    contrast = 0.15
    per_channel = False
    preserve_black_point = True
    clip_black = 1.0
    clip_white = 99.5
    lin_min = None
    lin_max = None
    gamma_value = 0.9
    asinh_soften = 12.0
    log_gain = 1000.0
    planetary_cfg = {
        "center_fraction": 0.2,
        "white_percentile": 99.8,
        "black_percentile": 3.0,
        "auto_roi": False,
        "auto_roi_sigma": 4.0,
        "roi_min_area_frac": 0.02,
    }
    moon_cfg = {
        "midtone_boost": 1.25,
        "shadows_boost": 1.1,
        "white_percentile": 99.7,
        "black_percentile": 2.0,
    }

    try:
        norm_cfg = config.get_frame_processing_config().get("normalization", {})
        method = str(norm_cfg.get("method", "zscale")).lower()
        contrast = float(norm_cfg.get("contrast", 0.15))
        per_channel = bool(norm_cfg.get("per_channel", False))
        preserve_black_point = bool(norm_cfg.get("preserve_black_point", True))
        cp = norm_cfg.get("clip_percent", {}) or {}
        clip_black = float(cp.get("black", 1.0))
        clip_white = float(cp.get("white", 99.5))
        lw = norm_cfg.get("linear_window", {}) or {}
        lin_min = lw.get("min", None)
        lin_max = lw.get("max", None)
        gamma_value = float(norm_cfg.get("gamma_value", 0.9))
        asinh_soften = float(norm_cfg.get("asinh_soften", 12.0))
        log_gain = float(norm_cfg.get("log_gain", 1000.0))
        # Merge nested cfgs
        p = norm_cfg.get("planetary", {}) or {}
        for k in planetary_cfg:
            if k in p:
                planetary_cfg[k] = p[k]
        m = norm_cfg.get("moon", {}) or {}
        for k in moon_cfg:
            if k in m:
                moon_cfg[k] = m[k]
    except Exception:
        pass

    # Optional override (e.g., auto planetary/moon from processor)
    if override_method:
        try:
            ov = str(override_method).lower()
            if ov in {
                "none",
                "linear",
                "gamma",
                "log",
                "asinh",
                "zscale",
                "hist",
                "planetary",
                "moon",
            }:
                method = ov
        except Exception:
            pass

    # Keep for config compatibility; behavior is enforced by clipping to [0,1]
    _ = preserve_black_point

    # Prepare channel handling helpers
    def _iterate_channels(img: np.ndarray):
        if img.ndim == 2:
            yield None, img
        elif img.ndim == 3 and img.shape[2] in (3, 4):
            for c in range(img.shape[2]):
                yield c, img[:, :, c]
        else:
            yield None, img

    def _merge_channels(template: np.ndarray, channels: list[np.ndarray]) -> np.ndarray:
        if template.ndim == 2:
            return channels[0]
        out = np.empty_like(template, dtype=np.uint8)
        for c in range(template.shape[2]):
            out[:, :, c] = channels[c]
        return out

    # Method: none
    if method == "none":
        if image.ndim == 2:
            return _to_uint8_no_scale(image)
        if image.ndim == 3 and image.shape[2] in (3, 4):
            parts = []
            for _, ch in _iterate_channels(image):
                parts.append(_to_uint8_no_scale(ch))
            return _merge_channels(image, parts)
        return _to_uint8_no_scale(image)

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

    # Linear based methods (linear/gamma/log/asinh)
    if method in ("linear", "gamma", "log", "asinh"):
        # Compute scaling bounds
        if per_channel:
            parts_pc: list[np.ndarray] = []
            for _, ch in _iterate_channels(image):
                if lin_min is not None and lin_max is not None:
                    b, w = float(lin_min), float(lin_max)
                else:
                    b, w = _compute_percentiles(ch, clip_black, clip_white)
                unit = _linear_to_unit(ch, b, w)
                if method == "gamma":
                    unit = _apply_gamma01(unit, gamma_value)
                elif method == "log":
                    unit = _apply_log(unit, log_gain)
                elif method == "asinh":
                    unit = _apply_asinh(unit, asinh_soften)
                parts_pc.append((np.clip(unit, 0.0, 1.0) * 255.0).astype(np.uint8))
            return _merge_channels(image, parts_pc)
        else:
            # Shared window on luminance/mean
            ref = image if image.ndim == 2 else image.mean(axis=2)
            if lin_min is not None and lin_max is not None:
                b, w = float(lin_min), float(lin_max)
            else:
                b, w = _compute_percentiles(ref, clip_black, clip_white)
            parts_shared: list[np.ndarray] = []
            for _, ch in _iterate_channels(image):
                unit = _linear_to_unit(ch, b, w)
                if method == "gamma":
                    unit = _apply_gamma01(unit, gamma_value)
                elif method == "log":
                    unit = _apply_log(unit, log_gain)
                elif method == "asinh":
                    unit = _apply_asinh(unit, asinh_soften)
                parts_shared.append((np.clip(unit, 0.0, 1.0) * 255.0).astype(np.uint8))
            return _merge_channels(image, parts_shared)

    # Planetary mode: ROI-weighted percentiles
    if method == "planetary":
        cf = float(planetary_cfg["center_fraction"])  # default 0.2
        wp = float(planetary_cfg["white_percentile"])  # 99.8
        bp = float(planetary_cfg["black_percentile"])  # 3.0
        auto_roi = bool(planetary_cfg["auto_roi"])  # False
        roi_sigma = float(planetary_cfg["auto_roi_sigma"])  # 4.0
        min_area_frac = float(planetary_cfg["roi_min_area_frac"])  # 0.02

        gray = image if image.ndim == 2 else image.mean(axis=2)
        H, W = gray.shape[:2]
        roi_mask = np.zeros_like(gray, dtype=bool)

        if auto_roi:
            arr = gray.astype(np.float32)
            mu = float(np.mean(arr))
            sigma = float(np.std(arr))
            thresh = mu + roi_sigma * sigma
            roi_mask = arr > thresh
            # Ensure minimum area
            if roi_mask.mean() < min_area_frac:
                auto_roi = False

        if not auto_roi:
            # Center crop mask
            fh = max(int(H * cf), 1)
            fw = max(int(W * cf), 1)
            y0 = (H - fh) // 2
            x0 = (W - fw) // 2
            roi_mask[y0 : y0 + fh, x0 : x0 + fw] = True

        # Percentiles: white from ROI, black from global
        white_ref = gray[roi_mask]
        black_ref = gray
        b, _ = _compute_percentiles(black_ref, bp, 100.0)
        _, w = _compute_percentiles(white_ref, 0.0, wp)

        parts_planetary: list[np.ndarray] = []
        for _, ch in _iterate_channels(image):
            unit = _linear_to_unit(ch, b, w)
            parts_planetary.append((np.clip(unit, 0.0, 1.0) * 255.0).astype(np.uint8))
        return _merge_channels(image, parts_planetary)

    # Moon mode: planetary with midtone/shadows emphasis
    if method == "moon":
        wp = float(moon_cfg["white_percentile"])  # 99.7
        bp = float(moon_cfg["black_percentile"])  # 2.0
        midtone_boost = float(moon_cfg["midtone_boost"])  # 1.25
        shadows_boost = float(moon_cfg["shadows_boost"])  # 1.1

        gray = image if image.ndim == 2 else image.mean(axis=2)
        b, w = _compute_percentiles(gray, bp, wp)

        def _moon_curve(unit: np.ndarray) -> np.ndarray:
            # Asinh then gamma-like midtone boost, small shadow lift
            arr = _apply_asinh(unit, asinh_soften)
            # Midtone boost (>1 brightens midtones)
            if midtone_boost > 1.0:
                arr = np.power(arr, 1.0 / midtone_boost)
            # Shadows boost: small linear lift near zero
            if shadows_boost != 1.0:
                arr = np.clip(arr * shadows_boost, 0.0, 1.0)
            # Optional extra gamma from config, applied at end
            if gamma_value and gamma_value > 0:
                arr = _apply_gamma01(arr, gamma_value)
            return np.clip(arr, 0.0, 1.0)

        parts_moon: list[np.ndarray] = []
        for _, ch in _iterate_channels(image):
            unit = _linear_to_unit(ch, b, w)
            unit = _moon_curve(unit)
            parts_moon.append((unit * 255.0).astype(np.uint8))
        return _merge_channels(image, parts_moon)

    # Final fallback
    return _to_uint8_no_scale(image)
