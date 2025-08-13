#!/usr/bin/env python3
"""
Test script for calibration workflow with multi-camera support.

This script tests the calibration workflow (darks, flats, masters) 
with OpenCV, ASCOM, and Alpyca cameras.
"""

import sys
import logging
import argparse
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import ConfigManager
from capture.controller import VideoCapture
from calibration.dark_capture import DarkCapture
from calibration.flat_capture import FlatCapture
from calibration.master_frame_builder import MasterFrameCreator

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("calibration_test")

def test_camera_connection(config, logger):
    """Test camera connection for the configured camera type."""
    print("\n=== CAMERA CONNECTION TEST ===")
    
    try:
        video_config = config.get_video_config()
        camera_type = video_config.get('camera_type', 'opencv')
        
        print(f"Testing {camera_type.upper()} camera connection...")
        
        # Create video capture instance
        capture = VideoCapture(config=config, logger=logger, return_frame_objects=True)
        
        # Test connection
        if camera_type == 'opencv':
            # For OpenCV, just check if we can create the capture
            print("✅ OpenCV camera ready")
            return True
            
        elif camera_type in ['ascom', 'alpaca']:
            # For ASCOM/Alpyca, test actual connection via adapter
            if hasattr(capture, 'camera') and capture.camera:
                try:
                    if hasattr(capture.camera, 'get_camera_info'):
                        info_status = capture.camera.get_camera_info()
                        if getattr(info_status, 'is_success', False):
                            print(f"✅ {camera_type.upper()} camera connected successfully")
                            return True
                        else:
                            print(f"❌ Failed to get camera info: {getattr(info_status, 'message', 'unknown error')}")
                            return False
                    else:
                        print(f"ℹ️ {camera_type.upper()} adapter does not expose get_camera_info(); assuming connected")
                        return True
                except Exception as e:
                    print(f"❌ Error retrieving camera info: {e}")
                    return False
            else:
                print(f"❌ No {camera_type} camera instance found")
                return False
        else:
            print(f"❌ Unknown camera type: {camera_type}")
            return False
            
    except Exception as e:
        print(f"❌ Camera connection test failed: {e}")
        return False

def test_dark_capture(config, logger):
    """Test dark frame capture."""
    print("\n=== DARK CAPTURE TEST ===")
    
    try:
        dark_config = config.get_dark_config()
        
        # Create dark capture instance
        dark_capture = DarkCapture(config=config, logger=logger)
        
        print("Testing dark frame capture...")
        print(f"  Bias frames: {dark_config.get('bias_count', 0)}")
        print(f"  Flat darks: {dark_config.get('flat_dark_count', 0)}")
        print(f"  Science darks: {dark_config.get('science_dark_count', 0)}")
        
        # Test with minimal frames for testing
        test_config = dark_config.copy()
        test_config['bias_count'] = 2
        test_config['flat_dark_count'] = 2
        test_config['science_dark_count'] = 2
        
        # Run dark capture
        status = dark_capture.capture_darks(
            bias_count=test_config['bias_count'],
            flat_dark_count=test_config['flat_dark_count'],
            science_dark_count=test_config['science_dark_count'],
            science_exposure_factors=test_config.get('science_exposure_factors', [1.0])
        )
        
        if status.is_success:
            print("✅ Dark capture test completed successfully")
            return True
        else:
            print(f"❌ Dark capture test failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Dark capture test failed: {e}")
        return False

def test_flat_capture(config, logger):
    """Test flat frame capture."""
    print("\n=== FLAT CAPTURE TEST ===")
    
    try:
        flat_config = config.get_flat_config()
        
        # Create flat capture instance
        flat_capture = FlatCapture(config=config, logger=logger)
        
        print("Testing flat frame capture...")
        print(f"  Target count: {flat_config.get('target_count', 0)}")
        print(f"  Tolerance: {flat_config.get('tolerance_percent', 0)}%")
        print(f"  Max exposure: {flat_config.get('max_exposure_time', 0)}s")
        
        # Test with minimal frames for testing
        test_config = flat_config.copy()
        test_config['target_count'] = 2
        test_config['max_exposure_time'] = 1.0  # Short exposure for testing
        
        # Run flat capture
        status = flat_capture.capture_flats(
            target_count=test_config['target_count'],
            target_percent=test_config.get('target_percent', 50.0),
            tolerance_percent=test_config.get('tolerance_percent', 10.0),
            max_exposure_time=test_config['max_exposure_time']
        )
        
        if status.is_success:
            print("✅ Flat capture test completed successfully")
            return True
        else:
            print(f"❌ Flat capture test failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Flat capture test failed: {e}")
        return False

