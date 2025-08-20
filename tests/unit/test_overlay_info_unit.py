from overlay.info import (
    calculate_secondary_fov,
    camera_info,
    format_coordinates,
    fov_info,
    secondary_fov_label,
    telescope_info,
)


def test_camera_info_simple():
    s = camera_info(
        {
            "camera_type": "opencv",
            "sensor_width": 23.5,
            "sensor_height": 15.6,
            "pixel_size": 3.76,
            "bit_depth": 16,
        }
    )
    assert "OPENCV" in s
    assert "23.5×15.6mm" in s
    assert "3.76μm" in s
    assert "16bit" in s


def test_telescope_info_simple():
    s = telescope_info(
        {"focal_length": 1000, "aperture": 200, "focal_ratio": 5.0, "type": "Newtonian"}
    )
    assert "200mm" in s and "1000mm" in s and "f/5.0" in s


def test_fov_info_formatting():
    s = fov_info(1.5, 1.0)
    assert "1.50°×1.00°" in s
    assert "90.0'×60.0'" in s


def test_format_coordinates_hms_dms():
    s = format_coordinates(15.0, -30.5)
    assert "RA:" in s and "Dec:" in s


def test_secondary_fov_calculations_and_label_camera():
    cfg = {
        "enabled": True,
        "type": "camera",
        "telescope": {"focal_length": 1000.0, "aperture": 200, "type": "refractor"},
        "camera": {"sensor_width": 10.0, "sensor_height": 5.0},
    }
    w, h = calculate_secondary_fov(cfg)
    assert w > 0 and h > 0
    label = secondary_fov_label(cfg)
    assert "Secondary:" in label


def test_secondary_fov_calculations_and_label_eyepiece():
    cfg = {
        "enabled": True,
        "type": "eyepiece",
        "telescope": {"focal_length": 1000.0, "aperture": 200, "type": "reflector"},
        "eyepiece": {"focal_length": 25.0, "afov": 68.0, "barlow": 1.0, "aspect_ratio": [4, 3]},
    }
    w, h = calculate_secondary_fov(cfg)
    assert w > 0 and h > 0
    label = secondary_fov_label(cfg)
    assert "Secondary:" in label
