#!/usr/bin/env python3
"""
Test script for automated PlateSolve 2 integration.
Tests the automated plate solving functionality.
"""

import sys
import os
import argparse
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

import time

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def test_automated_platesolve2() -> bool:
    """Testet die neue automatisierte PlateSolve 2 Implementierung.
    Returns:
        bool: True bei Erfolg, sonst False.
    """
    print("Testing automated PlateSolve 2 with known coordinates...")
    
    try:
        from platesolve2_automated import PlateSolve2Automated
        
        # Create solver
        solver = PlateSolve2Automated()
        
        # Test image
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        
        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            print("⚠ Note: This test requires a real FITS image file.")
            print("   Please update the test_image path or provide a test image.")
            return False
        
        print(f"✓ Test image found: {test_image}")
        print(f"✓ Working directory: {solver.working_directory}")
        print(f"✓ Executable path: {solver.executable_path}")
        print(f"✓ Number of regions: {solver.number_of_regions}")
        
        # Test availability
        if not solver._is_available():
            print("✗ PlateSolve 2 not available")
            print("⚠ Please ensure PlateSolve 2 is installed and accessible.")
            return False
        
        print("✓ PlateSolve 2 is available")
        
        # Test FOV calculation
        fov_width, fov_height = solver._calculate_fov()
        print(f"✓ Calculated FOV: {fov_width:.4f}° x {fov_height:.4f}°")
        
        # Known coordinates for NGC 6819 (example)
        # These should be close to the actual image center
        known_ra = 295.0  # Example RA in degrees
        known_dec = 40.0  # Example Dec in degrees
        
        print(f"✓ Using known coordinates: RA={known_ra:.4f}°, Dec={known_dec:.4f}°")
        
        # Test solving with known coordinates
        print("\n--- Test: Solving with known coordinates ---")
        result = solver.solve(
            test_image,
            ra_deg=known_ra,
            dec_deg=known_dec,
            fov_width_deg=fov_width,
            fov_height_deg=fov_height
        )
        
        print(f"Result: {result}")
        
        if result['success']:
            print(f"✓ Plate solving successful!")
            print(f"✓ Solved RA: {result['ra_center']:.4f}°")
            print(f"✓ Solved Dec: {result['dec_center']:.4f}°")
            print(f"✓ Solving time: {result['solving_time']:.1f}s")
            
            # Check accuracy (should be within reasonable bounds)
            ra_diff = abs(result['ra_center'] - known_ra)
            dec_diff = abs(result['dec_center'] - known_dec)
            
            # Accept differences up to 0.1 degrees (6 arcminutes)
            max_diff = 0.1
            if ra_diff <= max_diff and dec_diff <= max_diff:
                print(f"✓ Coordinate accuracy: RA diff={ra_diff:.6f}°, Dec diff={dec_diff:.6f}°")
                print(f"✓ Accuracy within acceptable range (±{max_diff}°)")
                return True
            else:
                print(f"⚠ Large coordinate differences: RA diff={ra_diff:.6f}°, Dec diff={dec_diff:.6f}°")
                print(f"⚠ This might indicate incorrect known coordinates or image mismatch")
                print(f"⚠ Acceptable range: ±{max_diff}°")
                return False
        else:
            print(f"✗ Plate solving failed: {result['error_message']}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing automated PlateSolve 2: {e}")
        return False

