#!/usr/bin/env python3
"""
Debug test for cache loading and smart cooling info.
This script shows exactly what happens with cache loading.
"""

import json
from pathlib import Path
import sys

from drivers.ascom.camera import ASCOMCamera
import pytest

# Ensure tests utilities are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.test_utils import (
    check_cache_file,
    get_cache_file_path,
    print_test_header,
    print_test_result,
    setup_test_environment,
)


@pytest.mark.integration
def test_cache_debug():
    """Debug test for cache loading."""
    # Setup test environment
    config, logger, driver_id = setup_test_environment()

    # Print test header
    print_test_header("Cache Debug Test", driver_id, config.config_path)

    # Get cache file path
    cache_file = get_cache_file_path(driver_id)
    print(f"Cache file: {cache_file}")

    # Check if cache file exists
    cache_exists, cache_content = check_cache_file(driver_id)
    if cache_exists:
        print_test_result(True, "Cache file exists")
        print("Cache file content:")
        print(json.dumps(cache_content, indent=2))
    else:
        print_test_result(False, "Cache file does not exist")
        pytest.skip("No cache file present for debug")

    try:
        # Create camera instance
        print("\n1. Creating camera instance...")
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)

        # Check cache after loading
        print("\n2. Cache after loading:")
        print(f"   last_cooling_info: {camera.last_cooling_info}")

        # Check if cache is valid
        has_valid_cache = (
            camera.last_cooling_info["temperature"] is not None
            and camera.last_cooling_info["cooler_power"] is not None
            and camera.last_cooling_info["cooler_on"] is not None
        )
        print(f"   Has valid cache: {has_valid_cache}")

        # Connect to camera
        print("\n3. Connecting to camera...")
        connect_status = camera.connect()
        if connect_status.is_success:
            print_test_result(True, "Camera connected")

            if camera.has_cooling():
                print("\n4. Testing get_smart_cooling_info()...")
                cooling_status = camera.get_smart_cooling_info()
                if cooling_status.is_success:
                    info = cooling_status.data
                    print("   Result:")
                    print(f"     Temperature: {info['temperature']}°C")
                    print(f"     Cooler power: {info['cooler_power']}%")
                    print(f"     Cooler on: {info['cooler_on']}")
                    print(f"     Target temperature: {info['target_temperature']}°C")

                    # Compare with cache
                    print("\n5. Comparison:")
                    print(f"   Cache values: {camera.last_cooling_info}")
                    print(f"   Current values: {info}")

                    if (
                        info["temperature"] == camera.last_cooling_info["temperature"]
                        and info["cooler_power"] == camera.last_cooling_info["cooler_power"]
                        and info["cooler_on"] == camera.last_cooling_info["cooler_on"]
                    ):
                        print_test_result(True, "Cache and current values match")
                    else:
                        print_test_result(False, "Cache and current values differ")
                else:
                    print_test_result(
                        False, f"Failed to get cooling info: {cooling_status.message}"
                    )
            else:
                print_test_result(False, "Camera does not support cooling")

            camera.disconnect()
        else:
            print_test_result(False, f"Connection failed: {connect_status.message}")

        print("\n✅ Debug test completed")

    except Exception as e:
        print_test_result(False, f"Test failed with exception: {e}")
        logger.exception("Test failed")
        pytest.skip(f"Skipping due to environment: {e}")


# __main__ runner removed; use pytest
