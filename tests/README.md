# Test Suite Documentation

This directory contains comprehensive tests for the telescope streaming system.

## Test Scripts Overview

### Tests with `--config` Support ✅

All tests now support the `--config` option for flexible configuration:

```bash
# Use default config
python tests/test_filter_wheel.py

# Use custom config
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Use test config
python tests/test_cooling_cache.py --config test_config_example.yaml

# With debug output
python tests/test_cache_debug.py --config test_config_example.yaml --debug
```

**Available Tests with `--config` Support:**
- ✅ `test_filter_wheel.py` - Filter wheel functionality
- ✅ `test_cooling_cache.py` - ASCOM camera cooling cache
- ✅ `test_cache_debug.py` - Debug cooling cache issues
- ✅ `test_persistent_cache.py` - Persistent cache functionality
- ✅ `test_status_system.py` - Status and exception system
- ✅ `test_automated_platesolve2.py` - Automated plate solving
- ✅ `test_basic_functionality.py` - Basic system functionality
- ✅ `test_integration.py` - System integration tests
- ✅ `test_ascom_camera.py` - ASCOM camera features
- ✅ `test_final_integration.py` - Complete system integration

### Tests with Custom Arguments

Some tests have additional command-line options:

```bash
# Video system test with camera options
python tests/test_video_system.py --list
python tests/test_video_system.py --camera 1 --output test.jpg
python tests/test_video_system.py --test-camera --skip-camera

# Object analysis
python tests/analyze_objects.py --help
```

## Command Line Options

### Standard Options (Available in all tests with `--config` support)

```bash
--config, -c PATH    # Custom configuration file path
--driver DRIVER_ID   # Override ASCOM driver from config
--verbose, -v        # Enable verbose output (DEBUG level)
--debug, -d          # Enable debug logging (same as --verbose)
--quiet, -q          # Enable quiet logging (WARNING level only)
```

### Examples

```bash
# Test with QHY camera config (INFO level - default)
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Test with debug output (all details)
python tests/test_cooling_cache.py --config test_config_example.yaml --debug

# Test with verbose output (same as debug)
python tests/test_cooling_cache.py --config test_config_example.yaml --verbose

# Override driver
python tests/test_ascom_camera.py --config test_config_example.yaml --driver ASCOM.QHYCCD.Camera

# Test with quiet output (only warnings/errors)
python tests/test_integration.py --config test_config_example.yaml --quiet
```

## Test Configuration Files

### Example Configurations

- `test_config_example.yaml` - Basic test configuration
- `config_qhy_with_filterwheel.yaml` - QHY camera with filter wheel
- `../config_ost_qhy600m.yaml` - Your QHY camera configuration

### Configuration Structure

```yaml
# Test configuration example
video:
  ascom:
    ascom_driver: "ASCOM.QHYCCD.Camera"
    filter_wheel_driver: "ASCOM.QHYCFW.FilterWheel"  # Optional

logging:
  level: "DEBUG"  # For debug output
```

## Test Categories

### 1. Hardware Tests
- **Filter Wheel Tests** - Test filter wheel functionality
- **Cooling Cache Tests** - Test ASCOM camera cooling
- **ASCOM Camera Tests** - Test camera features

### 2. System Tests
- **Integration Tests** - Test system integration
- **Basic Functionality** - Test core features
- **Status System** - Test error handling

### 3. Advanced Tests
- **Plate Solving** - Test automated plate solving
- **Video System** - Test video capture and processing
- **Final Integration** - Complete system test

## Running Tests

### Individual Tests

```bash
# Test specific functionality
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Test with debug output
python tests/test_cooling_cache.py --config test_config_example.yaml --debug

# Test system integration
python tests/test_integration.py --config test_config_example.yaml
```

### Test Suites

```bash
# Run all hardware tests
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml
python tests/test_cooling_cache.py --config ../config_ost_qhy600m.yaml
python tests/test_ascom_camera.py --config ../config_ost_qhy600m.yaml

# Run all system tests
python tests/test_basic_functionality.py --config test_config_example.yaml
python tests/test_integration.py --config test_config_example.yaml
python tests/test_status_system.py --config test_config_example.yaml

# Run advanced tests
python tests/test_automated_platesolve2.py --config test_config_example.yaml
python tests/test_final_integration.py --config test_config_example.yaml
```

## Test Utilities

### `test_utils.py`

Centralized utilities for all tests:

- `setup_logging()` - Configure logging
- `get_test_config()` - Load configuration
- `parse_test_args()` - Parse command line arguments
- `setup_test_environment()` - Setup test environment
- `print_test_header()` - Print formatted test header
- `print_test_result()` - Print test results

### Logger Synchronization

All modules in the `code/` directory now have **synchronized logging**:

