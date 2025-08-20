#!/usr/bin/env python3
"""
Direct Alpyca property test without wrapper.

This script tests Alpyca properties directly to find which one causes
the "Property Unknown is not implemented" error.
"""

import sys


def test_direct_alpyca():
    """Test Alpyca properties directly."""
    print("=== DIRECT ALPYCA PROPERTY TEST ===")

    try:
        from alpaca.camera import Camera

        print("Connecting to Alpyca camera...")
        camera = Camera("localhost:11111", 0)
        print(f"✅ Connected to: {camera.Name}")

        # Test properties one by one
        properties_to_test = [
            # Core properties
            "Name",
            "Description",
            "DriverInfo",
            "DriverVersion",
            "InterfaceVersion",
            "Connected",
            # Sensor properties
            "SensorName",
            "SensorType",
            "CameraXSize",
            "CameraYSize",
            "PixelSizeX",
            "PixelSizeY",
            "MaxADU",
            "ElectronsPerADU",
            "FullWellCapacity",
            # Exposure properties
            "ExposureMin",
            "ExposureMax",
            "ExposureResolution",
            "LastExposureDuration",
            "LastExposureStartTime",
            "ImageReady",
            "CameraState",
            "PercentCompleted",
            # Binning properties
            "BinX",
            "BinY",
            "MaxBinX",
            "MaxBinY",
            "CanAsymmetricBin",
            # Cooling properties
            "CanSetCCDTemperature",
            "CanGetCoolerPower",
            "CCDTemperature",
            "SetCCDTemperature",
            "CoolerOn",
            "CoolerPower",
            "HeatSinkTemperature",
            # Gain/Offset properties
            "Gain",
            "GainMin",
            "GainMax",
            "Gains",
            "Offset",
            "OffsetMin",
            "OffsetMax",
            "Offsets",
            # Readout properties
            "ReadoutMode",
            "ReadoutModes",
            "CanFastReadout",
            "FastReadout",
        ]

        failed_properties = []
        successful_properties = []

        for prop_name in properties_to_test:
            print(f"\n--- Testing: {prop_name} ---")
            try:
                value = getattr(camera, prop_name)
                print(f"  ✅ Success: {value}")
                successful_properties.append(prop_name)
            except Exception as e:
                error_msg = str(e)
                print(f"  ❌ Failed: {error_msg}")
                failed_properties.append((prop_name, error_msg))

                # Check if it's the specific error we're looking for
                if "Property Unknown is not implemented" in error_msg:
                    print(f"  🔍 FOUND THE PROBLEM PROPERTY: {prop_name}")
                    print(f"  🔍 Error Code: {error_msg}")

        # Summary
        print("\n=== SUMMARY ===")
        print(f"Successful properties: {len(successful_properties)}")
        print(f"Failed properties: {len(failed_properties)}")

        if failed_properties:
            print("\n❌ FAILED PROPERTIES:")
            for prop_name, error in failed_properties:
                print(f"  {prop_name}: {error}")

            # Find specific "Property Unknown" errors
            unknown_errors = [
                p for p, e in failed_properties if "Property Unknown is not implemented" in e
            ]
            if unknown_errors:
                print("\n🎯 'Property Unknown' ERRORS:")
                for prop_name, error in unknown_errors:
                    print(f"  🔍 {prop_name}: {error}")

        if successful_properties:
            print("\n✅ SUCCESSFUL PROPERTIES:")
            for prop_name in successful_properties:
                print(f"  {prop_name}")

        return len(failed_properties) == 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_specific_properties():
    """Test specific properties that might be problematic."""
    print("\n=== SPECIFIC PROPERTY TEST ===")

    try:
        from alpaca.camera import Camera

        camera = Camera("localhost:11111", 0)

        # Test specific properties that often cause issues
        problematic_properties = [
            "LastExposureDuration",
            "LastExposureStartTime",
            "PercentCompleted",
            "CameraState",
            "ImageReady",
            "HeatSinkTemperature",
            "ElectronsPerADU",
            "FullWellCapacity",
        ]

        for prop_name in problematic_properties:
            print(f"\n--- Testing: {prop_name} ---")
            try:
                value = getattr(camera, prop_name)
                print(f"  ✅ {prop_name}: {value}")
            except Exception as e:
                error_msg = str(e)
                print(f"  ❌ {prop_name}: {error_msg}")
                if "Property Unknown is not implemented" in error_msg:
                    print(f"  🔍 CONFIRMED PROBLEM PROPERTY: {prop_name}")

        return True

    except Exception as e:
        print(f"❌ Specific test failed: {e}")
        return False


def main():
    """Main test function."""
    print("Direct Alpyca property debugging")
    print("This will test each property individually to find the problematic one.")
    print()

    # Test all properties
    all_success = test_direct_alpyca()

    # Test specific problematic properties
    specific_success = test_specific_properties()

    # Summary
    print("\n=== FINAL SUMMARY ===")
    print(f"All properties test: {'✅ PASS' if all_success else '❌ FAIL'}")
    print(f"Specific properties test: {'✅ PASS' if specific_success else '❌ FAIL'}")

    if not all_success:
        print("\n💡 The problematic properties have been identified above.")
        print("   These properties should be handled with try-catch in the wrapper.")

    return all_success and specific_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
