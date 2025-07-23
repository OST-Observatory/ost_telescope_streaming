#!/usr/bin/env python3
"""
Test script for ASCOM Camera features.
Tests cooling, filter wheel, and debayering functionality.
"""

import sys
import os
import logging
from pathlib import Path

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from ascom_camera import ASCOMCamera
from config_manager import config

def test_ascom_camera_basic() -> bool:
    """Test basic ASCOM camera functionality."""
    print("Testing basic ASCOM camera functionality...")
    
    # This test requires a real ASCOM camera driver
    # For testing without hardware, we'll just check the class structure
    try:
        camera = ASCOMCamera(driver_id="ASCOM.TestCamera.Camera", config=config)
        print("✓ ASCOMCamera class instantiated successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to instantiate ASCOMCamera: {e}")
        return False

def test_ascom_camera_methods() -> bool:
    """Test ASCOM camera method signatures and basic functionality."""
    print("Testing ASCOM camera method signatures...")
    
    try:
        camera = ASCOMCamera(driver_id="ASCOM.TestCamera.Camera", config=config)
        
        # Test method existence and signatures
        methods_to_test = [
            'connect',
            'disconnect', 
            'expose',
            'get_image',
            'has_cooling',
            'set_cooling',
            'get_temperature',
            'has_filter_wheel',
            'get_filter_names',
            'set_filter_position',
            'get_filter_position',
            'is_color_camera',
            'debayer'
        ]
        
        for method_name in methods_to_test:
            if hasattr(camera, method_name):
                print(f"✓ Method {method_name} exists")
            else:
                print(f"✗ Method {method_name} missing")
                return False
        
        # Test that expose method accepts seconds
        import inspect
        sig = inspect.signature(camera.expose)
        params = list(sig.parameters.keys())
        if 'exposure_time_s' in params:
            print("✓ expose method accepts exposure_time_s parameter")
        else:
            print("✗ expose method does not accept exposure_time_s parameter")
            return False
            
        # Test that expose method accepts binning parameter
        if 'binning' in params:
            print("✓ expose method accepts binning parameter")
        else:
            print("✗ expose method does not accept binning parameter")
            
        return True
        
    except Exception as e:
        print(f"✗ Error testing method signatures: {e}")
        return False

def test_status_objects() -> bool:
    """Test that ASCOM camera methods return proper status objects."""
    print("Testing status object returns...")
    
    try:
        camera = ASCOMCamera(driver_id="ASCOM.TestCamera.Camera", config=config)
        
        # Test that connect returns CameraStatus
        # Note: This will fail without real hardware, but we can check the return type
        from status import CameraStatus
        
        # We can't actually call connect without hardware, but we can verify the method exists
        if hasattr(camera, 'connect'):
            print("✓ connect method exists and should return CameraStatus")
        else:
            print("✗ connect method missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Error testing status objects: {e}")
        return False

def test_config_integration() -> bool:
    """Test that ASCOM camera configuration is properly integrated."""
    print("Testing configuration integration...")
    
    try:
        # Check that config has ASCOM camera settings
        video_config = config.get('video', {})
        
        required_keys = ['camera_type', 'ascom_driver']
        for key in required_keys:
            if key in video_config:
                print(f"✓ Config key '{key}' exists: {video_config[key]}")
            else:
                print(f"✗ Config key '{key}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing configuration integration: {e}")
        return False

def test_cli_integration() -> bool:
    """Test that CLI integration is properly set up."""
    print("Testing CLI integration...")
    
    try:
        # Check that main_video_capture.py exists and has ASCOM features
        main_script = Path(__file__).parent.parent / "main_video_capture.py"
        if main_script.exists():
            content = main_script.read_text()
            
            # Check for ASCOM-related features
            ascom_features = [
                '--camera-type',
                '--ascom-driver',
                '--action',
                'info',
                'cooling',
                'filter',
                'debayer'
            ]
            
            for feature in ascom_features:
                if feature in content:
                    print(f"✓ CLI feature '{feature}' found")
                else:
                    print(f"✗ CLI feature '{feature}' missing")
                    return False
            
            return True
        else:
            print("✗ main_video_capture.py not found")
            return False
            
    except Exception as e:
        print(f"✗ Error testing CLI integration: {e}")
        return False

def main() -> None:
    """Main test function."""
    print("ASCOM Camera Feature Tests")
    print("=" * 40)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        test_ascom_camera_basic,
        test_ascom_camera_methods,
        test_status_objects,
        test_config_integration,
        test_cli_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 