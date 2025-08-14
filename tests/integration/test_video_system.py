#!/usr/bin/env python3
"""
Consolidated test script for video system.
Tests video capture, integration, and FOV calculations.
"""

from pathlib import Path
import sys
import time

import cv2
import pytest

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from test_utils import (
    get_test_config,
    parse_test_args,
    print_test_header,
    setup_logging,
    setup_test_environment,
)


def list_cameras() -> list[int]:
    """Lists all available camera devices.
    Returns:
        list[int]: List of available camera indices.
    """
    print("Scanning for available cameras...")

    available_cameras = []
    # Test first 10 camera indices
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Get camera info
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            print(f"Camera {i}: {width}x{height} @ {fps:.1f}fps")
            available_cameras.append(i)
            cap.release()
        else:
            print(f"Camera {i}: Not available")

    if not available_cameras:
        print("No cameras found!")
        return []

    print(f"\nFound {len(available_cameras)} camera(s): {available_cameras}")
    return available_cameras


@pytest.mark.integration
def test_camera_access(camera_index: int) -> bool:
    """Test if camera is accessible (not blocked by other applications).
    Args:
        camera_index: Camera index.
    Returns:
        bool: True on success, False otherwise.
    """
    print(f"Testing access to camera {camera_index}...")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Camera {camera_index} is not accessible")
        return False

    # Try to read a frame
    ret, frame = cap.read()
    if not ret:
        print(
            "Camera %d is accessible but cannot read frames "
            "(possibly in use by another application)" % camera_index
        )
        cap.release()
        return False

    print(f"Camera {camera_index} is accessible and can read frames")
    cap.release()
    return True


@pytest.mark.integration
def capture_frame(camera_index: int, output_path: str = "test_frame.jpg") -> bool:
    """Captures a single frame from the specified camera.
    Args:
        camera_index: Camera index
        output_path: Filename for the saved image
    Returns:
        bool: True on success, False otherwise.
    """
    print(f"Capturing frame from camera {camera_index}...")

    # Test access first
    if not test_camera_access(camera_index):
        return False

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Failed to open camera {camera_index}")
        return False

    # Wait a moment for camera to stabilize
    print("Waiting for camera to stabilize...")
    time.sleep(1)

    # Capture frame
    ret, frame = cap.read()
    if not ret:
        print(f"Failed to capture frame from camera {camera_index}")
        cap.release()
        return False

    # Save frame
    output_file = Path(output_path)
    success = cv2.imwrite(str(output_file), frame)

    if success:
        print(f"Frame saved to: {output_file.absolute()}")
        print(f"   Frame size: {frame.shape[1]}x{frame.shape[0]} pixels")
    else:
        print(f"Failed to save frame to {output_file}")

    cap.release()
    return bool(success)


