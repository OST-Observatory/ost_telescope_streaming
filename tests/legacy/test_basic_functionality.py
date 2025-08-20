#!/usr/bin/env python3
"""
Basic functionality tests for core modules.
"""

from pathlib import Path
import sys

from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np
import pytest

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from tests.common.test_utils import (
    parse_test_args,
    print_test_header,
    setup_test_environment,
)


def test_configuration(config) -> None:
    """Tests the configuration system.
    Returns:
        bool: True on success, False otherwise.
    """
    print("Testing configuration system...")
    print("=" * 40)

    try:
        # Test basic configuration loading
        print(f"Config path: {config.config_path}")
        print(f"Config loaded: {config.config is not None}")

        # Test some configuration values
        fov = config.get("overlay.field_of_view", 1.5)
        print(f"Field of view: {fov}")

        update_interval = config.get("streaming.update_interval", 30)
        print(f"Update interval: {update_interval}")

        # Test mount configuration
        mount_config = config.get_mount_config()
        print(f"Mount driver: {mount_config.get('driver_id', 'Not set')}")

        # Test new configuration sections
        telescope_config = config.get_telescope_config()
        camera_config = config.get_camera_config()
        video_config = config.get_frame_processing_config()
        plate_solve_config = config.get_plate_solve_config()

        print(f"Telescope focal length: {telescope_config.get('focal_length', 'N/A')}mm")
        sw = camera_config.get("sensor_width", "N/A")
        sh = camera_config.get("sensor_height", "N/A")
        print(f"Camera sensor: {sw}mm x {sh}mm")
        print(f"Frame processing enabled: {video_config.get('enabled', True)}")
        print(f"Plate solving enabled: {plate_solve_config.get('auto_solve', False)}")
        print(f"PlateSolve 2 path: {plate_solve_config.get('platesolve2_path', 'Not set')}")

        # Assertions instead of returning booleans
        assert config.config is not None
        assert isinstance(telescope_config, dict)
        assert isinstance(camera_config, dict)
        assert isinstance(video_config, dict)
        assert isinstance(plate_solve_config, dict)

    except Exception as e:
        print(f"✗ Error during configuration test: {e}")
        import traceback

        traceback.print_exc()
        raise AssertionError("Configuration test failed") from e


@pytest.mark.integration
def test_simbad() -> None:
    """Tests SIMBAD queries.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting SIMBAD query...")
    print("=" * 40)

    try:
        from astroquery.simbad import Simbad

        # Test coordinates
        ra = 47.4166
        dec = -15.5384

        print(f"Testing coordinates: RA={ra}°, Dec={dec}°")

        # Configure SIMBAD
        custom_simbad = Simbad()
        custom_simbad.reset_votable_fields()
        custom_simbad.add_votable_fields("ra", "dec", "V", "otype", "main_id")

        # Create center coordinate
        center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")

        # Query SIMBAD
        print("Querying SIMBAD...")
        result = custom_simbad.query_region(center, radius=1.0 * u.deg)

        if result is None or len(result) == 0:
            print("No objects found in SIMBAD query.")
        else:
            print(f"Found {len(result)} objects")
            print(f"Available columns: {result.colnames}")

            # Show first few objects
            print("\nFirst 3 objects:")
            for i, row in enumerate(result[:3]):
                print(f"Object {i+1}:")
                for col in result.colnames:
                    print(f"  {col}: {row[col]}")
                print()

        assert True

    except Exception as e:
        print(f"✗ Error during SIMBAD test: {e}")
        import traceback

        traceback.print_exc()
        pytest.skip(f"SIMBAD test skipped due to error: {e}")


def test_coordinates() -> None:
    """Tests coordinate conversion.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting coordinate conversion...")
    print("=" * 40)

    def skycoord_to_pixel(
        obj_coord: SkyCoord, center_coord: SkyCoord, size_px: tuple[int, int], fov_deg: float
    ) -> tuple[int, int]:
        """Converts sky coordinates to pixel coordinates."""
        try:
            delta_ra = (
                (obj_coord.ra.degree - center_coord.ra.degree)
                * u.deg.to(u.arcmin)
                * np.cos(center_coord.dec.radian)
            )
            delta_dec = (obj_coord.dec.degree - center_coord.dec.degree) * u.deg.to(u.arcmin)

            scale = size_px[0] / (fov_deg * 60)  # arcmin -> pixels

            x = size_px[0] / 2 + delta_ra * scale
            y = size_px[1] / 2 - delta_dec * scale  # Invert Y-axis (Dec up)

            return int(x), int(y)
        except Exception as e:
            raise ValueError(f"Error in coordinate conversion: {e}") from e

    try:
        # Test coordinates
        center_ra = 47.4166
        center_dec = -15.5384
        image_size = (800, 800)
        fov_deg = 1.5

        center_coord = SkyCoord(ra=center_ra * u.deg, dec=center_dec * u.deg, frame="icrs")

        print(f"Center: RA={center_ra}°, Dec={center_dec}°")
        print(f"Image size: {image_size}")
        print(f"Field of view: {fov_deg}°")

        # Test some object coordinates
        test_objects = [
            (center_ra + 0.1, center_dec + 0.1, "Object 1"),
            (center_ra - 0.1, center_dec - 0.1, "Object 2"),
            (center_ra, center_dec, "Center object"),
            (center_ra + 1.0, center_dec + 1.0, "Far object"),
        ]

        for obj_ra, obj_dec, name in test_objects:
            obj_coord = SkyCoord(ra=obj_ra * u.deg, dec=obj_dec * u.deg, frame="icrs")

            try:
                x, y = skycoord_to_pixel(obj_coord, center_coord, image_size, fov_deg)
                print(f"{name}: RA={obj_ra:.4f}°, Dec={obj_dec:.4f}° -> Pixel({x}, {y})")
            except Exception as e:
                print(f"{name}: Error - {e}")

        # Basic sanity assertions
        cx, cy = skycoord_to_pixel(center_coord, center_coord, image_size, fov_deg)
        assert cx == image_size[0] // 2
        assert cy == image_size[1] // 2

    except Exception as e:
        print(f"✗ Error during coordinate test: {e}")
        import traceback

        traceback.print_exc()
        raise AssertionError("Coordinate conversion test failed") from e


def main() -> None:
    """Main function for the Basic Functionality Test."""
    # Parse command line arguments
    args = parse_test_args("Basic Functionality Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("Basic Functionality Test", driver_id, args.config)

    tests = [
        ("Configuration System", lambda: test_configuration(config)),
        ("SIMBAD Query", test_simbad),
        ("Coordinate Conversion", test_coordinates),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            print(f"✓ {test_name} completed")
            passed += 1
        else:
            print(f"✗ {test_name} failed")

    print("\n--- Results ---")
    print(f"Completed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All basic functionality tests passed!")
        print("\n✅ The system is ready for advanced features!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main()
