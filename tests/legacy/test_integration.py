#!/usr/bin/env python3
"""
Consolidated test script for system integration.
Tests modular system, overlay generation, and overall integration.
"""

import os
from pathlib import Path
import sys

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

import pytest

try:
    from tests.test_utils import parse_test_args, print_test_header, setup_test_environment
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_utils import parse_test_args, print_test_header, setup_test_environment


@pytest.mark.integration
def test_plate_solver() -> bool:
    """Tests the plate solver module.
    Returns:
        bool: True on success, False otherwise.
    """
    print("Testing plate solver module...")

    try:
        try:
            from platesolve.solver import PlateSolverFactory
        except Exception:
            from plate_solver import PlateSolverFactory

        # Test factory
        print("Available solvers:")
        available = PlateSolverFactory.get_available_solvers()
        for name, is_available in available.items():
            status = "✓" if is_available else "✗"
            print(f"  {status} {name}")

        # Test solver creation
        solver = PlateSolverFactory.create_solver("platesolve2")
        if solver:
            print(f"Created solver: {solver.get_name()}")
            print(f"Available: {solver.is_available()}")

            # Test automated solver availability
            if hasattr(solver, "automated_available"):
                print(f"Automated solver available: {solver.automated_available}")
        else:
            print("Failed to create solver")

        return True

    except Exception as e:
        print(f"Error testing plate solver: {e}")
        return False


@pytest.mark.integration
def test_video_processor() -> bool:
    """Tests the VideoProcessor.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting video processor module...")

    try:
        from video_processor import VideoProcessor

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
def test_config_integration(config) -> bool:
    """Tests the configuration integration.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting configuration integration...")

    try:
        # Test new configuration sections
        plate_solve_config = config.get_plate_solve_config()
        video_config = config.get_video_config()

        print(f"Plate-solve config: {plate_solve_config}")
        print(f"Video config: {video_config}")

        # Test specific settings
        default_solver = plate_solve_config.get("default_solver", "unknown")
        auto_solve = plate_solve_config.get("auto_solve", False)
        platesolve2_path = plate_solve_config.get("platesolve2_path", "")

        print(f"Default solver: {default_solver}")
        print(f"Auto solve: {auto_solve}")
        print(f"PlateSolve 2 path: {platesolve2_path}")

        return True

    except Exception as e:
        print(f"Error testing config integration: {e}")
        return False


@pytest.mark.integration
def test_overlay_generator() -> bool:
    """Tests the OverlayGenerator class.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting overlay generator...")

    try:
        try:
            from overlay.generator import OverlayGenerator
        except Exception:
            from generate_overlay import OverlayGenerator

        # Create generator
        generator = OverlayGenerator()

        # Test configuration loading
        print(f"FOV: {generator.fov_deg}°")
        print(f"Magnitude limit: {generator.mag_limit}")
        print(f"Image size: {generator.image_size}")
        print(f"Object color: {generator.object_color}")
        print(f"Text color: {generator.text_color}")

        # Test coordinate validation
        try:
            generator.validate_coordinates(47.4166, -15.5384)
            print("✓ Coordinate validation works")
        except Exception as e:
            print(f"✗ Coordinate validation failed: {e}")
            return False

        # Test invalid coordinates
        try:
            generator.validate_coordinates(400, 100)  # Invalid RA
            print("✗ Invalid RA not caught")
            return False
        except ValueError:
            print("✓ Invalid RA properly caught")

        try:
            generator.validate_coordinates(200, 100)  # Invalid Dec
            print("✗ Invalid Dec not caught")
            return False
        except ValueError:
            print("✓ Invalid Dec properly caught")

        print("Overlay generator loaded successfully")
        return True

    except Exception as e:
        print(f"Error testing overlay generator: {e}")
        return False


@pytest.mark.integration
def test_overlay_generation() -> bool:
    """Tests overlay generation.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting overlay generation...")

    try:
        try:
            from overlay.generator import OverlayGenerator
        except Exception:
            from generate_overlay import OverlayGenerator

        # Test coordinates
        ra = 47.4166
        dec = -15.5384

        print(f"Coordinates: RA={ra}°, Dec={dec}°")
        print("Generating overlay...")

        # Create generator and generate overlay
        generator = OverlayGenerator()
        output_file = "test_integration_overlay.png"

        result_file = generator.generate_overlay(ra, dec, output_file)

        # Check if file was created
        if os.path.exists(result_file):
            print(f"✓ Overlay generated successfully: {result_file}")
            return True
        else:
            print(f"✗ Overlay file not found: {result_file}")
            return False

    except Exception as e:
        print(f"Error during overlay generation: {e}")
        return False


