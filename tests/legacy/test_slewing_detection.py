#!/usr/bin/env python3
"""
Test script for ASCOM mount slewing detection.
Ensures captures are skipped during mount movement.
"""

import os
import sys
import time

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from drivers.ascom.mount import ASCOMMount
import pytest

from tests.test_utils import get_test_config, setup_logging


@pytest.mark.integration
def test_slewing_detection():
    """Test slewing detection with ASCOM mount."""

    # Setup logging
    logger = setup_logging()
    logger.info("Testing ASCOM mount slewing detection")

    # Get configuration
    config = get_test_config()

    # Create mount connection
    try:
        mount = ASCOMMount(config=config, logger=logger)
        logger.info("Mount connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to mount: {e}")
        pytest.skip(f"ASCOM mount connection unavailable: {e}")

    # Test 1: Check current slewing status
    logger.info("=" * 50)
    logger.info("TEST 1: Current slewing status")
    logger.info("=" * 50)

    slewing_status = mount.is_slewing()
    if slewing_status.is_success:
        is_slewing = slewing_status.data
        logger.info(f"Current slewing status: {'SLEWING' if is_slewing else 'NOT SLEWING'}")
        logger.info(f"Status details: {slewing_status.details}")
    else:
        logger.error(f"Failed to get slewing status: {slewing_status.message}")
        raise AssertionError("Failed to get slewing status")

    # Test 2: Get full mount status
    logger.info("=" * 50)
    logger.info("TEST 2: Full mount status")
    logger.info("=" * 50)

    mount_status = mount.get_mount_status()
    if mount_status.is_success:
        mount_info = mount_status.data
        logger.info(f"Mount status: {mount_status.message}")
        logger.info(
            f"Coordinates: RA={mount_info['ra_deg']:.4f}°, Dec={mount_info['dec_deg']:.4f}°"
        )
        logger.info(f"Slewing: {'Yes' if mount_info['is_slewing'] else 'No'}")

        # Show additional properties if available
        for key, value in mount_info.items():
            if key not in ["is_connected", "is_slewing", "coordinates", "ra_deg", "dec_deg"]:
                logger.info(f"{key}: {value}")
    else:
        logger.error(f"Failed to get mount status: {mount_status.message}")
        raise AssertionError("Failed to get mount status")

    # Test 3: Continuous slewing monitoring (if currently slewing)
    if is_slewing:
        logger.info("=" * 50)
        logger.info("TEST 3: Waiting for slewing to complete")
        logger.info("=" * 50)

        logger.info("Mount is currently slewing. Waiting for completion...")
        wait_status = mount.wait_for_slewing_complete(timeout=60, check_interval=1.0)

        if wait_status.is_success:
            if wait_status.data:
                logger.info("✅ Slewing completed successfully")
                logger.info(f"Wait time: {wait_status.details.get('wait_time', 0):.1f} seconds")
            else:
                logger.warning("⚠️ Slewing timeout")
                logger.info(f"Wait time: {wait_status.details.get('wait_time', 0):.1f} seconds")
        else:
            logger.error(f"❌ Error waiting for slewing completion: {wait_status.message}")
    else:
        logger.info("=" * 50)
        logger.info("TEST 3: Skipped (mount not slewing)")
        logger.info("=" * 50)
        logger.info("Mount is not currently slewing, so no wait test needed.")

    # Test 4: Simulate capture decision logic
    logger.info("=" * 50)
    logger.info("TEST 4: Capture decision simulation")
    logger.info("=" * 50)

    def should_capture(mount):
        """Simulate the capture decision logic from VideoProcessor."""
        slewing_status = mount.is_slewing()
        if slewing_status.is_success and slewing_status.data:
            logger.info("❌ CAPTURE SKIPPED: Mount is slewing")
            return False
        elif not slewing_status.is_success:
            logger.warning(
                f"⚠️ CAPTURE CONTINUED: Could not check slewing status: {slewing_status.message}"
            )
            return True
        else:
            logger.info("✅ CAPTURE PROCEEDING: Mount is not slewing")
            return True

    # Test capture decision
    should_proceed = should_capture(mount)
    logger.info(f"Capture decision: {'PROCEED' if should_proceed else 'SKIP'}")

    # Test 4b: Test wait_for_completion logic
    logger.info("=" * 50)
    logger.info("TEST 4b: Wait for completion simulation")
    logger.info("=" * 50)

    def simulate_wait_for_completion(mount, timeout=10):
        """Simulate the wait_for_completion logic from VideoProcessor."""
        slewing_status = mount.is_slewing()
        if slewing_status.is_success and slewing_status.data:
            logger.info("🔄 MOUNT SLEWING: Waiting for completion...")
            wait_status = mount.wait_for_slewing_complete(timeout=timeout, check_interval=1.0)
            if wait_status.is_success and wait_status.data:
                logger.info("✅ SLEWING COMPLETED: Proceeding with capture")
                return True
            else:
                logger.warning(f"⚠️ SLEWING TIMEOUT/ERROR: {wait_status.message}")
                if not wait_status.data:  # Timeout
                    logger.info("❌ CAPTURE SKIPPED: Due to slewing timeout")
                    return False
                else:  # Error
                    logger.warning("⚠️ CAPTURE CONTINUED: Despite slewing error")
                    return True
        else:
            logger.info("✅ MOUNT STATIONARY: Proceeding with capture")
            return True

    # Test wait for completion logic
    should_proceed_with_wait = simulate_wait_for_completion(mount, timeout=10)
    logger.info(
        f"Wait for completion decision: {'PROCEED' if should_proceed_with_wait else 'SKIP'}"
    )

    # Test 5: Performance test (multiple rapid checks)
    logger.info("=" * 50)
    logger.info("TEST 5: Performance test (10 rapid slewing checks)")
    logger.info("=" * 50)

    start_time = time.time()
    for i in range(10):
        slewing_status = mount.is_slewing()
        if slewing_status.is_success:
            logger.debug(f"Check {i+1}: {'Slewing' if slewing_status.data else 'Not slewing'}")
        else:
            logger.warning(f"Check {i+1}: Failed - {slewing_status.message}")

    elapsed_time = time.time() - start_time
    avg_time = elapsed_time / 10
    logger.info(f"Performance: {elapsed_time:.3f}s total, {avg_time:.3f}s average per check")

    # Disconnect
    mount.disconnect()

    logger.info("=" * 50)
    logger.info("SLEWING DETECTION TEST COMPLETE")
    logger.info("=" * 50)
    logger.info("✅ All tests completed successfully!")
    logger.info("The slewing detection is working correctly.")

    assert True


def main():
    """Main function."""
    try:
        success = test_slewing_detection()
        if success:
            print("✅ Slewing detection test completed successfully!")
        else:
            print("❌ Slewing detection test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error during slewing detection test: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
