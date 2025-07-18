#!/usr/bin/env python3
"""
Test script for video capture integration.
Tests the video capture module and its integration with the overlay system.
"""

import sys
import os
import time
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def test_config_manager():
    """Test configuration manager with new video settings."""
    print("Testing configuration manager...")
    
    try:
        from config_manager import config
        
        # Test new configuration sections
        telescope_config = config.get_telescope_config()
        camera_config = config.get_camera_config()
        video_config = config.get_video_config()
        
        print(f"Telescope config: {telescope_config}")
        print(f"Camera config: {camera_config}")
        print(f"Video config: {video_config}")
        
        # Test FOV calculation
        focal_length = telescope_config.get('focal_length', 1000)
        sensor_width = camera_config.get('sensor_width', 6.17)
        sensor_height = camera_config.get('sensor_height', 4.55)
        
        # Calculate FOV manually for verification
        import numpy as np
        fov_width_rad = 2 * np.arctan(sensor_width / (2 * focal_length))
        fov_height_rad = 2 * np.arctan(sensor_height / (2 * focal_length))
        fov_width_deg = np.degrees(fov_width_rad)
        fov_height_deg = np.degrees(fov_height_rad)
        
        print(f"Calculated FOV: {fov_width_deg:.3f}° x {fov_height_deg:.3f}°")
        
        return True
        
    except Exception as e:
        print(f"Error testing config manager: {e}")
        return False

def test_video_capture():
    """Test video capture module."""
    print("\nTesting video capture module...")
    
    try:
        from video_capture import VideoCapture
        
        video_capture = VideoCapture()
        
        # Test camera info
        info = video_capture.get_camera_info()
        print(f"Camera info: {info}")
        
        # Test FOV calculation
        fov_width, fov_height = video_capture.get_field_of_view()
        sampling = video_capture.get_sampling_arcsec_per_pixel()
        
        print(f"FOV: {fov_width:.3f}° x {fov_height:.3f}°")
        print(f"Sampling: {sampling:.2f} arcsec/pixel")
        
        # Test connection (without actually connecting)
        print("Video capture module loaded successfully")
        return True
        
    except Exception as e:
        print(f"Error testing video capture: {e}")
        return False

def test_overlay_runner_integration():
    """Test overlay runner integration."""
    print("\nTesting overlay runner integration...")
    
    try:
        from overlay_runner import OverlayRunner
        
        runner = OverlayRunner()
        
        # Check if video capture is enabled
        print(f"Video enabled: {runner.video_enabled}")
        print(f"Video capture interval: {runner.video_capture_interval} seconds")
        
        print("Overlay runner integration test passed")
        return True
        
    except Exception as e:
        print(f"Error testing overlay runner integration: {e}")
        return False

def test_actual_camera_connection():
    """Test actual camera connection (optional)."""
    print("\nTesting actual camera connection...")
    
    try:
        from video_capture import VideoCapture
        
        video_capture = VideoCapture()
        
        # Test connection
        if video_capture.connect():
            print("Camera connected successfully")
            
            # Test single frame capture
            frame = video_capture.capture_single_frame()
            if frame is not None:
                print(f"Frame captured: {frame.shape}")
                
                # Save test frame
                test_filename = "test_video_integration_frame.jpg"
                if video_capture.save_frame(frame, test_filename):
                    print(f"Test frame saved: {test_filename}")
                else:
                    print("Failed to save test frame")
            else:
                print("Failed to capture frame")
            
            video_capture.disconnect()
            return True
        else:
            print("Failed to connect to camera")
            return False
            
    except Exception as e:
        print(f"Error testing camera connection: {e}")
        return False

def main():
    """Main test function."""
    print("Video Integration Test")
    print("=" * 50)
    
    tests = [
        ("Configuration Manager", test_config_manager),
        ("Video Capture Module", test_video_capture),
        ("Overlay Runner Integration", test_overlay_runner_integration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            print(f"✓ {test_name} passed")
            passed += 1
        else:
            print(f"✗ {test_name} failed")
    
    print(f"\n--- Results ---")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed!")
        
        # Ask if user wants to test actual camera
        try:
            response = input("\nTest actual camera connection? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                test_actual_camera_connection()
        except KeyboardInterrupt:
            print("\nSkipping camera test")
    else:
        print("Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main() 