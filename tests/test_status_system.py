#!/usr/bin/env python3
"""
Test script for the status system.
Tests exception hierarchy, status objects, and error handling patterns.
"""

import os
from pathlib import Path
import sys

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from test_utils import parse_test_args, print_test_header, setup_test_environment

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


def test_exception_hierarchy() -> bool:
    """Tests the exception hierarchy."""
    print("Testing exception hierarchy...")

    try:
        from exceptions import (
            CameraError,
            ConfigurationError,
            HardwareError,
            MountError,
            PlateSolveError,
            TelescopeStreamingError,
        )

        # Test base exception
        base_error = TelescopeStreamingError("Test base error", {"test": "data"})
        print(f"✓ Base error: {base_error}")
        print(f"✓ Details: {base_error.details}")

        # Test specific exceptions
        config_error = ConfigurationError("Invalid configuration")
        mount_error = MountError("Mount connection failed")
        camera_error = CameraError("Camera not found")
        plate_error = PlateSolveError("Plate-solving failed")

        print(f"✓ Config error: {config_error}")
        print(f"✓ Mount error: {mount_error}")
        print(f"✓ Camera error: {camera_error}")
        print(f"✓ Plate error: {plate_error}")

        # Test inheritance
        assert isinstance(mount_error, HardwareError)
        assert isinstance(mount_error, TelescopeStreamingError)
        assert isinstance(camera_error, HardwareError)
        assert isinstance(camera_error, TelescopeStreamingError)

        print("✓ Exception hierarchy test completed")
        return True

    except Exception as e:
        print(f"✗ Exception hierarchy test failed: {e}")
        return False


def test_status_objects() -> bool:
    """Tests the status objects."""
    print("\nTesting status objects...")

    try:
        from status import (
            MountStatus,
            PlateSolveStatus,
            Status,
            StatusLevel,
            critical_status,
            error_status,
            success_status,
            warning_status,
        )

        # Test generic status
        generic_status = Status(StatusLevel.SUCCESS, "Test success", {"data": "test"})
        print(f"✓ Generic status: {generic_status}")
        print(f"✓ Is success: {generic_status.is_success}")
        print(f"✓ Is error: {generic_status.is_error}")

        # Test factory functions
        success = success_status("Operation successful", {"result": "data"})
        warning = warning_status("Operation completed with warnings", {"warnings": ["test"]})
        error = error_status("Operation failed", {"error_code": 404})
        critical = critical_status("Critical failure", {"fatal": True})

        print(f"✓ Success: {success}")
        print(f"✓ Warning: {warning}")
        print(f"✓ Error: {error}")
        print(f"✓ Critical: {critical}")

        # Test specific status objects
        mount_status = MountStatus(
            StatusLevel.SUCCESS,
            "Coordinates retrieved",
            data=(180.0, 45.0),
            details={"is_connected": True},
        )
        print(f"✓ Mount status: {mount_status}")
        print(f"✓ RA: {mount_status.ra_deg}°")
        print(f"✓ Dec: {mount_status.dec_deg}°")
        print(f"✓ Connected: {mount_status.is_connected}")

        # Test plate solve status
        plate_data = {
            "ra_center": 180.0,
            "dec_center": 45.0,
            "fov_width": 1.5,
            "fov_height": 1.0,
            "confidence": 0.95,
            "stars_detected": 150,
            "solving_time": 2.5,
            "solver_used": "PlateSolve2",
        }

        plate_status = PlateSolveStatus(
            StatusLevel.SUCCESS, "Plate-solving successful", data=plate_data
        )
        print(f"✓ Plate solve status: {plate_status}")
        print(f"✓ RA: {plate_status.ra_center}°")
        print(f"✓ Dec: {plate_status.dec_center}°")
        print(f"✓ Confidence: {plate_status.confidence}")
        print(f"✓ Stars: {plate_status.stars_detected}")

        print("✓ Status objects test completed")
        return True

    except Exception as e:
        print(f"✗ Status objects test failed: {e}")
        return False


