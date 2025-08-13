#!/usr/bin/env python3
"""
Specialized cooling power test script.
This script focuses on diagnosing and fixing the cooling power issue.
"""

import logging
from pathlib import Path
import sys
import time

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from ascom_camera import ASCOMCamera
from config_manager import ConfigManager


def setup_logging():
    """Setup detailed logging for debugging."""
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("cooling_power_debug")


def diagnose_cooling_power(camera, logger):
    """Diagnose the cooling power issue."""
    print("\n=== COOLING POWER DIAGNOSIS ===")

    try:
        # Check if cooler power property exists
        has_cooler_power = hasattr(camera.camera, "CoolerPower")
        print(f"CoolerPower property available: {has_cooler_power}")

        if not has_cooler_power:
            print("❌ CoolerPower property not available - this is the root cause")
            return False

        # Check if cooler is on
        cooler_on = camera.camera.CoolerOn if hasattr(camera.camera, "CoolerOn") else False
        print(f"Cooler on: {cooler_on}")

        if not cooler_on:
            print("❌ Cooler is not on - turning it on...")
            camera.camera.CoolerOn = True
            time.sleep(1)
            cooler_on = camera.camera.CoolerOn
            print(f"Cooler on after setting: {cooler_on}")

        # Try multiple approaches to read cooler power
        print("\nTrying different approaches to read cooler power:")

        # Approach 1: Direct read
        try:
            power1 = camera.camera.CoolerPower
            print(f"  Direct read: {power1}%")
        except Exception as e:
            print(f"  Direct read failed: {e}")
            power1 = None

        # Approach 2: Multiple reads
        powers = []
        for i in range(5):
            try:
                power = camera.camera.CoolerPower
                powers.append(power)
                print(f"  Read {i+1}: {power}%")
                time.sleep(0.5)
            except Exception as e:
                print(f"  Read {i+1} failed: {e}")

        # Approach 3: Check if power is actually 0 or just not updating
        if powers:
            avg_power = sum(powers) / len(powers)
            print(f"  Average power: {avg_power}%")

            if avg_power == 0:
                print("⚠️  Cooler power is consistently 0% - possible issues:")
                print("    1. Target temperature already reached")
                print("    2. Cooling system not active")
                print("    3. ASCOM driver not updating power value")
                print("    4. Hardware issue")
            else:
                print(f"✅ Cooler power detected: {avg_power}%")

        # Check target temperature
        target_temp = (
            camera.camera.SetCCDTemperature if hasattr(camera.camera, "SetCCDTemperature") else None
        )
        current_temp = (
            camera.camera.CCDTemperature if hasattr(camera.camera, "CCDTemperature") else None
        )

        print("\nTemperature analysis:")
        print(f"  Current temperature: {current_temp}°C")
        print(f"  Target temperature: {target_temp}°C")

        if current_temp is not None and target_temp is not None:
            temp_diff = current_temp - target_temp
            print(f"  Temperature difference: {temp_diff:+.1f}°C")

            if temp_diff <= 0:
                print("  ℹ️  Current temperature is at or below target - cooler may be idle")
            else:
                print("  ⚠️  Current temperature is above target - cooler should be active")

        return True

    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        return False


def test_cooling_power_workaround(camera, logger):
    """Test workarounds for the cooling power issue."""
    print("\n=== COOLING POWER WORKAROUND TEST ===")

    try:
        # Workaround 1: Set a very low target temperature to force cooling
        print("Workaround 1: Setting very low target temperature (-20°C)...")
        camera.camera.SetCCDTemperature = -20.0
        time.sleep(2)

        # Read power multiple times
        powers = []
        for _i in range(10):
            try:
                power = camera.camera.CoolerPower
                powers.append(power)
                print(f"  Power after -20°C target: {power}%")
                time.sleep(1)
            except Exception as e:
                print(f"  Read failed: {e}")

        # Workaround 2: Try setting cooler power directly if available
        if hasattr(camera.camera, "SetCoolerPower"):
            print("\nWorkaround 2: Setting cooler power directly...")
            try:
                camera.camera.SetCoolerPower = 50.0  # Set to 50%
                time.sleep(2)

                power = camera.camera.CoolerPower
                print(f"  Power after direct setting: {power}%")

                # Reset to automatic mode
                camera.camera.SetCCDTemperature = -10.0

            except Exception as e:
                print(f"  Direct power setting failed: {e}")
        else:
            print("\nWorkaround 2: Direct power control not available")

        # Workaround 3: Monitor temperature change instead of power
        print("\nWorkaround 3: Monitoring temperature change...")
        initial_temp = camera.camera.CCDTemperature
        print(f"  Initial temperature: {initial_temp}°C")

        for i in range(10):
            time.sleep(2)
            current_temp = camera.camera.CCDTemperature
            temp_change = current_temp - initial_temp
            print(f"  After {2*(i+1)}s: {current_temp}°C (change: {temp_change:+.1f}°C)")

            if temp_change < -1.0:
                print("  ✅ Temperature is decreasing - cooling is working!")
                break

        return True

    except Exception as e:
        print(f"❌ Error during workaround test: {e}")
        return False


def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description="Cooling power diagnosis and workaround test")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--driver", type=str, help="ASCOM driver ID")
    parser.add_argument("--target-temp", type=float, default=-10.0, help="Target temperature")

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

    print("=== COOLING POWER DIAGNOSIS ===")
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

        # Set target temperature
        print(f"\nSetting target temperature to {args.target_temp}°C...")
        cooling_status = camera.set_cooling(args.target_temp)
        print(f"Cooling status: {cooling_status.message}")

        # Wait a moment for cooling to start
        time.sleep(3)

        # Run diagnosis
        diagnose_cooling_power(camera, logger)

        # Test workarounds
        test_cooling_power_workaround(camera, logger)

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
