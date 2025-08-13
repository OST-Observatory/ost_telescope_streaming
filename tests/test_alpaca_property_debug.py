#!/usr/bin/env python3
"""
Detailed Alpyca property debugging.

This script tests each Alpyca property individually to identify which one
causes the "Property Unknown is not implemented" error.
"""

import logging
from pathlib import Path
import sys
import traceback

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from config_manager import ConfigManager
from drivers.alpaca.camera import AlpycaCameraWrapper


def setup_logging():
    """Setup detailed logging for debugging."""
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("property_debug")


def test_property_safely(camera, property_name, getter_func, setter_func=None, test_value=None):
    """Test a single property safely with detailed error reporting."""
    print(f"\n--- Testing Property: {property_name} ---")

    try:
        # Test getter
        print("  Testing getter...")
        value = getter_func()
        print(f"  ✅ Getter successful: {value}")

        # Test setter if provided
        if setter_func and test_value is not None:
            print(f"  Testing setter with value: {test_value}")
            setter_func(test_value)
            print("  ✅ Setter successful")

            # Verify the value was set
            new_value = getter_func()
            print(f"  ✅ Verification: {new_value}")

        return True, None

    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ Property failed: {error_msg}")

        # Check if it's the specific error we're looking for
        if "Property Unknown is not implemented" in error_msg:
            print(f"  🔍 FOUND THE PROBLEM PROPERTY: {property_name}")
            print(f"  🔍 Error details: {error_msg}")
            return False, error_msg
        else:
            print(f"  ⚠️  Different error: {error_msg}")
            return False, error_msg


