#!/usr/bin/env python3
"""
Test script for persistent cooling cache functionality.
This script tests that cache persists between different camera instances.
"""

import sys
import time
import os
import json
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from drivers.ascom.camera import ASCOMCamera
from config_manager import ConfigManager
import logging

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("persistent_cache_test")

def test_persistent_cache():
    """Test that cache persists between different camera instances."""
    logger = setup_logging()
    config = ConfigManager()
    
    # Get ASCOM driver from config
    video_config = config.get_video_config()
    driver_id = video_config['ascom']['ascom_driver']
    
    print("Persistent Cache Test")
    print("="*50)
    print(f"Driver ID: {driver_id}")
    
    # Calculate expected cache file path
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache')
    cache_file = os.path.join(cache_dir, f'cooling_cache_{driver_id.replace(".", "_").replace(":", "_")}.json')
    
    print(f"Cache file: {cache_file}")
    
    try:
        # Test 1: Create first camera instance and set cooling
        print("\n1. Creating first camera instance...")
        camera1 = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)
        
        # Check if cache file exists initially
        cache_exists_before = os.path.exists(cache_file)
        print(f"   Cache file exists before: {cache_exists_before}")
        
        # Connect and set cooling
        connect_status = camera1.connect()
        if connect_status.is_success:
            print("   ✅ Camera connected")
            
            if camera1.has_cooling():
                print("   Setting cooling to -5°C...")
                cooling_status = camera1.set_cooling(-5.0)
                if cooling_status.is_success:
                    print("   ✅ Cooling set successfully")
                    
                    # Check cache file was created
                    cache_exists_after = os.path.exists(cache_file)
                    print(f"   Cache file exists after: {cache_exists_after}")
                    
                    if cache_exists_after:
                        # Read cache file content
                        with open(cache_file, 'r') as f:
                            cache_data = json.load(f)
                        print(f"   Cache file content: {json.dumps(cache_data, indent=2)}")
                        
                        # Check cache values
                        cache_info = cache_data.get('cooling_info', {})
                        print(f"   Cached temperature: {cache_info.get('temperature')}°C")
                        print(f"   Cached cooler power: {cache_info.get('cooler_power')}%")
                        print(f"   Cached cooler on: {cache_info.get('cooler_on')}")
                    else:
                        print("   ❌ Cache file was not created")
                else:
                    print(f"   ❌ Cooling failed: {cooling_status.message}")
            else:
                print("   ❌ Camera does not support cooling")
            
            camera1.disconnect()
        else:
            print(f"   ❌ Connection failed: {connect_status.message}")
            return
        
        # Test 2: Create second camera instance and check if cache is loaded
        print("\n2. Creating second camera instance...")
        camera2 = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)
        
        # Check if cache was loaded
        print(f"   Cache loaded: {camera2.last_cooling_info}")
        
        # Connect and check cooling info
        connect_status = camera2.connect()
        if connect_status.is_success:
            print("   ✅ Camera connected")
            
            if camera2.has_cooling():
                print("   Getting cooling info...")
                cooling_status = camera2.get_smart_cooling_info()
                if cooling_status.is_success:
                    info = cooling_status.data
                    print(f"   Temperature: {info['temperature']}°C")
                    print(f"   Cooler power: {info['cooler_power']}%")
                    print(f"   Cooler on: {info['cooler_on']}")
                    print(f"   Target temperature: {info['target_temperature']}°C")
                    
                    # Check if values match the cache
                    if (info['temperature'] == camera2.last_cooling_info['temperature'] and
                        info['cooler_power'] == camera2.last_cooling_info['cooler_power'] and
                        info['cooler_on'] == camera2.last_cooling_info['cooler_on']):
                        print("   ✅ Cache values match current values")
                    else:
                        print("   ⚠️  Cache values differ from current values")
                        print(f"      Cache: {camera2.last_cooling_info}")
                        print(f"      Current: {info}")
                else:
                    print(f"   ❌ Failed to get cooling info: {cooling_status.message}")
            else:
                print("   ❌ Camera does not support cooling")
            
            camera2.disconnect()
        else:
            print(f"   ❌ Connection failed: {connect_status.message}")
        
        # Test 3: Test cache expiration
        print("\n3. Testing cache expiration...")
        
        # Modify cache file to be old (6 minutes)
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Make cache 6 minutes old
            cache_data['timestamp'] = time.time() - 360  # 6 minutes ago
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            print("   Made cache 6 minutes old")
            
            # Create new instance and check if old cache is ignored
            camera3 = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)
            print(f"   Cache after loading old cache: {camera3.last_cooling_info}")
            
            # Check if cache was cleared (all values should be None)
            if all(v is None for v in camera3.last_cooling_info.values()):
                print("   ✅ Old cache was correctly ignored")
            else:
                print("   ❌ Old cache was not ignored")
        
        print("\n✅ Persistent cache test completed")
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Test failed")

if __name__ == "__main__":
    test_persistent_cache() 