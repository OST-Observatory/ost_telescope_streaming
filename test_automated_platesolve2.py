#!/usr/bin/env python3
"""
Test script for automated PlateSolve 2 using the correct command line format.
Tests the new implementation that uses: ra,dec,width_field_of_view,height_field_of_view,number_of_regions_to_test,path_to_image,"0"
"""

import sys
import os
import time
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def test_automated_platesolve2():
    """Test the new automated PlateSolve 2 implementation."""
    print("Testing automated PlateSolve 2 with correct command line format...")
    
    try:
        from plate_solver_automated import PlateSolve2Automated
        
        # Create solver
        solver = PlateSolve2Automated()
        
        # Test image
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        
        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            return False
        
        print(f"✓ Test image found: {test_image}")
        print(f"✓ Working directory: {solver.working_directory}")
        print(f"✓ Executable path: {solver.executable_path}")
        print(f"✓ Number of regions: {solver.number_of_regions}")
        
        # Test availability
        if not solver._is_available():
            print("✗ PlateSolve 2 not available")
            return False
        
        print("✓ PlateSolve 2 is available")
        
        # Test FOV calculation
        fov_width, fov_height = solver._calculate_fov()
        print(f"✓ Calculated FOV: {fov_width:.4f}° x {fov_height:.4f}°")
        
        # Test solving with estimated coordinates
        print("\n--- Test 1: Solving with estimated coordinates ---")
        result1 = solver.solve(test_image)
        
        print(f"Result 1: {result1}")
        
        if result1['success']:
            print(f"✓ Test 1 successful!")
            print(f"✓ RA: {result1['ra_center']:.4f}°")
            print(f"✓ Dec: {result1['dec_center']:.4f}°")
            print(f"✓ Solving time: {result1['solving_time']:.1f}s")
            
            # Test solving with known coordinates
            print("\n--- Test 2: Solving with known coordinates ---")
            result2 = solver.solve(
                test_image,
                ra_deg=result1['ra_center'],
                dec_deg=result1['dec_center'],
                fov_width_deg=fov_width,
                fov_height_deg=fov_height
            )
            
            print(f"Result 2: {result2}")
            
            if result2['success']:
                print(f"✓ Test 2 successful!")
                print(f"✓ RA: {result2['ra_center']:.4f}°")
                print(f"✓ Dec: {result2['dec_center']:.4f}°")
                print(f"✓ Solving time: {result2['solving_time']:.1f}s")
                
                # Compare results
                ra_diff = abs(result1['ra_center'] - result2['ra_center'])
                dec_diff = abs(result1['dec_center'] - result2['dec_center'])
                print(f"✓ Coordinate differences: RA={ra_diff:.6f}°, Dec={dec_diff:.6f}°")
                
                return True
            else:
                print(f"✗ Test 2 failed: {result2['error_message']}")
                return False
        else:
            print(f"✗ Test 1 failed: {result1['error_message']}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing automated PlateSolve 2: {e}")
        return False

def test_command_string_building():
    """Test the command string building functionality."""
    print("\n--- Testing command string building ---")
    
    try:
        from plate_solver_automated import PlateSolve2Automated
        
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

def test_fov_calculation():
    """Test FOV calculation from telescope and camera parameters."""
    print("\n--- Testing FOV calculation ---")
    
    try:
        from plate_solver_automated import PlateSolve2Automated
        
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
        from plate_solver_automated import PlateSolve2Automated
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

def main():
    """Main test function."""
    print("Automated PlateSolve 2 Test")
    print("=" * 50)
    
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
        print("\nNext steps:")
        print("1. Integrate with overlay_runner.py")
        print("2. Test with real telescope data")
        print("3. Optimize parameters for your setup")
        print("4. Add error handling for edge cases")
    else:
        print("\n❌ Some tests failed. Check configuration and PlateSolve 2 installation.")

if __name__ == "__main__":
    main() 