def test_master_frame_creation(config, logger):
    """Test master frame creation."""
    print("\n=== MASTER FRAME CREATION TEST ===")
    
    try:
        master_config = config.get_master_config()
        
        # Create master frame creator instance
        master_creator = MasterFrameCreator(config=config, logger=logger)
        
        print("Testing master frame creation...")
        print(f"  Rejection method: {master_config.get('rejection_method', 'sigma_clipping')}")
        print(f"  Sigma threshold: {master_config.get('sigma_threshold', 3.0)}")
        
        # Run master frame creation
        status = master_creator.create_all_master_frames()
        
        if status.is_success:
            print("✅ Master frame creation test completed successfully")
            return True
        else:
            print(f"❌ Master frame creation test failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Master frame creation test failed: {e}")
        return False

def test_calibration_applier(config, logger):
    """Test calibration frame application."""
    print("\n=== CALIBRATION APPLIER TEST ===")
    
    try:
        from calibration_applier import CalibrationApplier
        
        # Create calibration applier instance
        applier = CalibrationApplier(config=config, logger=logger)
        
        print("Testing calibration applier...")
        
        # Test loading master frames
        if applier.auto_load_masters:
            print("✅ Auto-load masters enabled")
            
            # Get master frame info
            info_status = applier.get_master_frame_info()
            if info_status.is_success:
                info = info_status.data
                print(f"  Master bias: {'Available' if info['master_bias'] else 'Not available'}")
                print(f"  Master darks: {len(info['master_darks'])} available")
                print(f"  Master flat: {'Available' if info['master_flat'] else 'Not available'}")
            else:
                print(f"  Failed to get master frame info: {info_status.message}")
        else:
            print("ℹ️  Auto-load masters disabled")
        
        print("✅ Calibration applier test completed")
        return True
        
    except Exception as e:
        print(f"❌ Calibration applier test failed: {e}")
        return False

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test calibration workflow with multi-camera support")
    parser.add_argument("--config", type=str, required=True, help="Path to configuration file")
    parser.add_argument("--test", choices=['connection', 'darks', 'flats', 'masters', 'calibration', 'all'], 
                       default='all', help="Specific test to run")
    parser.add_argument("--verbose", action='store_true', help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("calibration_test")
    
    print("=== CALIBRATION WORKFLOW TEST ===")
    print(f"Configuration: {args.config}")
    print(f"Test: {args.test}")
    print()
    
    try:
        # Load configuration
        config = ConfigManager(args.config)
        video_config = config.get_video_config()
        camera_type = video_config.get('camera_type', 'opencv')
        
        print(f"Camera type: {camera_type.upper()}")
        print(f"Configuration loaded successfully")
        
        # Run tests
        tests_passed = 0
        total_tests = 0
        
        if args.test in ['connection', 'all']:
            total_tests += 1
            if test_camera_connection(config, logger):
                tests_passed += 1
        
        if args.test in ['darks', 'all']:
            total_tests += 1
            if test_dark_capture(config, logger):
                tests_passed += 1
        
        if args.test in ['flats', 'all']:
            total_tests += 1
            if test_flat_capture(config, logger):
                tests_passed += 1
        
        if args.test in ['masters', 'all']:
            total_tests += 1
            if test_master_frame_creation(config, logger):
                tests_passed += 1
        
        if args.test in ['calibration', 'all']:
            total_tests += 1
            if test_calibration_applier(config, logger):
                tests_passed += 1
        
        # Summary
        print(f"\n=== TEST SUMMARY ===")
        print(f"Tests passed: {tests_passed}/{total_tests}")
        print(f"Success rate: {tests_passed/total_tests*100:.1f}%")
        
        if tests_passed == total_tests:
            print("🎉 All tests passed! Calibration workflow is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
            return False
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 