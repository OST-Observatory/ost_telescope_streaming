#!/usr/bin/env python3
"""
Dedicated test script for Alpyca cooling debugging.

This script provides detailed testing and debugging of Alpyca camera cooling functionality.
"""

import sys
import logging
import time
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from drivers.alpaca.camera import AlpycaCameraWrapper
from config_manager import ConfigManager

def setup_logging():
    """Setup detailed logging for debugging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("alpaca_cooling_test")

def test_cooling_properties(camera):
    """Test all cooling-related properties."""
    print("\n=== COOLING PROPERTIES TEST ===")
    
    try:
        print("Testing cooling properties...")
        
        # Test cooling support
        can_set_temp = camera.can_set_ccd_temperature
        can_get_power = camera.can_get_cooler_power
        
        print(f"Can set CCD temperature: {can_set_temp}")
        print(f"Can get cooler power: {can_get_power}")
        
        if not can_set_temp:
            print("❌ Cooling not supported by this camera")
            return False
        
        # Test current values
        current_temp = camera.ccd_temperature
        target_temp = camera.set_ccd_temperature
        cooler_on = camera.cooler_on
        cooler_power = camera.cooler_power
        heat_sink_temp = camera.heat_sink_temperature
        
        print(f"Current temperature: {current_temp}°C")
        print(f"Target temperature: {target_temp}°C")
        print(f"Cooler on: {cooler_on}")
        print(f"Cooler power: {cooler_power}%")
        print(f"Heat sink temperature: {heat_sink_temp}°C")
        
        return True
        
    except Exception as e:
        print(f"❌ Cooling properties test failed: {e}")
        return False

def test_cooling_setting(camera, target_temp):
    """Test setting cooling target temperature."""
    print(f"\n=== COOLING SETTING TEST ({target_temp}°C) ===")
    
    try:
        print(f"Setting cooling target to {target_temp}°C...")
        
        # Get initial status
        initial_temp = camera.ccd_temperature
        initial_power = camera.cooler_power
        initial_cooler_on = camera.cooler_on
        
        print(f"Initial status:")
        print(f"  Temperature: {initial_temp}°C")
        print(f"  Cooler power: {initial_power}%")
        print(f"  Cooler on: {initial_cooler_on}")
        
        # Set cooling
        status = camera.set_cooling(target_temp)
        
        if status.is_success:
            print(f"✅ Cooling set successfully: {status.message}")
            
            # Show details if available
            if hasattr(status, 'details') and status.details:
                details = status.details
                print(f"Details:")
                print(f"  Target temp: {details.get('target_temp')}°C")
                print(f"  Current temp: {details.get('current_temp')}°C")
                print(f"  New temp: {details.get('new_temp')}°C")
                print(f"  Current power: {details.get('current_power')}%")
                print(f"  New power: {details.get('new_power')}%")
                print(f"  Current cooler on: {details.get('current_cooler_on')}")
                print(f"  New cooler on: {details.get('new_cooler_on')}")
            
            # Wait and check again
            print(f"\nWaiting 2 seconds and checking again...")
            time.sleep(2)
            
            final_temp = camera.ccd_temperature
            final_power = camera.cooler_power
            final_cooler_on = camera.cooler_on
            
            print(f"Final status:")
            print(f"  Temperature: {final_temp}°C")
            print(f"  Cooler power: {final_power}%")
            print(f"  Cooler on: {final_cooler_on}")
            
            # Analyze results
            if final_cooler_on and final_power > 0:
                print(f"✅ Cooling is active and working")
                temp_diff = final_temp - target_temp
                print(f"  Temperature difference: {temp_diff:+.1f}°C")
            elif final_cooler_on and final_power == 0:
                print(f"⚠️  Cooler is on but power is 0% - may be at target temperature")
            else:
                print(f"❌ Cooling is not working properly")
            
            return True
        else:
            print(f"❌ Failed to set cooling: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Cooling setting test failed: {e}")
        return False

def test_cooling_off(camera):
    """Test turning off cooling."""
    print(f"\n=== COOLING OFF TEST ===")
    
    try:
        print("Turning off cooling...")
        
        # Get initial status
        initial_temp = camera.ccd_temperature
        initial_power = camera.cooler_power
        initial_cooler_on = camera.cooler_on
        
        print(f"Initial status:")
        print(f"  Temperature: {initial_temp}°C")
        print(f"  Cooler power: {initial_power}%")
        print(f"  Cooler on: {initial_cooler_on}")
        
        # Turn off cooling
        status = camera.turn_cooling_off()
        
        if status.is_success:
            print(f"✅ Cooling turned off successfully: {status.message}")
            
            # Wait and check again
            print(f"\nWaiting 2 seconds and checking again...")
            time.sleep(2)
            
            final_temp = camera.ccd_temperature
            final_power = camera.cooler_power
            final_cooler_on = camera.cooler_on
            
            print(f"Final status:")
            print(f"  Temperature: {final_temp}°C")
            print(f"  Cooler power: {final_power}%")
            print(f"  Cooler on: {final_cooler_on}")
            
            if not final_cooler_on:
                print(f"✅ Cooling turned off successfully")
            else:
                print(f"❌ Cooling is still on")
            
            return True
        else:
            print(f"❌ Failed to turn off cooling: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Cooling off test failed: {e}")
        return False

def test_force_refresh(camera):
    """Test force refresh cooling status."""
    print(f"\n=== FORCE REFRESH TEST ===")
    
    try:
        print("Testing force refresh cooling status...")
        
        status = camera.force_refresh_cooling_status()
        
        if status.is_success:
            print(f"✅ Force refresh successful: {status.message}")
            
            info = status.data
            print(f"Refreshed status:")
            print(f"  Temperature: {info.get('temperature')}°C")
            print(f"  Cooler power: {info.get('cooler_power')}%")
            print(f"  Cooler on: {info.get('cooler_on')}")
            print(f"  Target temperature: {info.get('target_temperature')}°C")
            print(f"  Refresh attempts: {info.get('refresh_attempts')}")
            
            return True
        else:
            print(f"❌ Force refresh failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ Force refresh test failed: {e}")
        return False

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test Alpyca cooling functionality")
    parser.add_argument("--config", type=str, required=True, help="Path to configuration file")
    parser.add_argument("--target-temp", type=float, default=-10.0, help="Target temperature for cooling test")
    parser.add_argument("--verbose", action='store_true', help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = setup_logging()
    
    print("=== ALPYCA COOLING DEBUG TEST ===")
    print(f"Configuration: {args.config}")
    print(f"Target temperature: {args.target_temp}°C")
    print()
    
    try:
        # Load configuration
        config = ConfigManager(args.config)
        video_config = config.get_video_config()
        alpaca_config = video_config.get('alpaca', {})
        
        print(f"Alpyca configuration:")
        print(f"  Host: {alpaca_config.get('host', 'localhost')}")
        print(f"  Port: {alpaca_config.get('port', 11111)}")
        print(f"  Device ID: {alpaca_config.get('device_id', 0)}")
        
        # Create camera instance
        camera = AlpycaCameraWrapper(
            host=alpaca_config.get('host', 'localhost'),
            port=alpaca_config.get('port', 11111),
            device_id=alpaca_config.get('device_id', 0),
            config=config,
            logger=logger
        )
        
        # Connect to camera
        print(f"\nConnecting to Alpyca camera...")
        connect_status = camera.connect()
        if not connect_status.is_success:
            print(f"❌ Connection failed: {connect_status.message}")
            return False
        
        print(f"✅ Connected to: {camera.name}")
        
        # Run tests
        tests_passed = 0
        total_tests = 0
        
        # Test cooling properties
        total_tests += 1
        if test_cooling_properties(camera):
            tests_passed += 1
        
        # Test force refresh
        total_tests += 1
        if test_force_refresh(camera):
            tests_passed += 1
        
        # Test cooling setting
        total_tests += 1
        if test_cooling_setting(camera, args.target_temp):
            tests_passed += 1
        
        # Test cooling off
        total_tests += 1
        if test_cooling_off(camera):
            tests_passed += 1
        
        # Disconnect
        camera.disconnect()
        print(f"\n✅ Disconnected from camera")
        
        # Summary
        print(f"\n=== TEST SUMMARY ===")
        print(f"Tests passed: {tests_passed}/{total_tests}")
        print(f"Success rate: {tests_passed/total_tests*100:.1f}%")
        
        if tests_passed == total_tests:
            print("🎉 All cooling tests passed!")
            return True
        else:
            print("⚠️  Some cooling tests failed. Check the output above for details.")
            return False
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    success = main()
    sys.exit(0 if success else 1) 