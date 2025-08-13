from __future__ import annotations

import os
import sys

# Ensure we can import from the project 'code' directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from overlay.projection import skycoord_to_pixel_with_rotation  # noqa: E402


def test_projection_center_maps_to_center_pixel():
    width, height = 800, 600
    x, y = skycoord_to_pixel_with_rotation(
        obj_ra_deg=10.0,
        obj_dec_deg=20.0,
        center_ra_deg=10.0,
        center_dec_deg=20.0,
        size_px=(width, height),
        fov_width_deg=2.0,
        fov_height_deg=1.5,
        position_angle_deg=0.0,
        is_flipped=False,
        ra_increases_left=True,
    )
    assert x == width // 2
    assert y == height // 2


def test_projection_ra_offset_with_ra_increases_left():
    width, height = 800, 600
    # Object to the right in RA (smaller RA if ra_increases_left=True should map to +x)
    x_left_true, _ = skycoord_to_pixel_with_rotation(
        obj_ra_deg=9.9,
        obj_dec_deg=20.0,
        center_ra_deg=10.0,
        center_dec_deg=20.0,
        size_px=(width, height),
        fov_width_deg=2.0,
        fov_height_deg=1.5,
        position_angle_deg=0.0,
        is_flipped=False,
        ra_increases_left=True,
    )
    x_left_false, _ = skycoord_to_pixel_with_rotation(
        obj_ra_deg=9.9,
        obj_dec_deg=20.0,
        center_ra_deg=10.0,
        center_dec_deg=20.0,
        size_px=(width, height),
        fov_width_deg=2.0,
        fov_height_deg=1.5,
        position_angle_deg=0.0,
        is_flipped=False,
        ra_increases_left=False,
    )
    # With ra_increases_left=True we expect the point to move to the right compared to False
    assert x_left_true > width // 2
    assert x_left_false < width // 2


def test_projection_flip_mirrors_x():
    width, height = 800, 600
    x_no_flip, y_no_flip = skycoord_to_pixel_with_rotation(
        10.1, 20.0, 10.0, 20.0, (width, height), 2.0, 1.5, 0.0, False, True
    )
    x_flip, y_flip = skycoord_to_pixel_with_rotation(
        10.1, 20.0, 10.0, 20.0, (width, height), 2.0, 1.5, 0.0, True, True
    )
    assert y_no_flip == y_flip
    assert x_flip == width - x_no_flip


def test_projection_position_angle_rotates_coordinates():
    width, height = 800, 600
    # Object slightly above center in Dec; with PA=90 deg, it should shift in +x
    x_pa0, y_pa0 = skycoord_to_pixel_with_rotation(
        10.0, 20.1, 10.0, 20.0, (width, height), 2.0, 1.5, 0.0, False, True
    )
    x_pa90, y_pa90 = skycoord_to_pixel_with_rotation(
        10.0, 20.1, 10.0, 20.0, (width, height), 2.0, 1.5, 90.0, False, True
    )
    assert y_pa0 < height // 2  # above center
    assert x_pa90 > width // 2  # rotated into +x direction
