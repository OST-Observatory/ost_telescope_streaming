#!/usr/bin/env python3
"""
Test script for overlay runner with Alpyca camera support.

This script tests the overlay runner functionality with Alpyca cameras.
"""

import sys
import logging
import argparse
import time
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import ConfigManager
from overlay_runner import OverlayRunner
from alpaca_camera import AlpycaCameraWrapper

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("overlay_runner_test")

def test_alpaca_connection(config, logger):
    """Test Alpyca camera connection."""
    print("\n=== ALPYCA CONNECTION TEST ===")
    
    try:
        video_config = config.get_video_config()
        alpaca_config = video_config.get('alpaca', {})
        
        print(f"Testing Alpyca connection...")
        print(f"  Host: {alpaca_config.get('host', 'localhost')}")
        print(f"  Port: {alpaca_config.get('port', 11111)}")
        print(f"  Device ID: {alpaca_config.get('device_id', 0)}")
        
        # Create Alpyca camera instance
        camera = AlpycaCameraWrapper(
            host=alpaca_config.get('host', 'localhost'),
            port=alpaca_config.get('port', 11111),
            device_id=alpaca_config.get('device_id', 0),
            config=config,
            logger=logger
        )
        
        # Test connection
        status = camera.connect()
        if status.is_success:
            print(f"✅ Alpyca camera connected: {camera.name}")
            
            # Get camera info
            info_status = camera.get_camera_info()
            if info_status.is_success:
                info = info_status.data
                print(f"  Sensor: {info['camera_size']}")
                print(f"  Type: {'Color' if info['is_color'] else 'Monochrome'}")
                print(f"  Cooling: {'Supported' if info['cooling_supported'] else 'Not supported'}")
            
            camera.disconnect()
            return True
        else:
            print(f"❌ Alpyca connection failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Alpyca connection test failed: {e}")
        return False

def test_single_capture(config, logger):
    """Test single frame capture with overlay."""
    print("\n=== SINGLE CAPTURE TEST ===")
    
    try:
        print("Testing single frame capture with overlay...")
        
        # Create overlay runner
        runner = OverlayRunner(config=config, logger=logger)
        
        # Test single capture
        status = runner.capture_single_frame_with_overlay()
        
        if status.is_success:
            print("✅ Single capture test completed successfully")
            if hasattr(status, 'data') and status.data:
                data = status.data
                print(f"  Frame captured: {data.get('frame_path', 'Unknown')}")
                print(f"  Overlay generated: {data.get('overlay_path', 'Unknown')}")
                print(f"  Combined saved: {data.get('combined_path', 'Unknown')}")
            return True
        else:
            print(f"❌ Single capture test failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Single capture test failed: {e}")
        return False

def test_continuous_capture(config, logger, duration=30):
    """Test continuous capture for a short duration."""
    print(f"\n=== CONTINUOUS CAPTURE TEST ({duration}s) ===")
    
    try:
        print(f"Testing continuous capture for {duration} seconds...")
        
        # Create overlay runner
        runner = OverlayRunner(config=config, logger=logger)
        
        # Start continuous capture
        start_time = time.time()
        frame_count = 0
        
        print("Starting continuous capture...")
        while time.time() - start_time < duration:
            status = runner.capture_single_frame_with_overlay()
            if status.is_success:
                frame_count += 1
                elapsed = time.time() - start_time
                print(f"  Frame {frame_count} captured at {elapsed:.1f}s")
            else:
                print(f"  Frame capture failed: {status.message}")
                break
            
            # Small delay between captures
            time.sleep(2)
        
        print(f"✅ Continuous capture test completed")
        print(f"  Frames captured: {frame_count}")
        print(f"  Duration: {time.time() - start_time:.1f}s")
        print(f"  Average rate: {frame_count/(time.time() - start_time):.2f} fps")
        
        return frame_count > 0
        
    except Exception as e:
        print(f"❌ Continuous capture test failed: {e}")
        return False

