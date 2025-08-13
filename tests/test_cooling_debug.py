#!/usr/bin/env python3
"""
Comprehensive cooling debug test script.
This script provides detailed information about camera cooling capabilities and status.
"""

import logging
from pathlib import Path
import sys

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from ascom_camera import ASCOMCamera
from config_manager import ConfigManager


def setup_logging():
    """Setup detailed logging for debugging."""
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("cooling_debug")


def test_cooling_capabilities(camera, logger):
    """Test cooling capabilities and provide detailed information."""
    print("\n=== COOLING CAPABILITIES TEST ===")

    # Check if cooling is supported
    has_cooling = camera.has_cooling()
    print(f"Cooling supported: {has_cooling}")

    if not has_cooling:
        print("❌ Camera does not support cooling")
        return False

    # Check available cooling properties
    properties = [
        "CanSetCCDTemperature",
        "CCDTemperature",
        "SetCCDTemperature",
        "CoolerOn",
        "CoolerPower",
        "SetCoolerPower",
    ]

    print("\nAvailable cooling properties:")
    for prop in properties:
        available = hasattr(camera.camera, prop)
        print(f"  {prop}: {'✅' if available else '❌'}")

        if available:
            try:
                value = getattr(camera.camera, prop)
                print(f"    Value: {value}")
            except Exception as e:
                print(f"    Error reading: {e}")

    return True


def test_cooling_status(camera, logger):
    """Test current cooling status."""
    print("\n=== CURRENT COOLING STATUS ===")

    try:
        # Get comprehensive cooling information
        cooling_info = camera.get_smart_cooling_info()

        if cooling_info.is_success:
            info = cooling_info.data
            print(f"Current temperature: {info.get('temperature')}°C")
            print(f"Target temperature: {info.get('target_temperature')}°C")
            print(f"Cooler power: {info.get('cooler_power')}%")
            print(f"Cooler on: {info.get('cooler_on')}")
            print(f"Can set cooler power: {info.get('can_set_cooler_power')}")
        else:
            print(f"Failed to get cooling info: {cooling_info.message}")
            return False

    except Exception as e:
        print(f"Error getting cooling status: {e}")
        return False

    return True


def test_cooling_control(camera, logger, target_temp=-10.0):
    """Test cooling control functionality."""
    print(f"\n=== COOLING CONTROL TEST (Target: {target_temp}°C) ===")

    try:
        # Test setting cooling
        print(f"Setting target temperature to {target_temp}°C...")
        cooling_status = camera.set_cooling(target_temp)

        print(f"Cooling status: {cooling_status.level.value.upper()} - {cooling_status.message}")

        if (
            cooling_status.is_success
            and hasattr(cooling_status, "details")
            and cooling_status.details
        ):
            details = cooling_status.details
            print("\nDetailed cooling information:")
            print(f"  Target temperature: {details.get('target_temp')}°C")
            print(f"  Actual target: {details.get('actual_target')}°C")
            print(f"  Temperature before: {details.get('current_temp')}°C")
            print(f"  Temperature after: {details.get('new_temp')}°C")
            print(f"  Cooler power before: {details.get('current_power')}%")
            print(f"  Cooler power after: {details.get('new_power')}%")
            print(f"  Cooler on before: {details.get('current_cooler_on')}")
            print(f"  Cooler on after: {details.get('new_cooler_on')}")

            # Analyze the results
            temp_before = details.get("current_temp")
            temp_after = details.get("new_temp")
            power_after = details.get("new_power")
            cooler_on = details.get("new_cooler_on")

            print("\nAnalysis:")
            if temp_before is not None and temp_after is not None:
                temp_change = temp_after - temp_before
                print(f"  Temperature change: {temp_change:+.1f}°C")

                if temp_change > 0:
                    print("  ⚠️  Temperature increased - this might indicate:")
                    print("     - Camera is warming up from cold start")
                    print("     - Ambient temperature is higher than target")
                    print("     - Cooling system needs time to stabilize")
                elif temp_change < 0:
                    print("  ✅ Temperature decreased - cooling is working")
                else:
                    print("  ℹ️  Temperature unchanged - may need more time")

            if power_after is not None:
                if power_after > 0:
                    print(f"  ✅ Cooler power active: {power_after}%")
                else:
                    print("  ⚠️  Cooler power is 0% - may indicate:")
                    print("     - Target temperature already reached")
                    print("     - Cooling system not active")
                    print("     - Hardware issue")

            if cooler_on:
                print("  ✅ Cooler is turned on")
            else:
                print("  ❌ Cooler is turned off")

        return cooling_status.is_success

    except Exception as e:
        print(f"Error testing cooling control: {e}")
        return False


