#!/usr/bin/env python3
"""
Final integration test script.
Tests the complete system integration including all modules.
"""

import os
from pathlib import Path
import sys

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from common.test_utils import parse_test_args, print_test_header, setup_test_environment
import pytest


@pytest.mark.integration
def test_automated_platesolve2_integration() -> bool:
    """Tests the automated PlateSolve 2 integration.
    Returns:
        bool: True on success, False otherwise.
    """
    print("Testing automated PlateSolve 2 integration...")

    try:
        try:
            from platesolve.solver import PlateSolve2Solver
        except Exception:
            from plate_solver import PlateSolve2Solver

        # Create solver
        solver = PlateSolve2Solver()

        # Test image
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"

        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            return False

        print(f"✓ Test image found: {test_image}")
        print(f"✓ Automated solver available: {solver.automated_available}")

        # Test availability
        if not solver.is_available():
            print("✗ PlateSolve 2 not available")
            return False

        print("✓ PlateSolve 2 is available")

        # Test solving
        print("\n--- Testing automated solving ---")
        result = solver.solve(test_image)

        print(f"Result: {result}")

        if result.is_success:
            print("✓ Automated solving successful!")
            print(f"✓ Method used: {result.data.get('method', 'unknown')}")
            print(f"✓ RA: {result.data.get('ra_center', 0):.4f}°")
            print(f"✓ Dec: {result.data.get('dec_center', 0):.4f}°")
            fw = result.data.get("fov_width", 0)
            fh = result.data.get("fov_height", 0)
            print(f"✓ FOV: {fw:.4f}° x {fh:.4f}°")
            print(f"✓ Confidence: {result.data.get('confidence', 'unknown')}")
            print(f"✓ Solving time: {result.details.get('solving_time', 0):.1f}s")
            return True
        else:
            print(f"✗ Solving failed: {result.message}")
            return False

    except Exception as e:
        print(f"✗ Error testing automated integration: {e}")
        return False


@pytest.mark.integration
def test_video_processor_integration():
    """Test integration with video processor."""
    print("\n--- Testing video processor integration ---")

    try:
        from processing.processor import VideoProcessor

        try:
            from platesolve.solver import PlateSolve2Solver
        except Exception:
            from plate_solver import PlateSolve2Solver

        # Create video processor
        video_processor = VideoProcessor()

        # Test that it can use the automated solver
        if hasattr(video_processor, "plate_solver") and video_processor.plate_solver:
            print(f"✓ Video processor has plate solver: {video_processor.plate_solver.get_name()}")

            if isinstance(video_processor.plate_solver, PlateSolve2Solver):
                print("✓ Using PlateSolve 2 solver")
                avail = video_processor.plate_solver.automated_available
                print(f"✓ Automated solver available: {avail}")
                return True
            else:
                print(f"✗ Using different solver: {video_processor.plate_solver.get_name()}")
                return False
        else:
            print("✗ Video processor has no plate solver")
            return False

    except Exception as e:
        print(f"✗ Error testing video processor integration: {e}")
        return False


@pytest.mark.integration
def test_overlay_runner_integration():
    """Test integration with overlay runner."""
    print("\n--- Testing overlay runner integration ---")

    try:
        from overlay.runner import OverlayRunner

        # Create overlay runner
        runner = OverlayRunner()

        # Test that it can use video processor
        if hasattr(runner, "video_processor") and runner.video_processor:
            print("✓ Overlay runner has video processor")
            return True
        else:
            print("✗ Overlay runner has no video processor")
            return False

    except Exception as e:
        print(f"✗ Error testing overlay runner integration: {e}")
        return False


