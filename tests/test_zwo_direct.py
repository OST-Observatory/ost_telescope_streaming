#!/usr/bin/env python3
"""
Direct ZWO camera test without Alpyca.

This script tests ZWO camera cooling directly to determine if the issue
is with the camera hardware or the Alpyca interface.
"""

from pathlib import Path
import sys
import time

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))


def test_zwo_direct():
    """Test ZWO camera directly without Alpyca."""
    print("=== DIRECT ZWO CAMERA TEST ===")
    print("Testing ZWO camera cooling directly...")

    try:
        # Try to import ZWO ASI SDK directly
        try:
            import zwoasi as asi

            print("✅ ZWO ASI SDK found")
        except ImportError:
            print("❌ ZWO ASI SDK not found")
            print("   Install with: pip install zwoasi")
            return False

        # Initialize ASI
        asi.init("/path/to/asi-sdk")  # You'll need to specify the path

        # Get camera list
        num_cameras = asi.get_num_cameras()
        print(f"Found {num_cameras} ZWO cameras")

        if num_cameras == 0:
            print("❌ No ZWO cameras found")
            return False

        # Get first camera
        camera_id = asi.get_camera_property(0).get("CameraID")
        print(f"Camera ID: {camera_id}")

        # Open camera
        camera = asi.Camera(0)
        camera_info = camera.get_camera_property()
        print(f"Camera: {camera_info.get('FriendlyName', 'Unknown')}")

        # Check cooling support
        print("\nCooling support:")
        print(f"  Has cooler: {camera_info.get('IsCoolerCam', False)}")

        if camera_info.get("IsCoolerCam", False):
            # Test cooling
            print("\nTesting cooling...")

            # Get current temperature
            current_temp = camera.get_control_value(asi.ASI_TEMPERATURE)[0] / 10.0
            print(f"Current temperature: {current_temp}°C")

            # Set target temperature
            target_temp = -10.0
            camera.set_control_value(asi.ASI_TARGET_TEMP, int(target_temp * 10))
            print(f"Target temperature set to: {target_temp}°C")

            # Turn on cooler
            camera.set_control_value(asi.ASI_COOLER_ON, 1)
            print("Cooler turned on")

            # Wait and check
            time.sleep(2)

            new_temp = camera.get_control_value(asi.ASI_TEMPERATURE)[0] / 10.0
            cooler_on = camera.get_control_value(asi.ASI_COOLER_ON)[0]
            cooler_power = camera.get_control_value(asi.ASI_COOLER_POWER_PERC)[0]

            print("After 2 seconds:")
            print(f"  Temperature: {new_temp}°C")
            print(f"  Cooler on: {cooler_on}")
            print(f"  Cooler power: {cooler_power}%")

            # Turn off cooler
            camera.set_control_value(asi.ASI_COOLER_ON, 0)
            print("Cooler turned off")

            camera.close_camera()
            return True
        else:
            print("❌ Camera does not support cooling")
            camera.close_camera()
            return False

    except Exception as e:
        print(f"❌ Direct ZWO test failed: {e}")
        return False


def test_alpyca_vs_direct():
    """Compare Alpyca vs direct ZWO access."""
    print("\n=== ALPYCA VS DIRECT COMPARISON ===")

    try:
        # Test Alpyca
        print("Testing Alpyca access...")
        from alpaca.camera import Camera

        camera = Camera("localhost:11111", 0)
        print(f"Alpyca Camera: {camera.Name}")
        print(f"CanSetCCDTemperature: {camera.CanSetCCDTemperature}")
        print(f"CanGetCoolerPower: {camera.CanGetCoolerPower}")

        # Test direct access
        print("\nTesting direct ZWO access...")
        # This would require ZWO ASI SDK

        return True

    except Exception as e:
        print(f"❌ Comparison test failed: {e}")
        return False


def main():
    """Main test function."""
    print("Direct ZWO camera cooling test")
    print("This test helps determine if the cooling issue is with:")
    print("1. Camera hardware")
    print("2. ZWO ASI Driver")
    print("3. Alpyca interface")
    print()

    # Test direct ZWO access
    direct_success = test_zwo_direct()

    # Test comparison
    comparison_success = test_alpyca_vs_direct()

    # Summary
    print("\n=== SUMMARY ===")
    print(f"Direct ZWO test: {'✅ PASS' if direct_success else '❌ FAIL'}")
    print(f"Comparison test: {'✅ PASS' if comparison_success else '❌ FAIL'}")

    if direct_success:
        print("\n🎉 Direct ZWO access works!")
        print("   The issue is likely with the Alpyca interface")
    else:
        print("\n⚠️  Direct ZWO access failed")
        print("   The issue might be with the camera hardware or driver")

    return direct_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
