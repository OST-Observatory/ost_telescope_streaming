#!/usr/bin/env python3
"""
FrameWriter: saves frames to FITS or display formats with proper headers and orientation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from capture.frame import Frame
import numpy as np
from processing.format_conversion import convert_camera_data_to_opencv
from processing.orientation import enforce_long_side_horizontal
from status import error_status, success_status
from utils.fits_utils import enrich_header_from_metadata
from utils.status_utils import unwrap_status


class FrameWriter:
    def __init__(self, config, logger=None, camera=None, camera_type: str = "opencv") -> None:
        self.config = config
        self.logger = logger
        self.camera = camera
        self.camera_type = camera_type
        # Orientation/scaling policy from config
        try:
            fp_cfg = self.config.get_frame_processing_config()
            self.orientation_policy = str(fp_cfg.get("orientation", "long_side_horizontal")).lower()
            norm_cfg = fp_cfg.get("normalization", {})
            self.display_normalization = str(norm_cfg.get("method", "zscale")).lower()
            self.display_contrast = float(norm_cfg.get("contrast", 0.15))
        except Exception:
            self.orientation_policy = "long_side_horizontal"
            self.display_normalization = "zscale"
            self.display_contrast = 0.15

    def save(self, frame: Any, filename: str, metadata: Optional[Dict[str, Any]] = None):
        suffix = Path(filename).suffix.lower()
        if suffix in (".fit", ".fits"):
            return self.save_fits(frame, filename, metadata)
        return self.save_image(frame, filename)

    def save_image(self, frame: Any, filename: str):
        try:
            try:
                import cv2
            except Exception as e:
                return error_status(f"OpenCV not available for image saving: {e}")

            if hasattr(frame, "data"):
                frame_data = frame.data
            else:
                frame_data = frame

            # If data is a Frame object, use its color image for display
            if isinstance(frame_data, Frame):
                frame_data = frame_data.data

            if self.camera_type in ["alpaca", "ascom"]:
                frame_np = convert_camera_data_to_opencv(
                    frame_data, self.camera, self.config, self.logger
                )
            else:
                frame_np = frame_data

            if frame_np is None:
                return error_status("Failed to convert camera image to OpenCV format")

            if not isinstance(frame_np, np.ndarray):
                frame_np = np.array(frame_np)

            # Enforce orientation for display if configured
            if self.orientation_policy == "long_side_horizontal":
                from processing.orientation import enforce_long_side_horizontal

                frame_np, _ = enforce_long_side_horizontal(frame_np)

            # Normalize to uint8 for display
            if frame_np.dtype != np.uint8:
                try:
                    from processing.normalization import normalize_to_uint8

                    frame_np = normalize_to_uint8(frame_np, self.config, self.logger)
                except Exception:
                    if frame_np.dtype in [np.float32, np.float64]:
                        vmin = float(np.min(frame_np))
                        vmax = float(np.max(frame_np))
                        if vmax > vmin:
                            frame_np = ((frame_np - vmin) / (vmax - vmin) * 255).astype(np.uint8)
                        else:
                            frame_np = frame_np.astype(np.uint8)
                    else:
                        frame_np = frame_np.astype(np.uint8)

            os.makedirs(os.path.dirname(filename), exist_ok=True)
            success = cv2.imwrite(filename, frame_np)
            if success:
                return success_status("Image file saved", data=filename)
            return error_status("Failed to save image file")
        except Exception as e:
            return error_status(f"Error saving image file: {e}")

    def save_fits(self, frame: Any, filename: str, metadata: Optional[Dict[str, Any]] = None):
        try:
            try:
                import astropy.io.fits as fits
                from astropy.time import Time
            except ImportError as e:
                return error_status(f"Astropy not available for FITS saving: {e}")

            image_data, frame_details = unwrap_status(frame)
            frame_obj: Optional[Frame] = None
            if isinstance(image_data, Frame):
                frame_obj = image_data
                # Prefer green channel for FITS if available
                image_data = (
                    frame_obj.green_channel
                    if frame_obj.green_channel is not None
                    else frame_obj.data
                )
            if metadata:
                # Merge/override provided metadata
                try:
                    frame_details = {**(frame_details or {}), **metadata}
                except Exception:
                    frame_details = frame_details or metadata

            if image_data is None:
                return error_status("No image data found in frame")

            if not isinstance(image_data, np.ndarray):
                try:
                    image_data = np.array(image_data)
                except Exception as conv_e:
                    return error_status(f"Failed to convert to numpy array: {conv_e}")

            image_data, rotated = enforce_long_side_horizontal(image_data)

            # Convert to uint16 for FITS compatibility
            if image_data.dtype != np.uint16:
                if image_data.dtype in [np.float32, np.float64]:
                    vmin = float(np.min(image_data))
                    vmax = float(np.max(image_data))
                    if vmax > vmin:
                        image_data = ((image_data - vmin) / (vmax - vmin) * 65535).astype(np.uint16)
                    else:
                        image_data = image_data.astype(np.uint16)
                else:
                    image_data = image_data.astype(np.uint16)
            else:
                image_data = image_data.astype(np.uint16, copy=False)

            # Header
            header = fits.Header()
            header["NAXIS"] = image_data.ndim
            header["NAXIS1"] = image_data.shape[1] if image_data.ndim >= 2 else 1
            header["NAXIS2"] = image_data.shape[0] if image_data.ndim >= 2 else 1
            if image_data.ndim == 3:
                header["NAXIS3"] = image_data.shape[2]
            header["BITPIX"] = 16
            header["BZERO"] = 0
            header["BSCALE"] = 1
            header["CAMERA"] = self.camera_type.capitalize()
            if hasattr(self.camera, "name"):
                header["CAMNAME"] = self.camera.name

            # Enrich from metadata/config/camera
            enrich_header_from_metadata(
                header, frame_details, self.camera, self.config, self.camera_type, self.logger
            )

            # Cooling details if available
            try:
                if hasattr(self.camera, "ccdtemperature"):
                    header["CCD-TEMP"] = float(self.camera.ccdtemperature)
                if hasattr(self.camera, "cooler_power"):
                    cpwr = self.camera.cooler_power
                    if cpwr is not None:
                        header["COOLPOW"] = float(cpwr)
                if hasattr(self.camera, "cooler_on"):
                    header["COOLERON"] = bool(self.camera.cooler_on)
            except Exception:
                pass

            header["DATE-OBS"] = Time.now().isot

            hdu = fits.PrimaryHDU(image_data, header=header)
            # Measure write time for telemetry
            import time as _t

            t0 = _t.perf_counter()
            hdu.writeto(filename, overwrite=True)
            t1 = _t.perf_counter()
            try:
                if isinstance(frame_details, dict):
                    frame_details["save_duration_ms"] = (t1 - t0) * 1000.0
            except Exception:
                pass
            if os.path.exists(filename):
                return success_status("FITS file saved", data=filename)
            return error_status("FITS file was not created")
        except Exception as e:
            return error_status(f"Error saving FITS file: {e}")
