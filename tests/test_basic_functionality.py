#!/usr/bin/env python3
"""
Consolidated test script for basic functionality.
Tests configuration, SIMBAD queries, and coordinate conversion.
"""

import sys
import os
import argparse
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
from pathlib import Path

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from test_utils import (
    setup_logging,
    get_test_config,
    parse_test_args,
    setup_test_environment,
    print_test_header,
    print_test_result
)

def test_configuration(config) -> bool:
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
        fov = config.get('overlay.field_of_view', 1.5)
        print(f"Field of view: {fov}")
        
        update_interval = config.get('streaming.update_interval', 30)
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
        print(f"Camera sensor: {camera_config.get('sensor_width', 'N/A')}mm x {camera_config.get('sensor_height', 'N/A')}mm")
        print(f"Frame processing enabled: {video_config.get('enabled', True)}")
        print(f"Plate solving enabled: {plate_solve_config.get('auto_solve', False)}")
        print(f"PlateSolve 2 path: {plate_solve_config.get('platesolve2_path', 'Not set')}")
        
        print("✓ Configuration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Error during configuration test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simbad() -> bool:
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
        custom_simbad.add_votable_fields('ra', 'dec', 'V', 'otype', 'main_id')
        
        # Create center coordinate
        center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs')
        
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
        
        print("✓ SIMBAD test completed!")
        return True
        
    except Exception as e:
        print(f"✗ Error during SIMBAD test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_coordinates() -> bool:
    """Tests coordinate conversion.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting coordinate conversion...")
    print("=" * 40)
    
    def skycoord_to_pixel(obj_coord: SkyCoord, center_coord: SkyCoord, size_px: tuple[int, int], fov_deg: float) -> tuple[int, int]:
        """Converts sky coordinates to pixel coordinates."""
        try:
            delta_ra = (obj_coord.ra.degree - center_coord.ra.degree) * \
                u.deg.to(u.arcmin) * np.cos(center_coord.dec.radian)
            delta_dec = (obj_coord.dec.degree - center_coord.dec.degree) * u.deg.to(u.arcmin)

            scale = size_px[0] / (fov_deg * 60)  # arcmin -> pixels

            x = size_px[0] / 2 + delta_ra * scale
            y = size_px[1] / 2 - delta_dec * scale  # Invert Y-axis (Dec up)

            return int(x), int(y)
        except Exception as e:
            raise ValueError(f"Error in coordinate conversion: {e}")
    
    try:
        # Test coordinates
        center_ra = 47.4166
        center_dec = -15.5384
        image_size = (800, 800)
        fov_deg = 1.5
        
        center_coord = SkyCoord(ra=center_ra * u.deg, dec=center_dec * u.deg, frame='icrs')
        
        print(f"Center: RA={center_ra}°, Dec={center_dec}°")
        print(f"Image size: {image_size}")
        print(f"Field of view: {fov_deg}°")
        
        # Test some object coordinates
        test_objects = [
            (center_ra + 0.1, center_dec + 0.1, "Object 1"),
            (center_ra - 0.1, center_dec - 0.1, "Object 2"),
            (center_ra, center_dec, "Center object"),
            (center_ra + 1.0, center_dec + 1.0, "Far object")
        ]
        
        for obj_ra, obj_dec, name in test_objects:
            obj_coord = SkyCoord(ra=obj_ra * u.deg, dec=obj_dec * u.deg, frame='icrs')
            
            try:
                x, y = skycoord_to_pixel(obj_coord, center_coord, image_size, fov_deg)
                print(f"{name}: RA={obj_ra:.4f}°, Dec={obj_dec:.4f}° -> Pixel({x}, {y})")
            except Exception as e:
                print(f"{name}: Error - {e}")
        
        print("✓ Coordinate conversion test completed!")
        return True
        
    except Exception as e:
        print(f"✗ Error during coordinate test: {e}")
        import traceback
        traceback.print_exc()
        return False

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
    
    print(f"\n--- Results ---")
    print(f"Completed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All basic functionality tests passed!")
        print("\n✅ The system is ready for advanced features!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main() 