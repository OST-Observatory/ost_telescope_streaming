#!/usr/bin/env python3
"""
Debug test for cache loading and smart cooling info.
This script shows exactly what happens with cache loading.
"""

import sys
import os
import json
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
    return logging.getLogger("cache_debug_test")

def test_cache_debug():
    """Debug test for cache loading."""
    logger = setup_logging()
    config = ConfigManager()
    
    # Get ASCOM driver from config
    video_config = config.get_video_config()
    driver_id = video_config['ascom']['ascom_driver']
    
    print("Cache Debug Test")
    print("="*50)
    print(f"Driver ID: {driver_id}")
    
    # Calculate cache file path
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache')
    cache_file = os.path.join(cache_dir, f'cooling_cache_{driver_id.replace(".", "_").replace(":", "_")}.json')
    
    print(f"Cache file: {cache_file}")
    
    # Check if cache file exists
    if os.path.exists(cache_file):
        print(f"✅ Cache file exists")
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        print(f"Cache file content:")
        print(json.dumps(cache_data, indent=2))
    else:
        print(f"❌ Cache file does not exist")
        return
    
    try:
        # Create camera instance
        print("\n1. Creating camera instance...")
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)
        
        # Check cache after loading
        print(f"\n2. Cache after loading:")
        print(f"   last_cooling_info: {camera.last_cooling_info}")
        
        # Check if cache is valid
        has_valid_cache = (
            camera.last_cooling_info['temperature'] is not None and
            camera.last_cooling_info['cooler_power'] is not None and
            camera.last_cooling_info['cooler_on'] is not None
        )
        print(f"   Has valid cache: {has_valid_cache}")
        
        # Connect to camera
        print("\n3. Connecting to camera...")
        connect_status = camera.connect()
        if connect_status.is_success:
            print("   ✅ Camera connected")
            
            if camera.has_cooling():
                print("\n4. Testing get_smart_cooling_info()...")
                cooling_status = camera.get_smart_cooling_info()
                if cooling_status.is_success:
                    info = cooling_status.data
                    print(f"   Result:")
                    print(f"     Temperature: {info['temperature']}°C")
                    print(f"     Cooler power: {info['cooler_power']}%")
                    print(f"     Cooler on: {info['cooler_on']}")
                    print(f"     Target temperature: {info['target_temperature']}°C")
                    
                    # Compare with cache
                    print(f"\n5. Comparison:")
                    print(f"   Cache values: {camera.last_cooling_info}")
                    print(f"   Current values: {info}")
                    
                    if (info['temperature'] == camera.last_cooling_info['temperature'] and
                        info['cooler_power'] == camera.last_cooling_info['cooler_power'] and
                        info['cooler_on'] == camera.last_cooling_info['cooler_on']):
                        print("   ✅ Cache and current values match")
                    else:
                        print("   ❌ Cache and current values differ")
                else:
                    print(f"   ❌ Failed: {cooling_status.message}")
            else:
                print("   ❌ Camera does not support cooling")
            
            camera.disconnect()
        else:
            print(f"   ❌ Connection failed: {connect_status.message}")
        
        print("\n✅ Debug test completed")
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Test failed")

if __name__ == "__main__":
    test_cache_debug() 