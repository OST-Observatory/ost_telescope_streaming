"""Utilities to enrich FITS headers from metadata and camera/config sources."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def enrich_header_from_metadata(
    header,  # fits.Header
    frame_details: Dict[str, Any] | None,
    camera: Any,
    config: Any,
    camera_type: str,
    logger: Any,
) -> None:
    """Populate a FITS header with exposure/camera/calibration fields.

    This function mutates the provided header in-place.
    """
    # Exposure
    if frame_details is not None and isinstance(frame_details, dict):
        exposure_time = None
        for key in (
            "exposure_time_s",
            "exposure_time",
            "EXPTIME",
            "ExposureTime",
            "exptime",
            "Exposure",
            "exp_time",
            "ExpTime",
            "EXP",
        ):
            if key in frame_details and frame_details.get(key) is not None:
                exposure_time = _safe_float(frame_details.get(key))
                if exposure_time is not None:
                    header["EXPTIME"] = exposure_time
                    break
    # Fallback to camera/config
    if "EXPTIME" not in header:
        if hasattr(camera, "exposure_time"):
            header["EXPTIME"] = camera.exposure_time
        else:
            camera_config = config.get_camera_config()
            cfg = (
                camera_config.get("ascom", {})
                if camera_type == "ascom"
                else camera_config.get("alpaca", {})
            )
            if cfg.get("exposure_time") is not None:
                header["EXPTIME"] = cfg.get("exposure_time")

    # Gain / Offset / Readout / Binning
    # Gain
    gain = None
    if isinstance(frame_details, dict):
        gain = frame_details.get("gain")
    if gain is not None:
        header["GAIN"] = gain
    elif hasattr(camera, "gain"):
        header["GAIN"] = camera.gain

    # Offset
    offset = None
    if isinstance(frame_details, dict):
        offset = frame_details.get("offset")
    if offset is not None:
        header["OFFSET"] = offset
    elif hasattr(camera, "offset"):
        header["OFFSET"] = camera.offset
    else:
        camera_config = config.get_camera_config()
        for sub in ("ascom", "alpaca"):
            cfg = camera_config.get(sub, {})
            if "offset" in cfg and cfg.get("offset") is not None:
                header["OFFSET"] = cfg.get("offset")
                break

    # Readout mode
    readout = None
    if isinstance(frame_details, dict):
        readout = frame_details.get("readout_mode")
    if readout is not None:
        header["READOUT"] = readout
    elif hasattr(camera, "readout_mode"):
        header["READOUT"] = camera.readout_mode
    else:
        camera_config = config.get_camera_config()
        for sub in ("ascom", "alpaca"):
            cfg = camera_config.get(sub, {})
            if "readout_mode" in cfg and cfg.get("readout_mode") is not None:
                header["READOUT"] = cfg.get("readout_mode")
                break

    # Binning
    binning = None
    if isinstance(frame_details, dict):
        binning = frame_details.get("binning")
    if binning is not None:
        if isinstance(binning, list):
            header["XBINNING"] = binning[0]
            header["YBINNING"] = binning[1] if len(binning) > 1 else binning[0]
        else:
            header["XBINNING"] = binning
            header["YBINNING"] = binning
    elif hasattr(camera, "bin_x") and hasattr(camera, "bin_y"):
        header["XBINNING"] = camera.bin_x
        header["YBINNING"] = camera.bin_y

    # Sensor / optics fields (optional)
    try:
        camera_cfg = config.get_camera_config()
        telescope_cfg = config.get_telescope_config()
        px_um = camera_cfg.get("pixel_size")
        if px_um is not None:
            header["XPIXSZ"] = float(px_um)
            header["YPIXSZ"] = float(px_um)
        sw = camera_cfg.get("sensor_width")
        sh = camera_cfg.get("sensor_height")
        if sw is not None:
            header["SENSWID"] = float(sw)
        if sh is not None:
            header["SENSHGT"] = float(sh)
        fl = telescope_cfg.get("focal_length") if telescope_cfg else None
        if fl is not None:
            header["FOCALLEN"] = float(fl)
    except Exception:
        pass

    # Temperature / cooling
    try:
        if hasattr(camera, "ccdtemperature"):
            header["CCD-TEMP"] = float(camera.ccdtemperature)
        if hasattr(camera, "set_ccd_temperature"):
            tset = camera.set_ccd_temperature
            if tset is not None:
                header["CCD-TSET"] = float(tset)
        if hasattr(camera, "cooler_power"):
            cpwr = camera.cooler_power
            if cpwr is not None:
                header["COOLPOW"] = float(cpwr)
        if hasattr(camera, "cooler_on"):
            header["COOLERON"] = bool(camera.cooler_on)
    except Exception:
        pass

    # Calibration flags
    try:
        if isinstance(frame_details, dict):
            dark_applied = bool(frame_details.get("dark_subtraction_applied", False))
            flat_applied = bool(frame_details.get("flat_correction_applied", False))
            parts = []
            if dark_applied:
                parts.append("DARK")
            if flat_applied:
                parts.append("FLAT")
            header["DARKCOR"] = dark_applied
            header["FLATCOR"] = flat_applied
            header["CALSTAT"] = ",".join(parts) if parts else "NONE"
            if frame_details.get("master_dark_used"):
                try:
                    import os

                    header["MSTDARK"] = os.path.basename(str(frame_details.get("master_dark_used")))
                except Exception:
                    header["MSTDARK"] = str(frame_details.get("master_dark_used"))
            if frame_details.get("master_flat_used"):
                try:
                    import os

                    header["MSTFLAT"] = os.path.basename(str(frame_details.get("master_flat_used")))
                except Exception:
                    header["MSTFLAT"] = str(frame_details.get("master_flat_used"))
            # Capture correlation and timing
            if "capture_id" in frame_details:
                header["CAPTURE"] = int(frame_details["capture_id"])
            if "capture_started_at" in frame_details:
                header["CAPSTRT"] = str(frame_details["capture_started_at"])
            if "capture_finished_at" in frame_details:
                header["CAPEND"] = str(frame_details["capture_finished_at"])
            if "save_duration_ms" in frame_details:
                header["SAVEMS"] = float(frame_details["save_duration_ms"])
    except Exception:
        pass

    # Coordinates and pier side
    try:
        ra_deg: Optional[float] = None
        dec_deg: Optional[float] = None

        # Helper to parse from details
        def _get_coords_from_details(
            details: Dict[str, Any]
        ) -> Tuple[Optional[float], Optional[float]]:
            ra_local: Optional[float] = None
            dec_local: Optional[float] = None
            if "coordinates" in details and isinstance(details["coordinates"], (tuple, list)):
                try:
                    ra_local = _safe_float(details["coordinates"][0])
                    dec_local = _safe_float(details["coordinates"][1])
                except Exception:
                    ra_local = None
                    dec_local = None
            for key in ("ra_deg", "ra"):
                if key in details and details.get(key) is not None:
                    try:
                        ra_local = _safe_float(details.get(key))
                    except Exception:
                        pass
            for key in ("dec_deg", "dec"):
                if key in details and details.get(key) is not None:
                    try:
                        dec_local = _safe_float(details.get(key))
                    except Exception:
                        pass
            # RA could be in hours
            if ra_local is not None and 0.0 <= ra_local <= 24.0:
                ra_local = ra_local * 15.0
            return ra_local, dec_local

        if isinstance(frame_details, dict):
            ra_deg, dec_deg = _get_coords_from_details(frame_details)

        # Try to query the mount (ASCOM) for coordinates and pier side regardless of camera type
        # Use results only to fill missing values, and to set PIERSIDE if not present
        try:
            from drivers.ascom.mount import ASCOMMount

            mount = ASCOMMount(config=config, logger=logger)
            status = mount.get_mount_status()
            if getattr(status, "is_success", False) and isinstance(status.data, dict):
                data = status.data
                if ra_deg is None:
                    ra_val = data.get("ra_deg")
                    ra_deg = _safe_float(ra_val)
                if dec_deg is None:
                    dec_val = data.get("dec_deg")
                    dec_deg = _safe_float(dec_val)
                # Pier side
                if data.get("side_of_pier") is not None and "PIERSIDE" not in header:
                    header["PIERSIDE"] = str(data.get("side_of_pier"))
        except Exception:
            # Silently ignore on non-Windows or when ASCOM not available
            pass

        # If coordinates available, write both numeric and sexagesimal
        def _format_ra_sexagesimal(ra_degrees: float) -> str:
            # Convert degrees to hours:min:sec string
            ra_hours_total = (ra_degrees % 360.0) / 15.0
            hours = int(math.floor(ra_hours_total))
            minutes_total = (ra_hours_total - hours) * 60.0
            minutes = int(math.floor(minutes_total))
            seconds = (minutes_total - minutes) * 60.0
            return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

        def _format_dec_sexagesimal(dec_degrees: float) -> str:
            sign = "+" if dec_degrees >= 0 else "-"
            dec_abs = abs(dec_degrees)
            degrees = int(math.floor(dec_abs))
            minutes_total = (dec_abs - degrees) * 60.0
            minutes = int(math.floor(minutes_total))
            seconds = (minutes_total - minutes) * 60.0
            return f"{sign}{degrees:02d}:{minutes:02d}:{seconds:05.2f}"

        # If user already provided pier side in metadata, keep it / set it
        if isinstance(frame_details, dict):
            for k in ("pierside", "pier_side", "side_of_pier"):
                if k in frame_details and frame_details.get(k) is not None:
                    header["PIERSIDE"] = str(frame_details.get(k))
                    break

        if ra_deg is not None and dec_deg is not None:
            # Numeric degrees
            header["RA"] = float(ra_deg)
            header["DEC"] = float(dec_deg)
            # Sexagesimal strings commonly used
            header["OBJCTRA"] = _format_ra_sexagesimal(float(ra_deg))
            header["OBJCTDEC"] = _format_dec_sexagesimal(float(dec_deg))
    except Exception:
        pass
