from overlay.projection import skycoord_to_pixel_with_rotation


def test_center_maps_to_center_for_various_sizes():
    sizes = [(320, 240), (800, 600), (1024, 768)]
    for width, height in sizes:
        x, y = skycoord_to_pixel_with_rotation(
            obj_ra_deg=10.0,
            obj_dec_deg=20.0,
            center_ra_deg=10.0,
            center_dec_deg=20.0,
            size_px=(width, height),
            fov_width_deg=2.0,
            fov_height_deg=1.0,
            position_angle_deg=0.0,
            is_flipped=False,
            ra_increases_left=True,
        )
        assert x == width // 2
        assert y == height // 2


def test_flip_mirrors_x_coordinate():
    width, height = 800, 600
    x1, y1 = skycoord_to_pixel_with_rotation(
        10.1, 20.0, 10.0, 20.0, (width, height), 2.0, 1.5, 0.0, False, True
    )
    x2, y2 = skycoord_to_pixel_with_rotation(
        10.1, 20.0, 10.0, 20.0, (width, height), 2.0, 1.5, 0.0, True, True
    )
    assert y1 == y2
    assert x2 == width - x1


def test_position_angle_rotates_quadrants():
    width, height = 640, 480
    x0, y0 = skycoord_to_pixel_with_rotation(
        10.0, 20.1, 10.0, 20.0, (width, height), 2.0, 1.5, 0.0, False, True
    )
    x90, y90 = skycoord_to_pixel_with_rotation(
        10.0, 20.1, 10.0, 20.0, (width, height), 2.0, 1.5, 90.0, False, True
    )
    assert y0 < height // 2
    assert x90 > width // 2
