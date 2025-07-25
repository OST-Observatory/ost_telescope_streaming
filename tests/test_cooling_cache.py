#!/usr/bin/env python3
"""
Test script for ASCOM camera cooling cache issues.
This script demonstrates the problem with ASCOM driver caching and tests different solutions.
"""

import sys
import time
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from ascom_camera import ASCOMCamera
from config_manager import ConfigManager
import logging

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("cooling_test")

def test_cooling_methods(camera, logger):
    """Test different cooling info retrieval methods."""
    print("\n" + "="*60)
    print("TESTING DIFFERENT COOLING INFO METHODS")
    print("="*60)
    
    methods = [
        ("Normal Method", camera.get_cooling_info),
        ("Fresh Method", camera.get_fresh_cooling_info),
        ("Cached Method", camera.get_cached_cooling_info),
        ("Smart Method", camera.get_smart_cooling_info)
    ]
    
    for method_name, method_func in methods:
        print(f"\n--- Testing {method_name} ---")
        try:
            status = method_func()
            if status.is_success:
                info = status.data
                print(f"✅ {method_name}:")
                print(f"   Temperature: {info.get('temperature')}°C")
                print(f"   Cooler Power: {info.get('cooler_power')}%")
                print(f"   Cooler On: {info.get('cooler_on')}")
                print(f"   Target Temp: {info.get('target_temperature')}°C")
            else:
                print(f"❌ {method_name}: {status.message}")
        except Exception as e:
            print(f"❌ {method_name}: Exception - {e}")

def test_cooling_operation_sequence(camera, logger):
    """Test cooling operations and their effect on cached values."""
    print("\n" + "="*60)
    print("TESTING COOLING OPERATION SEQUENCE")
    print("="*60)
    
    # Step 1: Get initial values
    print("\n1. Initial cooling info:")
    status = camera.get_smart_cooling_info()
    if status.is_success:
        info = status.data
        print(f"   Temperature: {info.get('temperature')}°C")
        print(f"   Cooler Power: {info.get('cooler_power')}%")
        print(f"   Cooler On: {info.get('cooler_on')}")
    
    # Step 2: Set cooling to -10°C
    print("\n2. Setting cooling to -10°C...")
    status = camera.set_cooling(-10.0)
    if status.is_success:
        print(f"   ✅ Cooling set successfully")
        if hasattr(status, 'details') and status.details:
            details = status.details
            print(f"   Before: {details.get('current_temp')}°C, After: {details.get('new_temp')}°C")
    else:
        print(f"   ❌ Failed: {status.message}")
    
    # Step 3: Wait and check values
    print("\n3. Waiting 2 seconds and checking values...")
    time.sleep(2)
    
    # Test all methods after operation
    test_cooling_methods(camera, logger)
    
    # Step 4: Turn cooling off
    print("\n4. Turning cooling off...")
    status = camera.turn_cooling_off()
    if status.is_success:
        print(f"   ✅ Cooling turned off successfully")
        if hasattr(status, 'details') and status.details:
            details = status.details
            print(f"   Before: {details.get('current_temp')}°C, After: {details.get('new_temp')}°C")
    else:
        print(f"   ❌ Failed: {status.message}")
    
    # Step 5: Wait and check values again
    print("\n5. Waiting 2 seconds and checking values again...")
    time.sleep(2)
    
    # Test all methods after turning off
    test_cooling_methods(camera, logger)

def test_cache_consistency(camera, logger):
    """Test cache consistency over multiple reads."""
    print("\n" + "="*60)
    print("TESTING CACHE CONSISTENCY")
    print("="*60)
    
    print("\nReading cooling info 5 times with 1-second intervals:")
    for i in range(5):
        print(f"\nRead {i+1}:")
        status = camera.get_smart_cooling_info()
        if status.is_success:
            info = status.data
            print(f"   Temperature: {info.get('temperature')}°C")
            print(f"   Cooler Power: {info.get('cooler_power')}%")
            print(f"   Cooler On: {info.get('cooler_on')}")
        else:
            print(f"   ❌ Failed: {status.message}")
        
        if i < 4:  # Don't sleep after the last read
            time.sleep(1)

def main():
    """Main test function."""
    logger = setup_logging()
    config = ConfigManager()
    
    # Get ASCOM driver from config or use default
    video_config = config.get_video_config()
    driver_id = video_config['ascom']['ascom_driver']
    
    print("ASCOM Camera Cooling Cache Test")
    print("="*50)
    print(f"Driver ID: {driver_id}")
    print(f"Note: This test requires an ASCOM camera with cooling support")
    
    try:
        # Create camera instance
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)
        
        # Connect to camera
        print("\nConnecting to camera...")
        status = camera.connect()
        if not status.is_success:
            print(f"❌ Connection failed: {status.message}")
            return
        
        print("✅ Camera connected successfully")
        
        # Check if cooling is supported
        if not camera.has_cooling():
            print("❌ This camera does not support cooling")
            camera.disconnect()
            return
        
        print("✅ Cooling is supported")
        
        # Run tests
        test_cooling_methods(camera, logger)
        test_cooling_operation_sequence(camera, logger)
        test_cache_consistency(camera, logger)
        
        # Disconnect
        camera.disconnect()
        print("\n✅ Test completed successfully")
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Test failed")

if __name__ == "__main__":
    main() 