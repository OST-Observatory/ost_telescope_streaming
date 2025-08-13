#!/usr/bin/env python3
"""
Test script for filter wheel functionality.
Tests both integrated and separate filter wheel drivers.
"""

from drivers.ascom.camera import ASCOMCamera
from test_utils import print_test_header, print_test_result, setup_test_environment


def test_filter_wheel_functionality():
    """Test filter wheel functionality."""
    # Setup test environment
    config, logger, driver_id = setup_test_environment()

    # Print test header
    print_test_header("Filter Wheel Test", driver_id, config.config_path)

    try:
        # Create camera instance
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)

        # Connect to camera
        print("\n1. Connecting to camera...")
        connect_status = camera.connect()
        if not connect_status.is_success:
            print_test_result(False, f"Connection failed: {connect_status.message}")
            return

        print_test_result(True, "Camera connected successfully")

        # Check filter wheel availability
        print("\n2. Checking filter wheel availability...")
        has_filter_wheel = camera.has_filter_wheel()
        print_test_result(has_filter_wheel, f"Filter wheel available: {has_filter_wheel}")

        if has_filter_wheel:
            # Show filter wheel driver info
            if hasattr(camera, "filter_wheel_driver_id") and camera.filter_wheel_driver_id:
                print(f"   Separate filter wheel driver: {camera.filter_wheel_driver_id}")
            else:
                print("   Integrated filter wheel")

            # Get filter names
            print("\n3. Getting filter names...")
            filter_names_status = camera.get_filter_names()
            if filter_names_status.is_success:
                filter_names = filter_names_status.data
                print_test_result(True, f"Filter names retrieved: {filter_names}")
                print(f"   Number of filters: {len(filter_names)}")
            else:
                print_test_result(
                    False, f"Failed to get filter names: {filter_names_status.message}"
                )

            # Get current filter position
            print("\n4. Getting current filter position...")
            filter_pos_status = camera.get_filter_position()
            if filter_pos_status.is_success:
                current_pos = filter_pos_status.data
                print_test_result(True, f"Current filter position: {current_pos}")

                # Show filter name if available
                if filter_names_status.is_success and 0 <= current_pos < len(filter_names):
                    print(f"   Current filter: {filter_names[current_pos]}")
            else:
                print_test_result(
                    False, f"Failed to get filter position: {filter_pos_status.message}"
                )

            # Test filter position change (if multiple filters available)
            if filter_names_status.is_success and len(filter_names) > 1:
                print("\n5. Testing filter position change...")

                # Handle QHY filter wheel with position -1
                current_pos = filter_pos_status.data if filter_pos_status.is_success else 0
                if current_pos == -1:
                    print("   QHY filter wheel position is -1, trying to set to position 0...")
                    current_pos = 0

                # Find a different position
                new_pos = 1 if current_pos == 0 else 0

                print(f"   Changing to position {new_pos}...")
                set_pos_status = camera.set_filter_position(new_pos)
                if set_pos_status.is_success:
                    print_test_result(True, f"Filter position changed to {new_pos}")

                    # Wait a bit for QHY filter wheel to settle
                    import time

                    time.sleep(1.0)

                    # Verify the change
                    verify_pos_status = camera.get_filter_position()
                    if verify_pos_status.is_success:
                        actual_pos = verify_pos_status.data
                        # QHY filter wheels might still report -1 (this is normal for QHY)
                        if actual_pos == new_pos:
                            print_test_result(True, f"Position change verified: {actual_pos}")
                        elif actual_pos == -1 and hasattr(camera, "_is_qhy_filter_wheel"):
                            print_test_result(
                                True, "Position change accepted (QHY reports -1, which is normal)"
                            )
                            print("   Note: Some QHY wheels report -1 even when position is set")
                        else:
                            print_test_result(
                                False,
                                f"Position change failed: expected {new_pos}, got {actual_pos}",
                            )
                    else:
                        print_test_result(
                            False, f"Failed to verify position: {verify_pos_status.message}"
                        )
                else:
                    print_test_result(
                        False, f"Failed to change filter position: {set_pos_status.message}"
                    )

                # Change back to original position (if it was valid)
                if filter_pos_status.is_success and filter_pos_status.data != -1:
                    original_pos = filter_pos_status.data
                    print(f"   Changing back to position {original_pos}...")
                    restore_status = camera.set_filter_position(original_pos)
                    if restore_status.is_success:
                        print_test_result(True, f"Filter position restored to {original_pos}")
                    else:
                        print_test_result(
                            False, f"Failed to restore position: {restore_status.message}"
                        )
                else:
                    print("   Skipping restore (original position was -1)")
            else:
                print("\n5. Skipping filter position change test (only one filter available)")

        # Disconnect
        camera.disconnect()
        print_test_result(True, "Camera disconnected")

        print("\n✅ Filter wheel test completed")

    except Exception as e:
        print_test_result(False, f"Test failed with exception: {e}")
        logger.exception("Test failed")


if __name__ == "__main__":
    test_filter_wheel_functionality()