def test_core_properties(camera):
    """Test core camera properties."""
    print("\n=== CORE PROPERTIES TEST ===")

    properties = [
        ("Name", lambda: camera.name, None, None),
        ("Description", lambda: camera.description, None, None),
        ("DriverInfo", lambda: camera.driver_info, None, None),
        ("DriverVersion", lambda: camera.driver_version, None, None),
        ("InterfaceVersion", lambda: camera.interface_version, None, None),
        ("Connected", lambda: camera.connected, None, None),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_sensor_properties(camera):
    """Test sensor-related properties."""
    print("\n=== SENSOR PROPERTIES TEST ===")

    properties = [
        ("SensorName", lambda: camera.sensor_name, None, None),
        ("SensorType", lambda: camera.sensor_type, None, None),
        ("CameraXSize", lambda: camera.camera_x_size, None, None),
        ("CameraYSize", lambda: camera.camera_y_size, None, None),
        ("PixelSizeX", lambda: camera.pixel_size_x, None, None),
        ("PixelSizeY", lambda: camera.pixel_size_y, None, None),
        ("MaxADU", lambda: camera.max_adu, None, None),
        ("ElectronsPerADU", lambda: camera.electrons_per_adu, None, None),
        ("FullWellCapacity", lambda: camera.full_well_capacity, None, None),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_exposure_properties(camera):
    """Test exposure-related properties."""
    print("\n=== EXPOSURE PROPERTIES TEST ===")

    properties = [
        ("ExposureMin", lambda: camera.exposure_min, None, None),
        ("ExposureMax", lambda: camera.exposure_max, None, None),
        ("ExposureResolution", lambda: camera.exposure_resolution, None, None),
        ("LastExposureDuration", lambda: camera.last_exposure_duration, None, None),
        ("LastExposureStartTime", lambda: camera.last_exposure_start_time, None, None),
        ("ImageReady", lambda: camera.image_ready, None, None),
        ("CameraState", lambda: camera.camera_state, None, None),
        ("PercentCompleted", lambda: camera.percent_completed, None, None),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_binning_properties(camera):
    """Test binning properties."""
    print("\n=== BINNING PROPERTIES TEST ===")

    properties = [
        ("BinX", lambda: camera.bin_x, lambda x: setattr(camera, "bin_x", x), 1),
        ("BinY", lambda: camera.bin_y, lambda x: setattr(camera, "bin_y", x), 1),
        ("MaxBinX", lambda: camera.max_bin_x, None, None),
        ("MaxBinY", lambda: camera.max_bin_y, None, None),
        ("CanAsymmetricBin", lambda: camera.can_asymmetric_bin, None, None),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_cooling_properties(camera):
    """Test cooling properties."""
    print("\n=== COOLING PROPERTIES TEST ===")

    properties = [
        ("CanSetCCDTemperature", lambda: camera.can_set_ccd_temperature, None, None),
        ("CanGetCoolerPower", lambda: camera.can_get_cooler_power, None, None),
        ("CCDTemperature", lambda: camera.ccd_temperature, None, None),
        (
            "SetCCDTemperature",
            lambda: camera.set_ccd_temperature,
            lambda x: setattr(camera, "set_ccd_temperature", x),
            -10.0,
        ),
        ("CoolerOn", lambda: camera.cooler_on, lambda x: setattr(camera, "cooler_on", x), True),
        ("CoolerPower", lambda: camera.cooler_power, None, None),
        ("HeatSinkTemperature", lambda: camera.heat_sink_temperature, None, None),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_gain_offset_properties(camera):
    """Test gain and offset properties."""
    print("\n=== GAIN/OFFSET PROPERTIES TEST ===")

    properties = [
        ("Gain", lambda: camera.gain, lambda x: setattr(camera, "gain", x), 100.0),
        ("GainMin", lambda: camera.gain_min, None, None),
        ("GainMax", lambda: camera.gain_max, None, None),
        ("Gains", lambda: camera.gains, None, None),
        ("Offset", lambda: camera.offset, lambda x: setattr(camera, "offset", x), 50.0),
        ("OffsetMin", lambda: camera.offset_min, None, None),
        ("OffsetMax", lambda: camera.offset_max, None, None),
        ("Offsets", lambda: camera.offsets, None, None),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_readout_properties(camera):
    """Test readout mode properties."""
    print("\n=== READOUT PROPERTIES TEST ===")

    properties = [
        (
            "ReadoutMode",
            lambda: camera.readout_mode,
            lambda x: setattr(camera, "readout_mode", x),
            0,
        ),
        ("ReadoutModes", lambda: camera.readout_modes, None, None),
        ("CanFastReadout", lambda: camera.can_fast_readout, None, None),
        (
            "FastReadout",
            lambda: camera.fast_readout,
            lambda x: setattr(camera, "fast_readout", x),
            False,
        ),
    ]

    failed_properties = []

    for prop_name, getter, setter, test_value in properties:
        success, error = test_property_safely(camera, prop_name, getter, setter, test_value)
        if not success:
            failed_properties.append((prop_name, error))

    return failed_properties


def test_direct_alpyca_properties(camera):
    """Test properties directly through Alpyca without wrapper."""
    print("\n=== DIRECT ALPYCA PROPERTIES TEST ===")

    if not hasattr(camera, "camera") or not camera.camera:
        print("❌ No direct camera access available")
        return []

    direct_camera = camera.camera

    # Test some key properties directly
    properties_to_test = [
        "Name",
        "Description",
        "DriverInfo",
        "DriverVersion",
        "SensorName",
        "SensorType",
        "CameraXSize",
        "CameraYSize",
        "CanSetCCDTemperature",
        "CanGetCoolerPower",
        "CCDTemperature",
        "SetCCDTemperature",
        "CoolerOn",
        "CoolerPower",
    ]

    failed_properties = []

    for prop_name in properties_to_test:
        print(f"\n--- Testing Direct Property: {prop_name} ---")
        try:
            value = getattr(direct_camera, prop_name)
            print(f"  ✅ Direct property successful: {value}")
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Direct property failed: {error_msg}")
            if "Property Unknown is not implemented" in error_msg:
                print(f"  🔍 FOUND THE PROBLEM PROPERTY (Direct): {prop_name}")
                failed_properties.append((prop_name, error_msg))

    return failed_properties


def main():
    """Main debugging function."""
    parser = argparse.ArgumentParser(description="Debug Alpyca property issues")
    parser.add_argument("--config", type=str, required=True, help="Path to configuration file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = setup_logging()

    print("=== ALPYCA PROPERTY DEBUGGING ===")
    print(f"Configuration: {args.config}")
    print("This will test each property individually to find the problematic one.")
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

        # Test all property categories
        all_failed_properties = []

        # Test direct Alpyca properties first
        direct_failed = test_direct_alpyca_properties(camera)
        all_failed_properties.extend(direct_failed)

        # Test wrapper properties
        core_failed = test_core_properties(camera)
        all_failed_properties.extend(core_failed)

        sensor_failed = test_sensor_properties(camera)
        all_failed_properties.extend(sensor_failed)

        exposure_failed = test_exposure_properties(camera)
        all_failed_properties.extend(exposure_failed)

        binning_failed = test_binning_properties(camera)
        all_failed_properties.extend(binning_failed)

        cooling_failed = test_cooling_properties(camera)
        all_failed_properties.extend(cooling_failed)

        gain_offset_failed = test_gain_offset_properties(camera)
        all_failed_properties.extend(gain_offset_failed)

        readout_failed = test_readout_properties(camera)
        all_failed_properties.extend(readout_failed)

        # Disconnect
        camera.disconnect()
        print("\n✅ Disconnected from camera")

        # Summary
        print("\n=== DEBUGGING SUMMARY ===")
        print(f"Total failed properties: {len(all_failed_properties)}")

        if all_failed_properties:
            print("\n🔍 PROBLEMATIC PROPERTIES:")
            for prop_name, error in all_failed_properties:
                print(f"  ❌ {prop_name}: {error}")

            # Find the specific "Property Unknown" errors
            unknown_properties = [
                p for p, e in all_failed_properties if "Property Unknown is not implemented" in e
            ]
            if unknown_properties:
                print("\n🎯 SPECIFIC 'Property Unknown' ERRORS:")
                for prop_name, error in unknown_properties:
                    print(f"  🔍 {prop_name}: {error}")
        else:
            print("✅ No problematic properties found!")

        return len(all_failed_properties) == 0

    except Exception as e:
        print(f"❌ Debugging failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    success = main()
    sys.exit(0 if success else 1)
