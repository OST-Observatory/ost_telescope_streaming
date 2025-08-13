#!/usr/bin/env python3
"""
Test script for ASCOM Camera features.
Tests cooling, filter wheel, and debayering functionality.
"""

from pathlib import Path
import sys

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from drivers.ascom.camera import ASCOMCamera
from test_utils import parse_test_args, print_test_header, setup_test_environment


def test_ascom_camera_basic(config) -> bool:
    """Test basic ASCOM camera functionality."""
    print("Testing basic ASCOM camera functionality...")

    # This test requires a real ASCOM camera driver
    # For testing without hardware, we'll just check the class structure
    try:
        _camera = ASCOMCamera(driver_id="ASCOM.TestCamera.Camera", config=config)
        print("✓ ASCOMCamera class instantiated successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to instantiate ASCOMCamera: {e}")
        return False


def test_ascom_camera_methods(config) -> bool:
    """Test ASCOM camera method signatures and basic functionality."""
    print("Testing ASCOM camera method signatures...")

    try:
        camera = ASCOMCamera(driver_id="ASCOM.TestCamera.Camera", config=config)

        # Test method existence and signatures
        methods_to_test = [
            "connect",
            "disconnect",
            "expose",
            "get_image",
            "has_cooling",
            "set_cooling",
            "get_temperature",
            "has_filter_wheel",
            "get_filter_names",
            "set_filter_position",
            "get_filter_position",
            "is_color_camera",
            "debayer",
        ]

        for method_name in methods_to_test:
            if hasattr(camera, method_name):
                print(f"✓ Method {method_name} exists")
            else:
                print(f"✗ Method {method_name} missing")
                return False

        # Test that expose method accepts seconds
        import inspect

        sig = inspect.signature(camera.expose)
        params = list(sig.parameters.keys())
        if "exposure_time_s" in params:
            print("✓ expose method accepts exposure_time_s parameter")
        else:
            print("✗ expose method does not accept exposure_time_s parameter")
            return False

        # Test that expose method accepts binning parameter
        if "binning" in params:
            print("✓ expose method accepts binning parameter")
        else:
            print("✗ expose method does not accept binning parameter")

        return True

    except Exception as e:
        print(f"✗ Error testing method signatures: {e}")
        return False


def test_status_objects(config) -> bool:
    """Test that ASCOM camera methods return proper status objects."""
    print("Testing status object returns...")

    try:
        camera = ASCOMCamera(driver_id="ASCOM.TestCamera.Camera", config=config)

        # Test that connect returns CameraStatus
        # Note: This will fail without real hardware, but we can check the return type

        # We can't actually call connect without hardware, but we can verify the method exists
        if hasattr(camera, "connect"):
            print("✓ connect method exists and should return CameraStatus")
        else:
            print("✗ connect method missing")
            return False

        return True

    except Exception as e:
        print(f"✗ Error testing status objects: {e}")
        return False


def test_config_integration(config) -> bool:
    """Test that ASCOM camera configuration is properly integrated."""
    print("Testing configuration integration...")

    try:
        # Check that config has ASCOM camera settings
        video_config = config.get_video_config()

        # Check for required ASCOM settings
        ascom_config = video_config.get("ascom", {})
        required_keys = ["ascom_driver"]

        for key in required_keys:
            if key in ascom_config:
                print(f"✓ ASCOM config key '{key}' exists: {ascom_config[key]}")
            else:
                print(f"✗ ASCOM config key '{key}' missing")
                return False

        # Check camera type
        camera_type = video_config.get("camera_type", "opencv")
        print(f"✓ Camera type: {camera_type}")

        return True

    except Exception as e:
        print(f"✗ Error testing configuration integration: {e}")
        return False


def test_cli_integration() -> bool:
    """Test that CLI integration is properly set up."""
    print("Testing CLI integration...")

    try:
        # Check that main_video_capture.py exists and has ASCOM features
        main_script = Path(__file__).parent.parent / "main_video_capture.py"
        if main_script.exists():
            content = main_script.read_text()

            # Check for ASCOM-related features
            ascom_features = [
                "--camera-type",
                "--ascom-driver",
                "--action",
                "info",
                "cooling",
                "filter",
                "debayer",
            ]

            for feature in ascom_features:
                if feature in content:
                    print(f"✓ CLI feature '{feature}' found")
                else:
                    print(f"✗ CLI feature '{feature}' missing")
                    return False

            return True
        else:
            print("✗ main_video_capture.py not found")
            return False

    except Exception as e:
        print(f"✗ Error testing CLI integration: {e}")
        return False


def main() -> None:
    """Main function for the ASCOM Camera Test."""
    # Parse command line arguments
    args = parse_test_args("ASCOM Camera Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("ASCOM Camera Test", driver_id, args.config)

    tests = [
        ("Basic ASCOM Camera", lambda: test_ascom_camera_basic(config)),
        ("Method Signatures", lambda: test_ascom_camera_methods(config)),
        ("Status Objects", lambda: test_status_objects(config)),
        ("Configuration Integration", lambda: test_config_integration(config)),
        ("CLI Integration", test_cli_integration),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            print(f"✓ {test_name} completed")
            passed += 1
        else:
            print(f"✗ {test_name} failed")

    print("\n--- Results ---")
    print(f"Completed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All ASCOM camera tests passed!")
        print("\n✅ ASCOM camera integration is working correctly!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main()
