"""
Live frame stacking service.

Provides median/mean accumulation with optional sigma-clipping and (later) alignment.
This is a skeleton for integration with VideoProcessor capture pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import threading
import time
from typing import List, Optional

import numpy as np


@dataclass
class StackSnapshot:
    image_uint8: Optional[np.ndarray]
    image_uint16: Optional[np.ndarray]
    frame_count: int
    started_at: float
    updated_at: float
    output_path_png: Optional[Path]
    output_path_fits: Optional[Path]


class FrameStacker:
    def __init__(
        self,
        output_dir: Path,
        method: str = "median",
        sigma_clip_enabled: bool = True,
        sigma: float = 3.0,
        max_frames: int = 100,
        max_integration_s: int = 0,
        align: str = "astroalign",
        write_interval_s: int = 10,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.method = method
        self.sigma_clip_enabled = sigma_clip_enabled
        self.sigma = float(sigma)
        self.max_frames = int(max_frames)
        self.max_integration_s = int(max_integration_s)
        self.align = align
        self.write_interval_s = int(write_interval_s)
        self.logger = logger or logging.getLogger(__name__)

        self._lock = threading.RLock()
        self._frames: List[np.ndarray] = []  # for median
        self._sum: Optional[np.ndarray] = None  # for mean
        self._count: int = 0
        self._started_at: float = time.time()
        self._last_write_at: float = 0.0
        self._last_snapshot: Optional[StackSnapshot] = None
        self._ref_gray: Optional[np.ndarray] = None

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        with self._lock:
            self._frames = []
            self._sum = None
            self._count = 0
            self._started_at = time.time()
            self._last_snapshot = None

    def add_frame(self, frame_uint8_or16: np.ndarray) -> None:
        """Add a frame to the stack. Frame expected as uint8 or uint16 mono/color."""
        if frame_uint8_or16 is None:
            return
        with self._lock:
            arr = frame_uint8_or16
            if arr.dtype == np.uint8:
                arr_f = arr.astype(np.float32)
            elif arr.dtype == np.uint16:
                arr_f = (arr.astype(np.float32) / 65535.0) * 255.0
            else:
                arr_f = arr.astype(np.float32)

            # Optional alignment using astroalign; robust to rotation
            if self.align == "astroalign":
                try:
                    arr_f = self._align_to_reference(arr_f)
                except Exception as e:
                    self.logger.debug(f"Alignment failed, using unaligned frame: {e}")

            if self.method == "median":
                self._frames.append(arr_f)
                if self.max_frames > 0 and len(self._frames) > self.max_frames:
                    self._frames.pop(0)
            else:
                if self._sum is None:
                    self._sum = np.zeros_like(arr_f, dtype=np.float32)
                self._sum += arr_f
                self._count += 1
                if self.max_frames > 0 and self._count > self.max_frames:
                    # simple rollover: reset when exceeding cap (median path retains last N)
                    self._sum = arr_f.copy()
                    self._count = 1

    def _compose_stack(self) -> Optional[np.ndarray]:
        with self._lock:
            if self.method == "median":
                if not self._frames:
                    return None
                stack = np.stack(self._frames, axis=0)
                if self.sigma_clip_enabled and stack.shape[0] >= 3:
                    med = np.median(stack, axis=0)
                    mad = np.median(np.abs(stack - med), axis=0) + 1e-6
                    z = np.abs(stack - med) / (1.4826 * mad)
                    mask = z <= self.sigma
                    # fallback to median where all rejected
                    masked = np.where(mask, stack, np.nan)
                    comp = np.nanmedian(masked, axis=0)
                    comp = np.where(np.isnan(comp), med, comp)
                else:
                    comp = np.median(stack, axis=0)
                return np.clip(comp, 0, 255).astype(np.float32)
            else:
                if self._sum is None or self._count == 0:
                    return None
                comp = self._sum / float(self._count)
                return np.clip(comp, 0, 255).astype(np.float32)

    def get_snapshot(self) -> Optional[StackSnapshot]:
        comp = self._compose_stack()
        if comp is None:
            return None
        img8 = np.clip(comp, 0, 255).astype(np.uint8)
        img16 = (comp * 257.0).clip(0, 65535).astype(np.uint16)  # approx scale
        with self._lock:
            return StackSnapshot(
                image_uint8=img8,
                image_uint16=img16,
                frame_count=(len(self._frames) if self.method == "median" else self._count),
                started_at=self._started_at,
                updated_at=time.time(),
                output_path_png=None,
                output_path_fits=None,
            )

    # Internals
    def _to_gray(self, arr_f: np.ndarray) -> np.ndarray:
        if arr_f.ndim == 2:
            return arr_f
        if arr_f.ndim == 3 and arr_f.shape[2] in (3, 4):
            return arr_f[..., :3].mean(axis=2)
        return arr_f if arr_f.ndim == 2 else arr_f.reshape(arr_f.shape[0], arr_f.shape[1])

    def _align_to_reference(self, arr_f: np.ndarray) -> np.ndarray:
        try:
            import astroalign as aa
        except Exception:
            return arr_f

        gray = self._to_gray(arr_f)
        if self._ref_gray is None:
            self._ref_gray = gray.copy()
            return arr_f

        try:
            transf, (src_list, dst_list) = aa.find_transform(gray, self._ref_gray)
        except Exception:
            # If feature detection fails (too few stars), refresh reference occasionally
            self._ref_gray = gray.copy()
            return arr_f

        try:
            aligned = aa.apply_transform(transf, arr_f, self._ref_gray.shape)
            return aligned.astype(np.float32)
        except Exception:
            return arr_f

    # Persistence
    def write_snapshot(
        self, base_name: str, write_png: bool = True, write_fits: bool = True
    ) -> Optional[StackSnapshot]:
        from PIL import Image

        try:
            from astropy.io import fits
        except Exception:
            fits = None

        snap = self.get_snapshot()
        if snap is None:
            return None

        ts_end = time.strftime("%Y%m%d_%H%M%S", time.localtime(snap.updated_at))
        out_png = self.output_dir / f"{base_name}_{ts_end}.png"
        out_fits = self.output_dir / f"{base_name}_{ts_end}.fits"

        if write_png and snap.image_uint8 is not None:
            tmp = out_png.with_suffix(".tmp.png")
            Image.fromarray(snap.image_uint8).save(tmp)
            tmp.replace(out_png)
            snap.output_path_png = out_png

        if write_fits and snap.image_uint16 is not None and fits is not None:
            tmp = out_fits.with_suffix(".tmp.fits")
            hdu = fits.PrimaryHDU(snap.image_uint16)
            hdr = hdu.header
            hdr["NFRAMES"] = snap.frame_count
            hdr["STACKST"] = (self._started_at, "Stack started at epoch seconds")
            hdr["STACKEND"] = (snap.updated_at, "Stack ended at epoch seconds")
            hdul = fits.HDUList([hdu])
            hdul.writeto(tmp, overwrite=True)
            tmp.replace(out_fits)
            snap.output_path_fits = out_fits

        with self._lock:
            self._last_snapshot = snap
        return snap