- ✅ **Consistent Logging Levels** - All modules use the same logging configuration
- ✅ **Proper Logger Initialization** - Modules accept logger parameter or create proper fallback
- ✅ **Root Logger Integration** - All loggers respect the root logger configuration
- ✅ **Debug Output Support** - Debug messages from all modules are visible in tests

**Fixed Modules:**
- ✅ `ascom_camera.py` - Improved logger initialization
- ✅ `video_capture.py` - Fixed duplicate logger setup
- ✅ `video_processor.py` - Already properly configured
- ✅ `platesolve2_automated.py` - Already properly configured
- ✅ `overlay_runner.py` - Already properly configured
- ✅ `generate_overlay.py` - Already properly configured
- ✅ `plate_solver.py` - Already properly configured
- ✅ `ascom_mount.py` - Already properly configured
- ✅ `config_manager.py` - No logger usage

**Example Output with Debug:**
```bash
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml --debug
```

Shows debug messages from:
- `test_utils` - Test setup and configuration
- `ascom_camera` - Camera operations and cache management
- `config_manager` - Configuration loading
- All other modules as needed

### Usage in Tests

```python
from test_utils import (
    setup_logging,
    get_test_config,
    parse_test_args,
    setup_test_environment,
    print_test_header,
    print_test_result
)

def main():
    # Parse arguments
    args = parse_test_args("Test Description")

    # Setup environment
    config, logger, driver_id = setup_test_environment(args)

    # Print header
    print_test_header("Test Name", driver_id, args.config)

    # Run tests
    # ...
```

## Troubleshooting

### Common Issues

1. **Configuration not found**
   ```bash
   # Use absolute path or relative path from tests directory
   python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml
   ```

2. **ASCOM driver not found**
   ```bash
   # Check driver ID in config
   python tests/test_filter_wheel.py --config test_config_example.yaml --debug
   ```

3. **Permission issues**
   ```bash
   # Run with appropriate permissions
   python tests/test_video_system.py --test-camera
   ```

### Logging Levels

Different logging levels for different needs:

```bash
# Default: INFO level (important information)
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Debug level (all details)
python tests/test_cache_debug.py --config test_config_example.yaml --debug

# Verbose level (same as debug)
python tests/test_cache_debug.py --config test_config_example.yaml --verbose

# Quiet level (only warnings/errors)
python tests/test_integration.py --config test_config_example.yaml --quiet
```

## Best Practices

### 1. Use Configuration Files
Always use `--config` to specify test configurations:

```bash
# Good
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Avoid
python tests/test_filter_wheel.py  # Uses default config
```

### 2. Test with Real Hardware
When possible, test with actual hardware:

```bash
# Test with your QHY camera
python tests/test_filter_wheel.py --config ../config_ost_qhy600m.yaml --debug
```

### 3. Use Debug Mode for Troubleshooting
Enable debug output when investigating issues:

```bash
python tests/test_cooling_cache.py --config test_config_example.yaml --debug
```

### 4. Check Test Results
Always verify test results and fix any failures:

```bash
# Run test and check output
python tests/test_integration.py --config test_config_example.yaml
```

## Writing New Tests

### Template

```python
#!/usr/bin/env python3
"""
Test script for [Feature Name].
Tests [specific functionality].
"""

import sys
import os
import argparse
from pathlib import Path

# Add the code directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from test_utils import (
    setup_logging,
    get_test_config,
    parse_test_args,
    setup_test_environment,
    print_test_header,
    print_test_result
)

def test_feature() -> bool:
    """Test specific feature."""
    print("Testing feature...")

    try:
        # Test implementation
        print("✓ Feature test completed")
        return True
    except Exception as e:
        print(f"✗ Feature test failed: {e}")
        return False

def main() -> None:
    """Main test function."""
    # Parse command line arguments
    args = parse_test_args("Feature Test")

    # Setup test environment
    config, logger, driver_id = setup_test_environment(args)

    # Print test header
    print_test_header("Feature Test", driver_id, args.config)

    tests = [
        ("Feature", test_feature),
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

    print(f"\n--- Results ---")
    print(f"Completed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n❌ {total - passed} test(s) failed.")

if __name__ == "__main__":
    main()
```

### Guidelines

1. **Use test_utils** - Import and use utilities from `test_utils.py`
2. **Support --config** - Always add `--config` support
3. **Clear output** - Use formatted output with `print_test_result()`
4. **Error handling** - Proper exception handling in tests
5. **Documentation** - Clear docstrings and comments

## Summary

All tests now support the `--config` option for flexible configuration management. This allows you to:

- ✅ Test with different camera configurations
- ✅ Use custom ASCOM drivers
- ✅ Enable debug output when needed
- ✅ Run tests consistently across environments

The test suite is now fully standardized and ready for comprehensive testing of the telescope streaming system.
