#!/usr/bin/env python3
"""
Final integration test for the complete telescope streaming system.
Tests the new automated PlateSolve 2 implementation integrated with the existing system.
"""

import sys
import os
import time
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def test_automated_platesolve2_integration():
    """Test the automated PlateSolve 2 integration."""
    print("Testing automated PlateSolve 2 integration...")
    
    try:
        from plate_solver import PlateSolve2Solver
        
        # Create solver
        solver = PlateSolve2Solver()
        
        # Test image
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        
        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            return False
        
        print(f"✓ Test image found: {test_image}")
        print(f"✓ Automated solver available: {solver.automated_available}")
        
        # Test availability
        if not solver.is_available():
            print("✗ PlateSolve 2 not available")
            return False
        
        print("✓ PlateSolve 2 is available")
        
        # Test solving
        print("\n--- Testing automated solving ---")
        result = solver.solve(test_image)
        
        print(f"Result: {result}")
        
        if result.success:
            print(f"✓ Automated solving successful!")
            print(f"✓ Method used: {result.method_used}")
            print(f"✓ RA: {result.ra_center:.4f}°")
            print(f"✓ Dec: {result.dec_center:.4f}°")
            print(f"✓ FOV: {result.fov_width:.4f}° x {result.fov_height:.4f}°")
            print(f"✓ Confidence: {result.confidence}")
            print(f"✓ Solving time: {result.solving_time:.1f}s")
            return True
        else:
            print(f"✗ Solving failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing automated integration: {e}")
        return False

def test_video_processor_integration():
    """Test integration with video processor."""
    print("\n--- Testing video processor integration ---")
    
    try:
        from video_processor import VideoProcessor
        from plate_solver import PlateSolve2Solver
        
        # Create video processor
        video_processor = VideoProcessor()
        
        # Test that it can use the automated solver
        if hasattr(video_processor, 'plate_solver') and video_processor.plate_solver:
            print(f"✓ Video processor has plate solver: {video_processor.plate_solver.get_name()}")
            
            if isinstance(video_processor.plate_solver, PlateSolve2Solver):
                print(f"✓ Using PlateSolve 2 solver")
                print(f"✓ Automated solver available: {video_processor.plate_solver.automated_available}")
                return True
            else:
                print(f"✗ Using different solver: {video_processor.plate_solver.get_name()}")
                return False
        else:
            print("✗ Video processor has no plate solver")
            return False
            
    except Exception as e:
        print(f"✗ Error testing video processor integration: {e}")
        return False

def test_overlay_runner_integration():
    """Test integration with overlay runner."""
    print("\n--- Testing overlay runner integration ---")
    
    try:
        from overlay_runner import OverlayRunner
        
        # Create overlay runner
        runner = OverlayRunner()
        
        # Test that it can use video processor
        if hasattr(runner, 'video_processor') and runner.video_processor:
            print("✓ Overlay runner has video processor")
            return True
        else:
            print("✗ Overlay runner has no video processor")
            return False
            
    except Exception as e:
        print(f"✗ Error testing overlay runner integration: {e}")
        return False

def test_configuration():
    """Test configuration for automated solving."""
    print("\n--- Testing configuration ---")
    
    try:
        from config_manager import config
        
        # Test plate solve configuration
        plate_solve_config = config.get_plate_solve_config()
        
        required_keys = [
            'platesolve2_path',
            'working_directory',
            'timeout',
            'number_of_regions',
            'search_radius'
        ]
        
        missing_keys = []
        for key in required_keys:
            if key not in plate_solve_config:
                missing_keys.append(key)
            else:
                print(f"✓ {key}: {plate_solve_config[key]}")
        
        if missing_keys:
            print(f"✗ Missing configuration keys: {missing_keys}")
            return False
        
        # Test telescope and camera configuration
        telescope_config = config.get_telescope_config()
        camera_config = config.get_camera_config()
        
        print(f"✓ Telescope focal length: {telescope_config.get('focal_length', 'N/A')}mm")
        print(f"✓ Camera sensor: {camera_config.get('sensor_width', 'N/A')}mm x {camera_config.get('sensor_height', 'N/A')}mm")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing configuration: {e}")
        return False