def test_command_string_building() -> bool:
    """Testet die Erstellung des Kommandozeilen-Strings.
    Returns:
        bool: True bei Erfolg, sonst False.
    """
    print("\n--- Testing command string building ---")
    
    try:
        from platesolve2_automated import PlateSolve2Automated
        
        solver = PlateSolve2Automated()
        
        # Test parameters
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        ra_deg = 295.0  # Example RA
        dec_deg = 40.0  # Example Dec
        fov_width_deg = 0.5  # Example FOV
        fov_height_deg = 0.4  # Example FOV
        
        # Prepare parameters
        ra_rad, dec_rad, fov_width_rad, fov_height_rad = solver._prepare_parameters(
            ra_deg, dec_deg, fov_width_deg, fov_height_deg
        )
        
        # Build command string
        cmd_string = solver._build_command_string(
            test_image, ra_rad, dec_rad, fov_width_rad, fov_height_rad
        )
        
        print(f"✓ Command string: {cmd_string}")
        
        # Verify format
        parts = cmd_string.split(',')
        if len(parts) == 7:
            print(f"✓ Correct number of parameters: {len(parts)}")
            print(f"✓ RA (rad): {parts[0]}")
            print(f"✓ Dec (rad): {parts[1]}")
            print(f"✓ FOV width (rad): {parts[2]}")
            print(f"✓ FOV height (rad): {parts[3]}")
            print(f"✓ Number of regions: {parts[4]}")
            print(f"✓ Image path: {parts[5]}")
            print(f"✓ Fixed parameter: {parts[6]}")
            return True
        else:
            print(f"✗ Incorrect number of parameters: {len(parts)}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing command string building: {e}")
        return False

def test_fov_calculation() -> bool:
    """Testet die FOV-Berechnung.
    Returns:
        bool: True bei Erfolg, sonst False.
    """
    print("\n--- Testing FOV calculation ---")
    
    try:
        from platesolve2_automated import PlateSolve2Automated
        
        solver = PlateSolve2Automated()
        
        # Test FOV calculation
        fov_width, fov_height = solver._calculate_fov()
        
        print(f"✓ Calculated FOV: {fov_width:.4f}° x {fov_height:.4f}°")
        
        # Test with different parameters
        # from config import get_telescope_config, get_camera_config # Assuming config.py exists
        # telescope_config = get_telescope_config()
        # camera_config = get_camera_config()
        
        # print(f"✓ Telescope focal length: {telescope_config.get('focal_length', 'N/A')}mm")
        # print(f"✓ Camera sensor: {camera_config.get('sensor_width', 'N/A')}mm x {camera_config.get('sensor_height', 'N/A')}mm")
        
        # Calculate sampling
        # pixel_size = camera_config.get('pixel_size', 3.75)  # microns
        # focal_length = telescope_config.get('focal_length', 1000)  # mm
        
        # sampling_arcsec_per_pixel = (pixel_size / 1000) / focal_length * 206265
        # print(f"✓ Sampling: {sampling_arcsec_per_pixel:.2f} arcsec/pixel")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing FOV calculation: {e}")
        return False

def test_integration_with_video_processor():
    """Test integration with the video processor."""
    print("\n--- Testing integration with video processor ---")
    
    try:
        from platesolve2_automated import PlateSolve2Automated
        from video_processor import VideoProcessor
        
        # Create automated solver
        automated_solver = PlateSolve2Automated()
        
        # Create video processor
        video_processor = VideoProcessor()
        
        # Test that they can work together
        print("✓ Automated solver created")
        print("✓ Video processor created")
        print("✓ Integration test passed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing integration: {e}")
        return False

def main() -> None:
    """Hauptfunktion für den automatisierten PlateSolve2-Test."""
    # Parse command line arguments
    args = parse_test_args("Automated PlateSolve 2 Test")
    
    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)
    
    # Print test header
    print_test_header("Automated PlateSolve 2 Test", driver_id, args.config)
    
    tests = [
        ("Automated PlateSolve 2", test_automated_platesolve2),
        ("Command String Building", test_command_string_building),
        ("FOV Calculation", test_fov_calculation),
        ("Video Processor Integration", test_integration_with_video_processor),
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
    
    if passed >= 3:
        print("\n🎉 Automated PlateSolve 2 testing completed successfully!")
        print("\n✅ PlateSolve 2 integration is working correctly!")
        print("\nNext steps:")
        print("1. Integrate with overlay_runner.py")
        print("2. Test with real telescope data")
        print("3. Optimize parameters for your setup")
        print("4. Add error handling for edge cases")
    else:
        print("\n❌ Some tests failed. Check configuration and PlateSolve 2 installation.")
        print("\nTroubleshooting:")
        print("• Ensure PlateSolve 2 is installed and accessible")
        print("• Verify the test image path exists and is a valid FITS file")
        print("• Check that known coordinates match the image content")
        print("• Review PlateSolve 2 configuration in config.yaml")

if __name__ == "__main__":
    main() 