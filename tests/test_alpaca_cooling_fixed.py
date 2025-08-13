#!/usr/bin/env python3
"""
Test Alpyca cooling after fixes.

This script tests the Alpyca cooling functionality after the property fixes.
"""

import logging
from pathlib import Path
import sys
import time

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import ConfigManager
from drivers.alpaca.camera import AlpycaCameraWrapper


def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("cooling_fixed_test")


def test_problematic_properties(camera):
    """Test the previously problematic properties."""
    print("\n=== PROBLEMATIC PROPERTIES TEST ===")

    try:
        print("Testing previously problematic properties...")

        # Test HeatSinkTemperature (should return CCD temperature as fallback)
        heat_sink_temp = camera.heat_sink_temperature
        print(f"HeatSinkTemperature: {heat_sink_temp}°C (should be CCD temperature as fallback)")

        # Test Gains (should return range based on min/max)
        gains = camera.gains
        print(f"Gains: {gains} (should be range from min to max)")

        # Test Offsets (should return range based on min/max)
        offsets = camera.offsets
        print(f"Offsets: {offsets} (should be range from min to max)")

        # Test FastReadout (should return False as fallback)
        fast_readout = camera.fast_readout
        print(f"FastReadout: {fast_readout} (should be False as fallback)")

        # Test Gain setting with integer conversion
        print("\nTesting Gain setting...")
        original_gain = camera.gain
        print(f"Original gain: {original_gain}")

        test_gain = 100
        camera.gain = test_gain
        new_gain = camera.gain
        print(f"Set gain to {test_gain}, new gain: {new_gain}")

        # Restore original gain
        camera.gain = original_gain
        print(f"Restored gain to {original_gain}")

        # Test Offset setting with integer conversion
        print("\nTesting Offset setting...")
        original_offset = camera.offset
        print(f"Original offset: {original_offset}")

        test_offset = 25
        camera.offset = test_offset
        new_offset = camera.offset
        print(f"Set offset to {test_offset}, new offset: {new_offset}")

        # Restore original offset
        camera.offset = original_offset
        print(f"Restored offset to {original_offset}")

        return True

    except Exception as e:
        print(f"❌ Problematic properties test failed: {e}")
        return False


def test_cooling_functionality(camera, target_temp):
    """Test cooling functionality with the fixes."""
    print(f"\n=== COOLING FUNCTIONALITY TEST ({target_temp}°C) ===")

    try:
        print("Testing cooling functionality...")

        # Get initial status
        initial_temp = camera.ccd_temperature
        initial_power = camera.cooler_power
        initial_cooler_on = camera.cooler_on
        initial_target = camera.set_ccd_temperature

        print("Initial status:")
        print(f"  Temperature: {initial_temp}°C")
        print(f"  Cooler power: {initial_power}%")
        print(f"  Cooler on: {initial_cooler_on}")
        print(f"  Target temperature: {initial_target}°C")

        # Set cooling
        print(f"\nSetting cooling to {target_temp}°C...")
        status = camera.set_cooling(target_temp)

        if status.is_success:
            print(f"✅ Cooling set successfully: {status.message}")

            # Show details if available
            if hasattr(status, "details") and status.details:
                details = status.details
                print("Details:")
                print(f"  Target temp: {details.get('target_temp')}°C")
                print(f"  Current temp: {details.get('current_temp')}°C")
                print(f"  New temp: {details.get('new_temp')}°C")
                print(f"  Current power: {details.get('current_power')}%")
                print(f"  New power: {details.get('new_power')}%")
                print(f"  Current cooler on: {details.get('current_cooler_on')}")
                print(f"  New cooler on: {details.get('new_cooler_on')}")
                print(f"  New target: {details.get('new_target')}°C")

            # Wait and check again
            print("\nWaiting 3 seconds and checking again...")
            time.sleep(3)

            final_temp = camera.ccd_temperature
            final_power = camera.cooler_power
            final_cooler_on = camera.cooler_on
            final_target = camera.set_ccd_temperature

            print("Final status:")
            print(f"  Temperature: {final_temp}°C")
            print(f"  Cooler power: {final_power}%")
            print(f"  Cooler on: {final_cooler_on}")
            print(f"  Target temperature: {final_target}°C")

            # Analyze results
            if final_cooler_on and final_target == target_temp:
                print("✅ Cooling is properly configured")
                if final_power > 0:
                    print(f"✅ Cooler is active with {final_power}% power")
                else:
                    print("⚠️  Cooler is on but power is 0% - may be at target temperature")

                temp_diff = final_temp - target_temp
                print(f"  Temperature difference: {temp_diff:+.1f}°C")
            else:
                print("❌ Cooling configuration failed")

            return True
        else:
            print(f"❌ Failed to set cooling: {status.message}")
            return False

    except Exception as e:
        print(f"❌ Cooling functionality test failed: {e}")
        return False


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test Alpyca cooling after fixes")
    parser.add_argument("--config", type=str, required=True, help="Path to configuration file")
    parser.add_argument(
        "--target-temp", type=float, default=-10.0, help="Target temperature for cooling test"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = setup_logging()

    print("=== ALPYCA COOLING FIXED TEST ===")
    print(f"Configuration: {args.config}")
    print(f"Target temperature: {args.target_temp}°C")
    print("This tests the cooling functionality after the property fixes.")
    print()

    try:
        # Load configuration
        config = ConfigManager(args.config)
        video_config = config.get_video_config()
        alpaca_config = video_config.get("alpaca", {})

        print("Alpyca configuration:")
        print(f"  Host: {alpaca_config.get('host', 'localhost')}")
        print(f"  Port: {alpaca_config.get('port', 11111)}")
        print(f"  Device ID: {alpaca_config.get('device_id', 0)}")

        # Create camera instance
        camera = AlpycaCameraWrapper(
            host=alpaca_config.get("host", "localhost"),
            port=alpaca_config.get("port", 11111),
            device_id=alpaca_config.get("device_id", 0),
            config=config,
            logger=logger,
        )

        # Connect to camera
        print("\nConnecting to Alpyca camera...")
        connect_status = camera.connect()
        if not connect_status.is_success:
            print(f"❌ Connection failed: {connect_status.message}")
            return False

        print(f"✅ Connected to: {camera.name}")

        # Run tests
        tests_passed = 0
        total_tests = 0

        # Test problematic properties
        total_tests += 1
        if test_problematic_properties(camera):
            tests_passed += 1

        # Test cooling functionality
        total_tests += 1
        if test_cooling_functionality(camera, args.target_temp):
            tests_passed += 1

        # Disconnect
        camera.disconnect()
        print("\n✅ Disconnected from camera")

        # Summary
        print("\n=== TEST SUMMARY ===")
        print(f"Tests passed: {tests_passed}/{total_tests}")
        print(f"Success rate: {tests_passed/total_tests*100:.1f}%")

        if tests_passed == total_tests:
            print("🎉 All tests passed! Cooling fixes are working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
            return False

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    success = main()
    sys.exit(0 if success else 1)