@pytest.mark.integration
def test_config_manager(config) -> bool:
    """Tests the ConfigManager with video settings.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting configuration manager...")

    try:
        # Test new configuration sections
        telescope_config = config.get_telescope_config()
        camera_config = config.get_camera_config()
        video_config = config.get_video_config()

        print(f"Telescope config: {telescope_config}")
        print(f"Camera config: {camera_config}")
        print(f"Video config: {video_config}")

        # Test FOV calculation
        focal_length = telescope_config.get("focal_length", 1000)
        sensor_width = camera_config.get("sensor_width", 6.17)
        sensor_height = camera_config.get("sensor_height", 4.55)

        # Calculate FOV manually for verification
        import numpy as np

        fov_width_rad = 2 * np.arctan(sensor_width / (2 * focal_length))
        fov_height_rad = 2 * np.arctan(sensor_height / (2 * focal_length))
        fov_width_deg = np.degrees(fov_width_rad)
        fov_height_deg = np.degrees(fov_height_rad)

        print(f"Calculated FOV: {fov_width_deg:.3f}° x {fov_height_deg:.3f}°")

        return True

    except Exception as e:
        print(f"Error testing config manager: {e}")
        return False


@pytest.mark.integration
def test_video_capture_module() -> bool:
    """Tests the VideoCapture module.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting video capture module...")

    try:
        from video_capture import VideoCapture

        video_capture = VideoCapture(config=get_test_config(), logger=setup_logging())

        # Test camera info via adapter when available
        if (
            hasattr(video_capture, "camera")
            and video_capture.camera
            and hasattr(video_capture.camera, "get_camera_info")
        ):
            info_status = video_capture.camera.get_camera_info()
            if getattr(info_status, "is_success", False):
                print(f"Camera info: {info_status.data}")
            else:
                print("Camera info not available")
        else:
            print("Camera adapter does not expose get_camera_info()")

        # Test FOV calculation
        fov_width, fov_height = video_capture.get_field_of_view()
        sampling = video_capture.get_sampling_arcsec_per_pixel()

        print(f"FOV: {fov_width:.3f}° x {fov_height:.3f}°")
        print(f"Sampling: {sampling:.2f} arcsec/pixel")

        # Test connection (without actually connecting)
        print("Video capture module loaded successfully")
        return True

    except Exception as e:
        print(f"Error testing video capture: {e}")
        return False


@pytest.mark.integration
def test_video_processor():
    """Test video processor module."""
    print("\nTesting video processor module...")

    try:
        from processing.processor import VideoProcessor

        processor = VideoProcessor()

        # Test initialization
        print(f"Video enabled: {processor.video_enabled}")
        print(f"Capture interval: {processor.capture_interval}")
        print(f"Auto solve: {processor.auto_solve}")
        print(f"Solver type: {processor.solver_type}")

        # Test statistics
        stats = processor.get_statistics()
        print(f"Statistics: {stats}")

        print("Video processor module loaded successfully")
        return True

    except Exception as e:
        print(f"Error testing video processor: {e}")
        return False


@pytest.mark.integration
def test_overlay_runner_integration():
    """Test overlay runner integration."""
    print("\nTesting overlay runner integration...")

    try:
        from overlay.runner import OverlayRunner

        runner = OverlayRunner()

        # Check if video capture is enabled
        print(f"Video enabled: {runner.video_enabled}")

        print("Overlay runner integration test passed")
        return True

    except Exception as e:
        print(f"Error testing overlay runner integration: {e}")
        return False


@pytest.mark.integration
def test_actual_camera_connection() -> bool:
    """Tests the actual camera connection (optional).
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting actual camera connection...")

    try:
        # List available cameras
        cameras = list_cameras()
        if not cameras:
            print("No cameras available for testing")
            return False

        # Test first available camera
        camera_index = cameras[0]
        print(f"Testing camera {camera_index}")

        # Test access
        if not test_camera_access(camera_index):
            print("Camera access test failed")
            return False

        # Capture test frame
        test_frame_path = f"test_camera_{camera_index}.jpg"
        if capture_frame(camera_index, test_frame_path):
            print(f"Camera test successful - frame saved as {test_frame_path}")
            return True
        else:
            print("Camera capture test failed")
            return False

    except Exception as e:
        print(f"Error testing camera connection: {e}")
        return False


def main() -> None:
    """Main function for the Video System Test."""
    # Parse command line arguments
    args = parse_test_args("Video System Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("Video System Test", driver_id, args.config)

    # Run comprehensive tests
    tests = [
        ("Configuration Manager", lambda: test_config_manager(config)),
        ("Video Capture Module", test_video_capture_module),
        ("Video Processor", test_video_processor),
        ("Overlay Runner Integration", test_overlay_runner_integration),
    ]

    # Add camera hardware test if not skipped
    if not args.skip_camera:
        tests.append(("Camera Hardware", test_actual_camera_connection))

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
        print("\n🎉 All video system tests passed!")
        print("\n✅ Video system is working correctly!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main()
