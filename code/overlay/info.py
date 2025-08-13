from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def format_coordinates(ra_deg: float, dec_deg: float) -> str:
    from astropy.coordinates import Angle

    ra_angle = Angle(ra_deg, unit="deg")
    dec_angle = Angle(dec_deg, unit="deg")
    ra_str = ra_angle.to_string(unit="hourangle", sep=":", precision=2)
    dec_str = dec_angle.to_string(unit="deg", sep=":", precision=1)
    return f"RA: {ra_str} | Dec: {dec_str}"


def telescope_info(telescope_config: dict) -> str:
    focal_length = telescope_config.get("focal_length", "Unknown")
    aperture = telescope_config.get("aperture", "Unknown")
    focal_ratio = telescope_config.get("focal_ratio", "Unknown")
    telescope_type = telescope_config.get("type", "Unknown")
    return f"Telescope: {aperture}mm {telescope_type} (f/{focal_ratio}, {focal_length}mm FL)"


def camera_info(camera_config: dict) -> str:
    camera_type = camera_config.get("camera_type", "Unknown")
    sensor_width = camera_config.get("sensor_width", "Unknown")
    sensor_height = camera_config.get("sensor_height", "Unknown")
    pixel_size = camera_config.get("pixel_size", "Unknown")
    bit_depth = camera_config.get("bit_depth", "Unknown")
    return (
        "Camera: "
        f"{str(camera_type).upper()} ("
        f"{sensor_width}×{sensor_height}mm, "
        f"{pixel_size}μm, {bit_depth}bit)"
    )


def fov_info(fov_width_deg: float, fov_height_deg: float) -> str:
    fov_width_arcmin = fov_width_deg * 60.0
    fov_height_arcmin = fov_height_deg * 60.0
    return (
        f"FOV: {fov_width_deg:.2f}°×{fov_height_deg:.2f}° ("
        f"{fov_width_arcmin:.1f}'×{fov_height_arcmin:.1f}')"
    )


def cooling_info(cooling_status: Optional[Dict[str, Any]], enabled: bool) -> str:
    if not enabled:
        return "Cooling: disabled"
    if not cooling_status or not isinstance(cooling_status, dict):
        return "Cooling: n/a"
    try:
        temp = cooling_status.get("ccd_temperature")
        target = cooling_status.get("target_temperature")
        power = cooling_status.get("cooler_power")
        cooler_on = cooling_status.get("cooler_on")
        parts = []
        if temp is not None:
            parts.append(f"T={float(temp):.1f}°C")
        if target is not None:
            parts.append(f"→{float(target):.1f}°C")
        if power is not None:
            parts.append(f"P={float(power):.0f}%")
        if cooler_on is not None:
            parts.append("ON" if cooler_on else "OFF")
        return "Cooling: " + (" ".join(parts) if parts else "n/a")
    except Exception:
        return "Cooling: n/a"


def calculate_secondary_fov(config: dict) -> Tuple[float, float]:
    import numpy as np

    if not config.get("enabled", False):
        return 0.0, 0.0
    fov_type = config.get("type", "camera")
    telescope_config = config.get("telescope", {})
    focal_length = telescope_config.get("focal_length", 1000.0)
    if fov_type == "camera":
        camera = config.get("camera", {})
        sensor_w = float(camera.get("sensor_width", 10.0))
        sensor_h = float(camera.get("sensor_height", 10.0))
        return (sensor_w / focal_length) * (180.0 / np.pi), (sensor_h / focal_length) * (
            180.0 / np.pi
        )
    if fov_type == "eyepiece":
        eyepiece = config.get("eyepiece", {})
        eyepiece_fl = float(eyepiece.get("focal_length", 25.0))
        afov = float(eyepiece.get("afov", 68.0))
        barlow = float(eyepiece.get("barlow", 1.0))
        effective_fl = float(focal_length) * barlow
        true_fov_deg = afov * (eyepiece_fl / effective_fl)
        aspect = eyepiece.get("aspect_ratio", [1.0, 1.0])
        ar_w, ar_h = float(aspect[0]), float(aspect[1])
        norm = max(ar_w, ar_h)
        return true_fov_deg * (ar_w / norm), true_fov_deg * (ar_h / norm)
    return 0.0, 0.0


def secondary_fov_label(config: dict) -> str:
    if not config.get("enabled", False):
        return ""
    fov_type = config.get("type", "camera")
    telescope_config = config.get("telescope", {})
    aperture = telescope_config.get("aperture", 200)
    telescope_type = telescope_config.get("type", "reflector")
    if fov_type == "camera":
        camera = config.get("camera", {})
        sensor_width = camera.get("sensor_width", 10.0)
        sensor_height = camera.get("sensor_height", 10.0)
        return f"Secondary: {aperture}mm {telescope_type} + {sensor_width}×{sensor_height}mm sensor"
    if fov_type == "eyepiece":
        eyepiece = config.get("eyepiece", {})
        eyepiece_fl = eyepiece.get("focal_length", 25)
        afov = eyepiece.get("afov", 68)
        return f"Secondary: {aperture}mm {telescope_type} + {eyepiece_fl}mm ({afov}° AFOV)"
    return "Secondary FOV"
