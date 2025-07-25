# Test System Documentation

## Overview

The test system provides flexible configuration management and common utilities for testing the OST Telescope Streaming system.

## Test Utilities (`test_utils.py`)

### Features

- **Flexible Configuration**: Use different config files for different test scenarios
- **Command Line Arguments**: Standardized argument parsing for all tests
- **Logging Management**: Consistent logging setup across tests
- **Cache Management**: Utilities for working with persistent cache files
- **Test Reporting**: Standardized test result formatting

### Command Line Options

All tests support the following command line options:

```bash
# Basic usage
python tests/test_cache_debug.py

# With custom config file
python tests/test_cache_debug.py --config tests/test_config_example.yaml

# With specific ASCOM driver
python tests/test_cache_debug.py --driver ASCOM.QHYCCD.Camera

# With verbose logging
python tests/test_cache_debug.py --verbose

# With debug logging
python tests/test_cache_debug.py --debug

# Combine options
python tests/test_cache_debug.py --config tests/test_config_example.yaml --driver ASCOM.QHYCCD.Camera --debug
```

### Available Options

| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Path to custom config file |
| `--driver` | `-d` | ASCOM driver ID (overrides config) |
| `--verbose` | `-v` | Enable verbose logging (INFO level) |
| `--debug` | | Enable debug logging (DEBUG level) |

## Test Configuration Files

### Using Custom Config Files

Create your own test configuration file:

```yaml
# my_test_config.yaml
video:
  ascom:
    ascom_driver: "ASCOM.MyCamera.Camera"
  opencv:
    camera_index: 1
    frame_width: 1280
    frame_height: 720

logging:
  level: "DEBUG"
  verbose: true
```

Use it with tests:

```bash
python tests/test_cache_debug.py --config my_test_config.yaml
```

### Example Config File

See `tests/test_config_example.yaml` for a complete example configuration.

## Available Tests

### 1. Cache Debug Test
```bash
python tests/test_cache_debug.py [options]
```
- Debug cache loading and smart cooling info
- Shows cache file content and validation
- Compares cache vs. current values

### 2. Cooling Cache Test
```bash
python tests/test_cooling_cache.py [options]
```
- Tests all cooling info retrieval methods
- Tests cooling operation sequences
- Tests cache consistency over time
- Tests cache update mechanisms

### 3. Persistent Cache Test
```bash
python tests/test_persistent_cache.py [options]
```
- Tests cache persistence across instances
- Tests cache expiration
- Tests cache sharing between sessions

## Test Utilities API

### Core Functions

#### `setup_test_environment(args=None)`
Setup test environment with configuration and logging.

```python
from test_utils import setup_test_environment

config, logger, driver_id = setup_test_environment()
```

#### `get_test_config(config_path=None)`
Get configuration for tests.

```python
from test_utils import get_test_config

# Use default config
config = get_test_config()

# Use custom config
config = get_test_config("my_config.yaml")
```

#### `parse_test_args(description="Test script")`
Parse command line arguments for tests.

```python
from test_utils import parse_test_args

args = parse_test_args("My Test Description")
```

### Utility Functions

#### `print_test_header(test_name, driver_id=None, config_file=None)`
Print formatted test header.

```python
from test_utils import print_test_header

print_test_header("My Test", "ASCOM.QHYCCD.Camera", "config.yaml")
```

#### `print_test_result(success, message)`
Print formatted test result.

```python
from test_utils import print_test_result

print_test_result(True, "Test passed")
print_test_result(False, "Test failed")
```

#### `check_cache_file(driver_id)`
Check if cache file exists and return content.

```python
from test_utils import check_cache_file

exists, content = check_cache_file("ASCOM.QHYCCD.Camera")
if exists:
    print(f"Cache content: {content}")
```

## Writing New Tests

### Basic Test Template