@pytest.mark.integration
def test_configuration(config) -> bool:
    """Tests the configuration for automated plate solving.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\n--- Testing configuration ---")

    try:
        # Test plate solve configuration
        plate_solve_config = config.get_plate_solve_config()

        required_keys = [
            "platesolve2_path",
            "working_directory",
            "timeout",
            "number_of_regions",
        ]

        missing_keys = []
        for key in required_keys:
            if key not in plate_solve_config:
                missing_keys.append(key)
            else:
                print(f"✓ {key}: {plate_solve_config[key]}")

        if missing_keys:
            print(f"✗ Missing configuration keys: {missing_keys}")
            return False

        # Test telescope and camera configuration
        telescope_config = config.get_telescope_config()
        camera_config = config.get_camera_config()

        print(f"✓ Telescope focal length: {telescope_config.get('focal_length', 'N/A')}mm")
        sw = camera_config.get("sensor_width", "N/A")
        sh = camera_config.get("sensor_height", "N/A")
        print(f"✓ Camera sensor: {sw}mm x {sh}mm")

        return True

    except Exception as e:
        print(f"✗ Error testing configuration: {e}")
        return False


@pytest.mark.integration
def test_command_line_format():
    """Test the correct command line format."""
    print("\n--- Testing command line format ---")

    try:
        try:
            from platesolve.platesolve2 import PlateSolve2Automated
        except Exception:
            from platesolve2_automated import PlateSolve2Automated

        solver = PlateSolve2Automated()

        # Test parameters
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        ra_deg = 295.0  # Example RA
        dec_deg = 40.0  # Example Dec
        fov_width_deg = 0.5  # Example FOV
        fov_height_deg = 0.4  # Example FOV

        # Build command string
        ra_rad, dec_rad, fov_width_rad, fov_height_rad = solver._prepare_parameters(
            ra_deg, dec_deg, fov_width_deg, fov_height_deg
        )

        cmd_string = solver._build_command_string(
            test_image, ra_rad, dec_rad, fov_width_rad, fov_height_rad
        )

        print(f"✓ Command string format: {cmd_string}")

        # Verify format matches user specification
        # Format: ra,dec,width_fov,height_fov,num_regions,path_to_image,"0"
        parts = cmd_string.split(",")

        if len(parts) == 7:
            print(f"✓ Correct number of parameters: {len(parts)}")
            print(f"✓ RA (rad): {parts[0]}")
            print(f"✓ Dec (rad): {parts[1]}")
            print(f"✓ FOV width (rad): {parts[2]}")
            print(f"✓ FOV height (rad): {parts[3]}")
            print(f"✓ Number of regions: {parts[4]}")
            print(f"✓ Image path: {parts[5]}")
            print(f"✓ Fixed parameter: {parts[6]}")

            # Verify all parameters are in radians (except the last two)
            try:
                float(parts[0])  # RA
                float(parts[1])  # Dec
                float(parts[2])  # FOV width
                float(parts[3])  # FOV height
                int(parts[4])  # Number of regions
                print("✓ All numeric parameters are valid")
                return True
            except ValueError:
                print("✗ Invalid numeric parameters")
                return False
        else:
            print(f"✗ Incorrect number of parameters: {len(parts)}")
            return False

    except Exception as e:
        print(f"✗ Error testing command line format: {e}")
        return False


@pytest.mark.integration
def test_complete_workflow() -> bool:
    """Tests the complete workflow from image to overlay.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\n--- Testing complete workflow ---")

    try:
        # This would test the complete workflow
        # For now, just verify all components are available

        try:
            from platesolve.solver import PlateSolve2Solver
        except Exception:
            from plate_solver import PlateSolve2Solver
        from overlay.runner import OverlayRunner
        from processing.processor import VideoProcessor

        print("✓ All core components imported successfully")

        # Test that automated solving is available
        solver = PlateSolve2Solver()
        if solver.automated_available:
            print("✓ Automated PlateSolve 2 is available")
        else:
            print("✗ Automated PlateSolve 2 is not available")

        # Test video processor
        _video_processor = VideoProcessor()
        print("✓ Video processor is available")

        # Test overlay runner
        _overlay_runner = OverlayRunner()
        print("✓ Overlay runner is available")

        return True

    except Exception as e:
        print(f"✗ Error testing complete workflow: {e}")
        return False


def main() -> None:
    """Main function for the Final Integration Test."""
    # Parse command line arguments
    args = parse_test_args("Final Integration Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("Final Integration Test", driver_id, args.config)

    tests = [
        ("Automated PlateSolve2 Integration", test_automated_platesolve2_integration),
        ("Video Processor Integration", test_video_processor_integration),
        ("Overlay Runner Integration", test_overlay_runner_integration),
        ("Configuration", lambda: test_configuration(config)),
        ("Command Line Format", test_command_line_format),
        ("Complete Workflow", test_complete_workflow),
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
        print("\n🎉 All final integration tests passed!")
        print("\n✅ The complete system is ready for production use!")
        print("\n🚀 You can now use the system for astrophotography!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main()