@pytest.mark.integration
def test_overlay_runner() -> bool:
    """Tests the OverlayRunner.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting overlay runner...")

    try:
        from overlay.runner import OverlayRunner

        runner = OverlayRunner()

        # Check if components are available
        print(f"Video enabled: {runner.video_enabled}")
        print(f"Overlay generator available: {runner.overlay_generator is not None}")

        # Test overlay generation method
        if runner.overlay_generator:
            print("✓ Overlay generator integrated")
        else:
            print("⚠ Overlay generator not available (fallback mode)")

        print("Overlay runner integration test passed")
        return True

    except Exception as e:
        print(f"Error testing overlay runner: {e}")
        return False


@pytest.mark.integration
def test_modular_architecture() -> bool:
    """Tests the modular architecture.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting modular architecture...")

    try:
        # Test all major components
        components = [
            ("Config Manager", lambda: __import__("config_manager")),
            ("Plate Solver", lambda: __import__("plate_solver")),
            ("Video Capture", lambda: __import__("video_capture")),
            ("Video Processor", lambda: __import__("video_processor")),
            ("Overlay Generator", lambda: __import__("generate_overlay")),
            ("Overlay Runner", lambda: __import__("overlay_runner")),
        ]

        for name, import_func in components:
            try:
                import_func()
                print(f"✓ {name} imported successfully")
            except Exception as e:
                print(f"✗ {name} import failed: {e}")
                return False

        print("✓ All modules imported successfully")
        return True

    except Exception as e:
        print(f"Error testing modular architecture: {e}")
        return False


@pytest.mark.integration
def test_automated_platesolve2_integration() -> bool:
    """Tests the automated PlateSolve2 integration.
    Returns:
        bool: True on success, False otherwise.
    """
    print("\nTesting automated PlateSolve 2 integration...")

    try:
        from plate_solver import PlateSolve2Solver

        # Create solver
        solver = PlateSolve2Solver()

        # Test availability
        print(f"PlateSolve 2 available: {solver.is_available()}")
        print(f"Automated solver available: {solver.automated_available}")

        if solver.automated_available:
            print("✓ Automated PlateSolve 2 integration available")
        else:
            print("⚠ Automated PlateSolve 2 not available, manual mode only")

        return True

    except Exception as e:
        print(f"Error testing automated PlateSolve 2: {e}")
        return False


def main() -> None:
    """Main function for the Integration Test."""
    # Parse command line arguments
    args = parse_test_args("System Integration Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("System Integration Test", driver_id, args.config)

    tests = [
        ("Plate Solver Module", test_plate_solver),
        ("Video Processor", test_video_processor),
        ("Configuration Integration", lambda: test_config_integration(config)),
        ("Overlay Generator", test_overlay_generator),
        ("Overlay Generation", test_overlay_generation),
        ("Overlay Runner", test_overlay_runner),
        ("Modular Architecture", test_modular_architecture),
        ("Automated PlateSolve2 Integration", test_automated_platesolve2_integration),
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
        print("\n🎉 All integration tests passed!")
        print("\n✅ The system is fully integrated and ready!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        print("Please check the failed tests and fix any issues.")


if __name__ == "__main__":
    main()