```python
#!/usr/bin/env python3
"""
My Test Description
"""

from test_utils import (
    setup_test_environment,
    print_test_header,
    print_test_result
)
from ascom_camera import ASCOMCamera

def my_test_function():
    """My test function."""
    # Setup test environment
    config, logger, driver_id = setup_test_environment()
    
    # Print test header
    print_test_header("My Test", driver_id, config.config_file)
    
    try:
        # Your test code here
        camera = ASCOMCamera(driver_id=driver_id, config=config, logger=logger)
        
        # Test something
        result = camera.some_function()
        
        if result.is_success:
            print_test_result(True, "Test passed")
        else:
            print_test_result(False, f"Test failed: {result.message}")
            
    except Exception as e:
        print_test_result(False, f"Test failed with exception: {e}")
        logger.exception("Test failed")

if __name__ == "__main__":
    my_test_function()
```

### Advanced Test with Custom Arguments

```python
#!/usr/bin/env python3
"""
Advanced Test with Custom Arguments
"""

from test_utils import (
    parse_test_args,
    setup_test_environment,
    print_test_header,
    print_test_result
)

def advanced_test():
    """Advanced test with custom arguments."""
    # Parse custom arguments
    parser = parse_test_args("Advanced Test")
    parser.add_argument("--custom-option", help="Custom option")
    args = parser.parse_args()
    
    # Setup test environment with custom args
    config, logger, driver_id = setup_test_environment(args)
    
    # Use custom option
    if args.custom_option:
        print(f"Using custom option: {args.custom_option}")
    
    # Your test code here...

if __name__ == "__main__":
    advanced_test()
```

## Best Practices

### 1. Use Test Utilities
Always use the provided test utilities for consistent behavior:

```python
# ✅ Good
from test_utils import setup_test_environment, print_test_result

# ❌ Bad
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Handle Exceptions
Always wrap test code in try-except blocks:

```python
try:
    # Test code
    result = camera.connect()
    print_test_result(result.is_success, "Connection test")
except Exception as e:
    print_test_result(False, f"Exception: {e}")
```

### 3. Use Descriptive Names
Use clear, descriptive names for test functions and variables:

```python
# ✅ Good
def test_cooling_cache_persistence():
    """Test that cooling cache persists across instances."""

# ❌ Bad
def test1():
    """Test."""
```

### 4. Document Test Purpose
Always include a docstring explaining what the test does:

```python
def test_cache_loading():
    """Test that cache files are properly loaded on startup."""
```

## Troubleshooting

### Common Issues

#### 1. Config File Not Found
```
FileNotFoundError: Config file not found: my_config.yaml
```
**Solution**: Check the file path and ensure the file exists.

#### 2. ASCOM Driver Not Found
```
Failed to connect to ASCOM camera: ...
```
**Solution**: Verify the ASCOM driver is installed and the driver ID is correct.

#### 3. Cache File Issues
```
Cache file does not exist
```
**Solution**: Run a cooling operation first to create the cache file.

### Debug Mode

Use debug mode for detailed logging:

```bash
python tests/test_cache_debug.py --debug
```

This will show:
- Cache loading details
- ASCOM driver interactions
- Configuration loading
- All debug messages

## Examples

### Example 1: Test with Different Camera
```bash
# Test with QHY camera
python tests/test_cooling_cache.py --driver ASCOM.QHYCCD.Camera --debug

# Test with ZWO camera
python tests/test_cooling_cache.py --driver ASCOM.ZWOCamera.Camera --debug
```

### Example 2: Test with Custom Config
```bash
# Create custom config for testing
cp tests/test_config_example.yaml my_test_config.yaml
# Edit my_test_config.yaml as needed

# Run test with custom config
python tests/test_cache_debug.py --config my_test_config.yaml --verbose
```

### Example 3: Compare Different Configs
```bash
# Test with default config
python tests/test_cooling_cache.py --verbose

# Test with custom config
python tests/test_cooling_cache.py --config tests/test_config_example.yaml --verbose
``` 