def test_plate_solving(config, logger):
    """Test plate solving functionality."""
    print("\n=== PLATE SOLVING TEST ===")
    
    try:
        print("Testing plate solving...")
        
        # Create overlay runner
        runner = OverlayRunner(config=config, logger=logger)
        
        # Test plate solving
        status = runner.solve_current_frame()
        
        if status.is_success:
            print("✅ Plate solving test completed successfully")
            if hasattr(status, 'data') and status.data:
                data = status.data
                print(f"  RA: {data.get('ra', 'Unknown')}")
                print(f"  Dec: {data.get('dec', 'Unknown')}")
                print(f"  Position angle: {data.get('position_angle', 'Unknown')}")
                print(f"  Image size: {data.get('image_size', 'Unknown')}")
                print(f"  Flipped: {data.get('is_flipped', 'Unknown')}")
            return True
        else:
            print(f"❌ Plate solving test failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Plate solving test failed: {e}")
        return False

def test_overlay_generation(config, logger):
    """Test overlay generation."""
    print("\n=== OVERLAY GENERATION TEST ===")
    
    try:
        print("Testing overlay generation...")
        
        # Create overlay runner
        runner = OverlayRunner(config=config, logger=logger)
        
        # Test overlay generation with test coordinates
        test_ra = 180.0  # Test RA
        test_dec = 0.0   # Test Dec
        
        status = runner.generate_overlay_with_coords(test_ra, test_dec)
        
        if status.is_success:
            print("✅ Overlay generation test completed successfully")
            if hasattr(status, 'data') and status.data:
                data = status.data
                print(f"  Overlay saved: {data.get('overlay_path', 'Unknown')}")
            return True
        else:
            print(f"❌ Overlay generation test failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Overlay generation test failed: {e}")
        return False

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test overlay runner with Alpyca camera support")
    parser.add_argument("--config", type=str, required=True, help="Path to configuration file")
    parser.add_argument("--test", choices=['connection', 'capture', 'continuous', 'platesolve', 'overlay', 'all'], 
                       default='all', help="Specific test to run")
    parser.add_argument("--duration", type=int, default=30, help="Duration for continuous capture test (seconds)")
    parser.add_argument("--verbose", action='store_true', help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("overlay_runner_test")
    
    print("=== OVERLAY RUNNER ALPYCA TEST ===")
    print(f"Configuration: {args.config}")
    print(f"Test: {args.test}")
    print()
    
    try:
        # Load configuration
        config = ConfigManager(args.config)
        video_config = config.get_video_config()
        camera_type = video_config.get('camera_type', 'opencv')
        
        if camera_type != 'alpaca':
            print(f"⚠️  Configuration uses {camera_type} camera, but this test is designed for Alpyca")
            print(f"   Consider using --camera-type alpaca in your configuration")
        
        print(f"Camera type: {camera_type.upper()}")
        print(f"Configuration loaded successfully")
        
        # Run tests
        tests_passed = 0
        total_tests = 0
        
        if args.test in ['connection', 'all']:
            total_tests += 1
            if test_alpaca_connection(config, logger):
                tests_passed += 1
        
        if args.test in ['capture', 'all']:
            total_tests += 1
            if test_single_capture(config, logger):
                tests_passed += 1
        
        if args.test in ['continuous', 'all']:
            total_tests += 1
            if test_continuous_capture(config, logger, args.duration):
                tests_passed += 1
        
        if args.test in ['platesolve', 'all']:
            total_tests += 1
            if test_plate_solving(config, logger):
                tests_passed += 1
        
        if args.test in ['overlay', 'all']:
            total_tests += 1
            if test_overlay_generation(config, logger):
                tests_passed += 1
        
        # Summary
        print(f"\n=== TEST SUMMARY ===")
        print(f"Tests passed: {tests_passed}/{total_tests}")
        print(f"Success rate: {tests_passed/total_tests*100:.1f}%")
        
        if tests_passed == total_tests:
            print("🎉 All tests passed! Overlay runner with Alpyca is working correctly.")
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