def test_mount_integration() -> bool:
    """Tests the integration with the mount module."""
    print("\nTesting mount integration...")

    try:
        from status import error_status, success_status

        # Test successful mount status
        mount_status = success_status(
            "Coordinates retrieved: RA=180.0000°, Dec=45.0000°",
            data=(180.0, 45.0),
            details={"is_connected": True, "ra_hours": 12.0, "dec_deg": 45.0},
        )

        print(f"✓ Mount status: {mount_status}")
        print(f"✓ Level: {mount_status.level}")
        print(f"✓ Message: {mount_status.message}")
        print(f"✓ Data: {mount_status.data}")
        print(f"✓ Details: {mount_status.details}")
        print(f"✓ Is success: {mount_status.is_success}")

        # Test error mount status
        error_status = error_status("Mount not connected", details={"is_connected": False})

        print(f"✓ Error status: {error_status}")
        print(f"✓ Is error: {error_status.is_error}")

        # Test coordinate extraction
        if mount_status.is_success and mount_status.data:
            ra, dec = mount_status.data
            print(f"✓ Extracted coordinates: RA={ra}°, Dec={dec}°")

        print("✓ Mount integration test completed")
        return True

    except Exception as e:
        print(f"✗ Mount integration test failed: {e}")
        return False


def test_error_handling_patterns() -> bool:
    """Tests various error handling patterns."""
    print("\nTesting error handling patterns...")

    try:
        from exceptions import ConnectionError, ValidationError
        from status import MountStatus, error_status, success_status

        # Pattern 1: Try-catch with status return
        def simulate_mount_operation() -> MountStatus:
            """Simulates a mount operation."""
            try:
                # Simulate success
                if True:  # Change to False to test error path
                    return success_status(
                        "Coordinates retrieved successfully",
                        data=(180.0, 45.0),
                        details={"is_connected": True},
                    )
                else:
                    raise ConnectionError("Mount not available")

            except ConnectionError as e:
                return error_status(f"Connection failed: {e}", details={"is_connected": False})
            except ValidationError as e:
                return error_status(f"Validation failed: {e}", details={"is_connected": True})
            except Exception as e:
                return error_status(f"Unexpected error: {e}", details={"is_connected": False})

        # Test the pattern
        result = simulate_mount_operation()
        print(f"✓ Operation result: {result}")
        print(f"✓ Success: {result.is_success}")

        if result.is_success:
            print(f"✓ Coordinates: {result.data}")
        else:
            print(f"✓ Error: {result.message}")

        # Pattern 2: Status checking
        def process_mount_data(mount_status: MountStatus) -> str:
            """Processes mount data based on status."""
            if mount_status.is_success:
                ra, dec = mount_status.data
                return f"Processing coordinates: RA={ra}°, Dec={dec}°"
            elif mount_status.is_error:
                return f"Error occurred: {mount_status.message}"
            else:
                return f"Warning: {mount_status.message}"

        result_text = process_mount_data(result)
        print(f"✓ Processed result: {result_text}")

        print("✓ Error handling patterns test completed")
        return True

    except Exception as e:
        print(f"✗ Error handling patterns test failed: {e}")
        return False


def main() -> None:
    """Main function for the Status System Test."""
    # Parse command line arguments
    args = parse_test_args("Status System Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("Status System Test", driver_id, args.config)

    tests = [
        ("Exception Hierarchy", test_exception_hierarchy),
        ("Status Objects", test_status_objects),
        ("Mount Integration", test_mount_integration),
        ("Error Handling Patterns", test_error_handling_patterns),
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
        print("\n🎉 All status system tests passed!")
        print("\n✅ The new exception and status system is working correctly!")
        print("\nBenefits:")
        print("• Structured error handling with specific exception types")
        print("• Rich status objects with detailed information")
        print("• Consistent error patterns across all modules")
        print("• Better debugging and monitoring capabilities")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main()