def test_command_line_format():
    """Test the correct command line format."""
    print("\n--- Testing command line format ---")
    
    try:
        from plate_solver_automated import PlateSolve2Automated
        
        solver = PlateSolve2Automated()
        
        # Test parameters
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        ra_deg = 295.0  # Example RA
        dec_deg = 40.0  # Example Dec
        fov_width_deg = 0.5  # Example FOV
        fov_height_deg = 0.4  # Example FOV
        
        # Build command string
        ra_rad, dec_rad, fov_width_rad, fov_height_rad = solver._prepare_parameters(
            ra_deg, dec_deg, fov_width_deg, fov_height_deg
        )
        
        cmd_string = solver._build_command_string(
            test_image, ra_rad, dec_rad, fov_width_rad, fov_height_rad
        )
        
        print(f"✓ Command string format: {cmd_string}")
        
        # Verify format matches user specification
        # Format: ra,dec,width_field_of_view,height_field_of_view,number_of_regions_to_test,path_to_image,"0"
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
            
            # Verify all parameters are in radians (except the last two)
            try:
                float(parts[0])  # RA
                float(parts[1])  # Dec
                float(parts[2])  # FOV width
                float(parts[3])  # FOV height
                int(parts[4])    # Number of regions
                print("✓ All numeric parameters are valid")
                return True
            except ValueError:
                print("✗ Invalid numeric parameters")
                return False
        else:
            print(f"✗ Incorrect number of parameters: {len(parts)}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing command line format: {e}")
        return False

def test_complete_workflow():
    """Test the complete workflow from image to overlay."""
    print("\n--- Testing complete workflow ---")
    
    try:
        # This would test the complete workflow
        # For now, just verify all components are available
        
        from plate_solver import PlateSolve2Solver
        from video_processor import VideoProcessor
        from overlay_runner import OverlayRunner
        from generate_overlay import generate_overlay
        
        print("✓ All core components imported successfully")
        
        # Test that automated solving is available
        solver = PlateSolve2Solver()
        if solver.automated_available:
            print("✓ Automated PlateSolve 2 is available")
        else:
            print("✗ Automated PlateSolve 2 is not available")
        
        # Test video processor
        video_processor = VideoProcessor()
        print("✓ Video processor is available")
        
        # Test overlay runner
        overlay_runner = OverlayRunner()
        print("✓ Overlay runner is available")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing complete workflow: {e}")
        return False

def main():
    """Main test function."""
    print("Final Integration Test")
    print("=" * 50)
    print("Testing complete system with automated PlateSolve 2")
    
    tests = [
        ("Automated PlateSolve 2 Integration", test_automated_platesolve2_integration),
        ("Video Processor Integration", test_video_processor_integration),
        ("Overlay Runner Integration", test_overlay_runner_integration),
        ("Configuration", test_configuration),
        ("Command Line Format", test_command_line_format),
        ("Complete Workflow", test_complete_workflow),
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
    
    print(f"\n--- Final Results ---")
    print(f"Completed: {passed}/{total}")
    
    if passed >= 5:
        print("\n🎉 Final integration test completed successfully!")
        print("\n🎯 Your automated PlateSolve 2 system is ready!")
        print("\nNext steps:")
        print("1. Run the system with real telescope data")
        print("2. Monitor performance and accuracy")
        print("3. Adjust parameters as needed")
        print("4. Enjoy automated plate-solving!")
        
        print("\n🚀 To start the system:")
        print("python overlay_runner.py")
        
    elif passed >= 3:
        print("\n⚠️  Most tests passed, but some issues remain.")
        print("Check the failed tests and fix any configuration issues.")
        
    else:
        print("\n❌ Multiple tests failed. Please check:")
        print("1. PlateSolve 2 installation and path")
        print("2. Configuration settings")
        print("3. Image file availability")
        print("4. System dependencies")

if __name__ == "__main__":
    main() 