def test_camera_type_detection(camera, logger):
    """Test camera type detection."""
    print("\n=== CAMERA TYPE DETECTION TEST ===")

    try:
        # Check camera type
        is_color = camera.is_color_camera()
        print(f"Camera type: {'Color' if is_color else 'Monochrome'}")

        # Get sensor type information
        sensor_type = camera.sensor_type
        print(f"Bayer pattern: {sensor_type if sensor_type else 'None (monochrome)'}")

        # Check driver information
        print(f"Driver ID: {camera.driver_id}")

        # Check ASCOM properties
        if hasattr(camera.camera, "SensorType"):
            ascom_sensor_type = camera.camera.SensorType
            print(f"ASCOM SensorType: {ascom_sensor_type}")

        if hasattr(camera.camera, "IsColor"):
            ascom_is_color = camera.camera.IsColor
            print(f"ASCOM IsColor: {ascom_is_color}")

        return True

    except Exception as e:
        print(f"Error testing camera type detection: {e}")
        return False


def test_cooling_stabilization(camera, logger, timeout=30):
    """Test cooling stabilization and power consumption."""
    print(f"\n=== COOLING STABILIZATION TEST (Timeout: {timeout}s) ===")

    try:
        print("Waiting for cooling system to stabilize and show power consumption...")
        stabilization_status = camera.wait_for_cooling_stabilization(timeout=timeout)

        if stabilization_status.is_success:
            info = stabilization_status.data
            print("✅ Cooling stabilized successfully!")
            print("Final status:")
            print(f"  Temperature: {info.get('temperature')}°C")
            print(f"  Cooler power: {info.get('cooler_power')}%")
            print(f"  Cooler on: {info.get('cooler_on')}")
            print(f"  Target temperature: {info.get('target_temperature')}°C")
            return True
        else:
            print(f"⚠️  Cooling stabilization: {stabilization_status.message}")
            if hasattr(stabilization_status, "data") and stabilization_status.data:
                info = stabilization_status.data
                print("Final status (timeout):")
                print(f"  Temperature: {info.get('temperature')}°C")
                print(f"  Cooler power: {info.get('cooler_power')}%")
                print(f"  Cooler on: {info.get('cooler_on')}")
            return False

    except Exception as e:
        print(f"❌ Error testing cooling stabilization: {e}")
        return False


def test_force_refresh(camera, logger):
    """Test forced cooling status refresh."""
    print("\n=== FORCE REFRESH TEST ===")

    try:
        print("Forcing cooling status refresh...")
        refresh_status = camera.force_refresh_cooling_status()

        if refresh_status.is_success:
            info = refresh_status.data
            print("✅ Cooling status refreshed successfully!")
            print("Refresh results:")
            print(f"  Temperature: {info.get('temperature')}°C")
            print(f"  Cooler power: {info.get('cooler_power')}%")
            print(f"  Cooler on: {info.get('cooler_on')}")
            print(f"  Target temperature: {info.get('target_temperature')}°C")
            print(f"  Refresh attempts: {info.get('refresh_attempts')}")
            return True
        else:
            print(f"❌ Force refresh failed: {refresh_status.message}")
            return False

    except Exception as e:
        print(f"❌ Error testing force refresh: {e}")
        return False


def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive cooling debug test")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--driver", type=str, help="ASCOM driver ID")
    parser.add_argument(
        "--target-temp", type=float, default=-10.0, help="Target temperature for cooling test"
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging()

    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()

    # Get driver ID
    driver_id = args.driver or config.get_video_config()["ascom"]["ascom_driver"]

    print("=== COOLING DEBUG TEST ===")
    print(f"Driver: {driver_id}")
    print(f"Target temperature: {args.target_temp}°C")

    try:
        # Create camera instance
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)

        # Connect to camera
        print("\nConnecting to camera...")
        connect_status = camera.connect()

        if not connect_status.is_success:
            print(f"❌ Connection failed: {connect_status.message}")
            return False

        print("✅ Connected successfully")

        # Test camera type detection
        test_camera_type_detection(camera, logger)

        # Test cooling capabilities
        if test_cooling_capabilities(camera, logger):
            # Test current status
            test_cooling_status(camera, logger)

            # Test cooling control
            test_cooling_control(camera, logger, args.target_temp)

            # Test cooling stabilization
            test_cooling_stabilization(camera, logger)

            # Test force refresh
            test_force_refresh(camera, logger)

        # Disconnect
        camera.disconnect()
        print("\n✅ Disconnected from camera")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
