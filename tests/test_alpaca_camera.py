#!/usr/bin/env python3
"""
Test script for Alpyca camera integration.

This script tests the AlpycaCameraWrapper class and all its features.
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
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("alpaca_test")


def test_connection():
    """Test basic camera connection."""
    print("\n=== CONNECTION TEST ===")

    try:
        # Load configuration if provided
        config = None
        host = "localhost"
        port = 11111
        device_id = 0

        if len(sys.argv) > 2 and sys.argv[1] == "--config":
            config_file = sys.argv[2]
            print(f"Loading configuration from: {config_file}")
            try:
                config = ConfigManager(config_file)
                video_config = config.get_video_config()
                alpaca_config = video_config.get("alpaca", {})

                host = alpaca_config.get("host", "localhost")
                port = alpaca_config.get("port", 11111)
                device_id = alpaca_config.get("device_id", 0)

                print(f"Using config: host={host}, port={port}, device_id={device_id}")
            except Exception as e:
                print(f"⚠️  Failed to load configuration: {e}")
                print("Using default configuration")
        else:
            print("Using default configuration")

        # Create camera instance
        camera = AlpycaCameraWrapper(
            host=host, port=port, device_id=device_id, config=config, logger=setup_logging()
        )

        # Test connection
        print("Testing Alpyca camera connection...")
        status = camera.connect()

        if not status.is_success:
            print(f"❌ Connection failed: {status.message}")
            print("💡 Make sure Alpaca server is running on localhost:11111")
            return False

        print(f"✅ Connected to: {camera.name}")
        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def test_camera_properties(camera):
    """Test camera properties."""
    print("\n=== CAMERA PROPERTIES TEST ===")

    try:
        # Core properties
        print(f"Name: {camera.name}")
        print(f"Description: {camera.description}")
        print(f"Driver: {camera.driver_info}")
        print(f"Version: {camera.driver_version}")
        print(f"Interface: {camera.interface_version}")
        print(f"Connected: {camera.connected}")

        # Sensor properties
        print("\nSensor Information:")
        print(f"  Sensor: {camera.sensor_name}")
        print(f"  Type: {camera.sensor_type}")
        print(f"  Size: {camera.camera_x_size}x{camera.camera_y_size}")
        print(f"  Pixel size: {camera.pixel_size_x}x{camera.pixel_size_y} μm")
        print(f"  Max ADU: {camera.max_adu}")
        print(f"  Electrons per ADU: {camera.electrons_per_adu}")
        print(f"  Full well capacity: {camera.full_well_capacity}")

        # Camera type detection
        print("\nCamera Type Detection:")
        is_color = camera.is_color_camera()
        print(f"  Is color camera: {is_color}")

        return True

    except Exception as e:
        print(f"❌ Properties test failed: {e}")
        return False


def test_exposure_properties(camera):
    """Test exposure-related properties."""
    print("\n=== EXPOSURE PROPERTIES TEST ===")

    try:
        print("Exposure limits:")

        # Test exposure_min
        try:
            min_exp = camera.exposure_min
            print(f"  Min: {min_exp} s")
        except Exception as e:
            print(f"  Min: Not implemented ({e})")

        # Test exposure_max
        try:
            max_exp = camera.exposure_max
            print(f"  Max: {max_exp} s")
        except Exception as e:
            print(f"  Max: Not implemented ({e})")

        # Test exposure_resolution
        try:
            res_exp = camera.exposure_resolution
            print(f"  Resolution: {res_exp} s")
        except Exception as e:
            print(f"  Resolution: Not implemented ({e})")

        print("\nLast exposure:")

        # Test last_exposure_duration
        try:
            last_duration = camera.last_exposure_duration
            print(f"  Duration: {last_duration} s")
        except Exception as e:
            print(f"  Duration: Not implemented ({e})")

        # Test last_exposure_start_time
        try:
            last_start = camera.last_exposure_start_time
            print(f"  Start time: {last_start}")
        except Exception as e:
            print(f"  Start time: Not implemented ({e})")

        print("\nCurrent state:")

        # Test camera_state
        try:
            state = camera.camera_state
            print(f"  Camera state: {state}")
        except Exception as e:
            print(f"  Camera state: Not implemented ({e})")

        # Test image_ready
        try:
            ready = camera.image_ready
            print(f"  Image ready: {ready}")
        except Exception as e:
            print(f"  Image ready: Not implemented ({e})")

        # Test percent_completed
        try:
            percent = camera.percent_completed
            print(f"  Percent completed: {percent}%")
        except Exception as e:
            print(f"  Percent completed: Not implemented ({e})")

        return True

    except Exception as e:
        print(f"❌ Exposure properties test failed: {e}")
        return False


def test_binning_properties(camera):
    """Test binning properties."""
    print("\n=== BINNING PROPERTIES TEST ===")

    try:
        # Test current binning
        try:
            current_bin_x = camera.bin_x
            current_bin_y = camera.bin_y
            print(f"Current binning: {current_bin_x}x{current_bin_y}")
        except Exception as e:
            print(f"Current binning: Not implemented ({e})")

        # Test max binning
        try:
            max_bin_x = camera.max_bin_x
            max_bin_y = camera.max_bin_y
            print(f"Max binning: {max_bin_x}x{max_bin_y}")
        except Exception as e:
            print(f"Max binning: Not implemented ({e})")

        # Test asymmetric binning
        try:
            can_asymmetric = camera.can_asymmetric_bin
            print(f"Can asymmetric bin: {can_asymmetric}")
        except Exception as e:
            print(f"Can asymmetric bin: Not implemented ({e})")

        # Test setting binning
        try:
            if camera.max_bin_x and camera.max_bin_x > 1:
                print("\nTesting binning change...")
                original_bin_x = camera.bin_x
                original_bin_y = camera.bin_y

                # Set to 2x2 if supported
                if camera.max_bin_x >= 2 and camera.max_bin_y >= 2:
                    camera.bin_x = 2
                    camera.bin_y = 2
                    print(f"  Set binning to: {camera.bin_x}x{camera.bin_y}")

                    # Restore original
                    camera.bin_x = original_bin_x
                    camera.bin_y = original_bin_y
                    print(f"  Restored binning to: {camera.bin_x}x{camera.bin_y}")
                else:
                    print("  Skipping binning test (max binning < 2)")
            else:
                print("  Skipping binning test (max binning not available)")
        except Exception as e:
            print(f"  Binning change test failed: {e}")

        return True

    except Exception as e:
        print(f"❌ Binning properties test failed: {e}")
        return False


def test_cooling_properties(camera):
    """Test cooling properties."""
    print("\n=== COOLING PROPERTIES TEST ===")

    try:
        print("Cooling support:")

        # Test cooling support
        try:
            can_set_temp = camera.can_set_ccd_temperature
            print(f"  Can set CCD temperature: {can_set_temp}")
        except Exception as e:
            print(f"  Can set CCD temperature: Not implemented ({e})")

        try:
            can_get_power = camera.can_get_cooler_power
            print(f"  Can get cooler power: {can_get_power}")
        except Exception as e:
            print(f"  Can get cooler power: Not implemented ({e})")

        # Test current cooling status
        if camera.can_set_ccd_temperature:
            print("\nCurrent cooling status:")

            try:
                ccd_temp = camera.ccd_temperature
                print(f"  CCD temperature: {ccd_temp}°C")
            except Exception as e:
                print(f"  CCD temperature: Not implemented ({e})")

            try:
                target_temp = camera.set_ccd_temperature
                print(f"  Target temperature: {target_temp}°C")
            except Exception as e:
                print(f"  Target temperature: Not implemented ({e})")

            try:
                cooler_on = camera.cooler_on
                print(f"  Cooler on: {cooler_on}")
            except Exception as e:
                print(f"  Cooler on: Not implemented ({e})")

            try:
                cooler_power = camera.cooler_power
                print(f"  Cooler power: {cooler_power}%")
            except Exception as e:
                print(f"  Cooler power: Not implemented ({e})")

            try:
                heat_sink_temp = camera.heat_sink_temperature
                print(f"  Heat sink temperature: {heat_sink_temp}°C")
            except Exception as e:
                print(f"  Heat sink temperature: Not implemented ({e})")
        else:
            print("  Cooling not supported by this camera")

        return True

    except Exception as e:
        print(f"❌ Cooling properties test failed: {e}")
        return False


def test_gain_offset_properties(camera):
    """Test gain and offset properties."""
    print("\n=== GAIN/OFFSET PROPERTIES TEST ===")

    try:
        print("Gain settings:")

        # Test gain properties
        try:
            current_gain = camera.gain
            print(f"  Current gain: {current_gain}")
        except Exception as e:
            print(f"  Current gain: Not implemented ({e})")

        try:
            gain_min = camera.gain_min
            print(f"  Min gain: {gain_min}")
        except Exception as e:
            print(f"  Min gain: Not implemented ({e})")

        try:
            gain_max = camera.gain_max
            print(f"  Max gain: {gain_max}")
        except Exception as e:
            print(f"  Max gain: Not implemented ({e})")

        try:
            gains = camera.gains
            print(f"  Available gains: {gains}")
        except Exception as e:
            print(f"  Available gains: Not implemented ({e})")

        print("\nOffset settings:")

        # Test offset properties
        try:
            current_offset = camera.offset
            print(f"  Current offset: {current_offset}")
        except Exception as e:
            print(f"  Current offset: Not implemented ({e})")

        try:
            offset_min = camera.offset_min
            print(f"  Min offset: {offset_min}")
        except Exception as e:
            print(f"  Min offset: Not implemented ({e})")

        try:
            offset_max = camera.offset_max
            print(f"  Max offset: {offset_max}")
        except Exception as e:
            print(f"  Max offset: Not implemented ({e})")

        try:
            offsets = camera.offsets
            print(f"  Available offsets: {offsets}")
        except Exception as e:
            print(f"  Available offsets: Not implemented ({e})")

        # Test setting gain/offset if supported
        try:
            if camera.gain is not None:
                print("\nTesting gain/offset change...")
                original_gain = camera.gain
                original_offset = camera.offset

                # Try to set different values
                if camera.gain_max and camera.gain_max > camera.gain_min:
                    test_gain = min(camera.gain_max, camera.gain + 10)
                    camera.gain = test_gain
                    print(f"  Set gain to: {camera.gain}")

                    # Restore original
                    camera.gain = original_gain
                    print(f"  Restored gain to: {camera.gain}")

                if camera.offset_max and camera.offset_max > camera.offset_min:
                    test_offset = min(camera.offset_max, camera.offset + 5)
                    camera.offset = test_offset
                    print(f"  Set offset to: {camera.offset}")

                    # Restore original
                    camera.offset = original_offset
                    print(f"  Restored offset to: {camera.offset}")
        except Exception as e:
            print(f"  Gain/offset change test failed: {e}")

        return True

    except Exception as e:
        print(f"❌ Gain/offset properties test failed: {e}")
        return False


def test_readout_properties(camera):
    """Test readout mode properties."""
    print("\n=== READOUT PROPERTIES TEST ===")

    try:
        print("Readout modes:")

        # Test readout mode properties
        try:
            current_mode = camera.readout_mode
            print(f"  Current mode: {current_mode}")
        except Exception as e:
            print(f"  Current mode: Not implemented ({e})")

        try:
            readout_modes = camera.readout_modes
            print(f"  Available modes: {readout_modes}")
        except Exception as e:
            print(f"  Available modes: Not implemented ({e})")

        try:
            can_fast = camera.can_fast_readout
            print(f"  Can fast readout: {can_fast}")
        except Exception as e:
            print(f"  Can fast readout: Not implemented ({e})")

        try:
            fast_readout = camera.fast_readout
            print(f"  Fast readout: {fast_readout}")
        except Exception as e:
            print(f"  Fast readout: Not implemented ({e})")

        # Test setting readout mode if supported
        try:
            if camera.readout_modes and len(camera.readout_modes) > 1:
                print("\nTesting readout mode change...")
                original_mode = camera.readout_mode

                # Try next mode
                next_mode = (original_mode + 1) % len(camera.readout_modes)
                camera.readout_mode = next_mode
                print(f"  Set readout mode to: {camera.readout_mode}")

                # Restore original
                camera.readout_mode = original_mode
                print(f"  Restored readout mode to: {camera.readout_mode}")
            else:
                print("  Skipping readout mode change test (not enough modes available)")
        except Exception as e:
            print(f"  Readout mode change test failed: {e}")

        return True

    except Exception as e:
        print(f"❌ Readout properties test failed: {e}")
        return False


def test_cooling_methods(camera):
    """Test cooling methods."""
    print("\n=== COOLING METHODS TEST ===")

    try:
        if not camera.can_set_ccd_temperature:
            print("  Cooling not supported by this camera")
            return True

        print("Testing cooling methods...")

        # Get current status
        status = camera.get_cooling_status()
        if status.is_success:
            info = status.data
            print(f"  Current temperature: {info['temperature']}°C")
            print(f"  Target temperature: {info['target_temperature']}°C")
            print(f"  Cooler on: {info['cooler_on']}")
            print(f"  Cooler power: {info['cooler_power']}%")

        # Test force refresh
        print("\nTesting force refresh...")
        refresh_status = camera.force_refresh_cooling_status()
        if refresh_status.is_success:
            info = refresh_status.data
            print(f"  Refreshed temperature: {info['temperature']}°C")
            print(f"  Refreshed cooler power: {info['cooler_power']}%")
            print(f"  Refresh attempts: {info['refresh_attempts']}")

        # Test setting cooling (if not already at target)
        current_temp = camera.ccd_temperature
        target_temp = camera.set_ccd_temperature

        if current_temp and target_temp and abs(current_temp - target_temp) > 5:
            print("\nTesting cooling set...")
            new_target = target_temp - 5  # 5°C cooler
            cooling_status = camera.set_cooling(new_target)
            print(f"  Cooling set result: {cooling_status.message}")

            # Wait a moment and check status
            time.sleep(2)
            status = camera.get_cooling_status()
            if status.is_success:
                info = status.data
                print(f"  New target: {info['target_temperature']}°C")
                print(f"  Current: {info['temperature']}°C")
                print(f"  Cooler on: {info['cooler_on']}")

        return True

    except Exception as e:
        print(f"❌ Cooling methods test failed: {e}")
        return False


def test_exposure_methods(camera):
    """Test exposure methods."""
    print("\n=== EXPOSURE METHODS TEST ===")

    try:
        print("Testing exposure methods...")

        # Test short exposure
        exposure_time = 0.1  # 100ms
        print(f"Starting {exposure_time}s exposure...")

        start_status = camera.start_exposure(exposure_time, True)
        if not start_status.is_success:
            print(f"  ❌ Failed to start exposure: {start_status.message}")
            return False

        print(f"  ✅ Exposure started: {start_status.message}")

        # Wait for exposure to complete
        print("  Waiting for exposure to complete...")
        while not camera.image_ready:
            time.sleep(0.1)
            if camera.percent_completed:
                print(f"    Progress: {camera.percent_completed}%")

        print("  ✅ Exposure completed")

        # Get image array
        print("  Getting image array...")
        image_status = camera.get_image_array()
        if image_status.is_success:
            image_array = image_status.data
            print(f"  ✅ Image retrieved: {type(image_array)}")
            if hasattr(image_array, "shape"):
                print(f"    Shape: {image_array.shape}")
        else:
            print(f"  ❌ Failed to get image: {image_status.message}")

        return True

    except Exception as e:
        print(f"❌ Exposure methods test failed: {e}")
        return False


def test_camera_info(camera):
    """Test comprehensive camera info."""
    print("\n=== CAMERA INFO TEST ===")

    try:
        info_status = camera.get_camera_info()
        if info_status.is_success:
            info = info_status.data
            print("Comprehensive camera information:")
            for key, value in info.items():
                print(f"  {key}: {value}")
        else:
            print(f"❌ Failed to get camera info: {info_status.message}")

        return True

    except Exception as e:
        print(f"❌ Camera info test failed: {e}")
        return False


def test_available_features(camera):
    """Test only features that are available on this camera."""
    print("\n=== AVAILABLE FEATURES TEST ===")

    available_features = []
    unavailable_features = []

    # Test core features
    try:
        name = camera.name
        if name:
            available_features.append(f"Name: {name}")
        else:
            unavailable_features.append("Name")
    except Exception:
        unavailable_features.append("Name")

    try:
        sensor_size = f"{camera.camera_x_size}x{camera.camera_y_size}"
        if camera.camera_x_size and camera.camera_y_size:
            available_features.append(f"Sensor: {sensor_size}")
        else:
            unavailable_features.append("Sensor size")
    except Exception:
        unavailable_features.append("Sensor size")

    # Test exposure features
    try:
        if camera.exposure_min is not None:
            available_features.append(f"Min exposure: {camera.exposure_min}s")
        else:
            unavailable_features.append("Min exposure")
    except Exception:
        unavailable_features.append("Min exposure")

    try:
        if camera.exposure_max is not None:
            available_features.append(f"Max exposure: {camera.exposure_max}s")
        else:
            unavailable_features.append("Max exposure")
    except Exception:
        unavailable_features.append("Max exposure")

    # Test cooling features
    try:
        if camera.can_set_ccd_temperature:
            available_features.append("Cooling control")
        else:
            unavailable_features.append("Cooling control")
    except Exception:
        unavailable_features.append("Cooling control")

    try:
        if camera.can_get_cooler_power:
            available_features.append("Cooler power reading")
        else:
            unavailable_features.append("Cooler power reading")
    except Exception:
        unavailable_features.append("Cooler power reading")

    # Test gain/offset features
    try:
        if camera.gain is not None:
            available_features.append(f"Gain control: {camera.gain}")
        else:
            unavailable_features.append("Gain control")
    except Exception:
        unavailable_features.append("Gain control")

    try:
        if camera.offset is not None:
            available_features.append(f"Offset control: {camera.offset}")
        else:
            unavailable_features.append("Offset control")
    except Exception:
        unavailable_features.append("Offset control")

    # Test binning features
    try:
        if camera.max_bin_x and camera.max_bin_y:
            available_features.append(f"Binning: {camera.max_bin_x}x{camera.max_bin_y}")
        else:
            unavailable_features.append("Binning")
    except Exception:
        unavailable_features.append("Binning")

    # Test readout features
    try:
        if camera.readout_modes:
            available_features.append(f"Readout modes: {len(camera.readout_modes)} available")
        else:
            unavailable_features.append("Readout modes")
    except Exception:
        unavailable_features.append("Readout modes")

    # Print results
    print("Available features:")
    for feature in available_features:
        print(f"  ✅ {feature}")

    print("\nUnavailable features:")
    for feature in unavailable_features:
        print(f"  ❌ {feature}")

    print(
        "\nFeature summary: %d available, %d unavailable",
        len(available_features),
        len(unavailable_features),
    )

    return len(available_features) > 0


def main():
    """Main test function."""
    print("=== ALPYCA CAMERA TEST ===")
    print("This test validates the Alpyca camera integration.")
    print("Make sure an Alpaca server is running on localhost:11111")
    print()

    # Load configuration if provided
    config = None
    host = "localhost"
    port = 11111
    device_id = 0

    if len(sys.argv) > 2 and sys.argv[1] == "--config":
        config_file = sys.argv[2]
        print(f"Loading configuration from: {config_file}")
        try:
            config = ConfigManager(config_file)
            video_config = config.get_video_config()
            alpaca_config = video_config.get("alpaca", {})

            host = alpaca_config.get("host", "localhost")
            port = alpaca_config.get("port", 11111)
            device_id = alpaca_config.get("device_id", 0)

            print(f"Configuration loaded: host={host}, port={port}, device_id={device_id}")
        except Exception as e:
            print(f"⚠️  Failed to load configuration: {e}")
            print("Using default configuration")

    # Test connection first
    if not test_connection():
        print("\n❌ Connection test failed. Cannot proceed with other tests.")
        print("💡 Please ensure:")
        print("   1. Alpaca server is running on localhost:11111")
        print("   2. A camera is connected to the Alpaca server")
        print("   3. The camera is not in use by another application")
        return False

    # Create camera instance for other tests
    camera = AlpycaCameraWrapper(
        host=host, port=port, device_id=device_id, config=config, logger=setup_logging()
    )

    # Connect
    status = camera.connect()
    if not status.is_success:
        print(f"❌ Failed to connect: {status.message}")
        return False

    # Run all tests
    tests = [
        ("Available Features", test_available_features, camera),
        ("Camera Properties", test_camera_properties, camera),
        ("Exposure Properties", test_exposure_properties, camera),
        ("Binning Properties", test_binning_properties, camera),
        ("Cooling Properties", test_cooling_properties, camera),
        ("Gain/Offset Properties", test_gain_offset_properties, camera),
        ("Readout Properties", test_readout_properties, camera),
        ("Cooling Methods", test_cooling_methods, camera),
        ("Exposure Methods", test_exposure_methods, camera),
        ("Camera Info", test_camera_info, camera),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func, *args in tests:
        try:
            if test_func(*args):
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    # Disconnect
    camera.disconnect()

    # Summary
    print("\n=== TEST SUMMARY ===")
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")

    if passed == total:
        print("🎉 All tests passed! Alpyca integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
