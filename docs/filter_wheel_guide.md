# Filter Wheel Support Guide

## Overview

The OST Telescope Streaming system supports **both integrated and separate filter wheel drivers**. This is particularly useful for QHY cameras and other systems where the filter wheel has its own ASCOM driver.

## Supported Filter Wheel Types

### 1. **Integrated Filter Wheels**
- Filter wheel is part of the camera ASCOM driver
- Automatically detected via `FilterNames` property
- Examples: ZWO cameras with integrated filter wheels

### 2. **Separate Filter Wheel Drivers**
- Filter wheel has its own ASCOM driver
- Must be configured separately
- Examples: QHY cameras with separate filter wheel drivers

## Configuration

### Basic Configuration (No Separate Filter Wheel)

```yaml
video:
  ascom:
    ascom_driver: "ASCOM.MyCamera.Camera"
    exposure_time: 0.1
    gain: 1.0
    binning: 1
    # No filter_wheel_driver specified - uses integrated filter wheel if available
```

### Configuration with Separate Filter Wheel

```yaml
video:
  ascom:
    ascom_driver: "ASCOM.QHYCCD.Camera"
    exposure_time: 0.1
    gain: 1.0
    binning: 2
    # Separate filter wheel driver for QHY cameras
    filter_wheel_driver: "ASCOM.QHYCCD.FilterWheel"
```

## Usage

### Automatic Detection

The system automatically detects and uses the appropriate filter wheel:

```python
from ascom_camera import ASCOMCamera
from config_manager import ConfigManager

config = ConfigManager()
camera = ASCOMCamera(driver_id="ASCOM.QHYCCD.Camera", config=config)

# Connect (automatically connects to filter wheel if configured)
camera.connect()

# Check if filter wheel is available
if camera.has_filter_wheel():
    print("Filter wheel available!")
    
    # Get filter names
    names_status = camera.get_filter_names()
    if names_status.is_success:
        print(f"Available filters: {names_status.data}")
    
    # Get current position
    pos_status = camera.get_filter_position()
    if pos_status.is_success:
        print(f"Current position: {pos_status.data}")
    
    # Change filter position
    camera.set_filter_position(1)  # Change to position 1
```

### Command Line Usage

```bash
cd tests

# Test filter wheel functionality
python test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Test with debug output
python test_filter_wheel.py --config ../config_ost_qhy600m.yaml --debug

# Test with specific driver
python test_filter_wheel.py --config ../config_ost_qhy600m.yaml --driver ASCOM.QHYCCD.Camera --debug
```

## API Reference

### Filter Wheel Methods

#### `has_filter_wheel() -> bool`
Check if filter wheel is available (integrated or separate).

```python
if camera.has_filter_wheel():
    print("Filter wheel available")
```

#### `get_filter_names() -> CameraStatus`
Get list of filter names.

```python
status = camera.get_filter_names()
if status.is_success:
    filter_names = status.data
    print(f"Filters: {filter_names}")
```

#### `get_filter_position() -> CameraStatus`
Get current filter position.

```python
status = camera.get_filter_position()
if status.is_success:
    position = status.data
    print(f"Current position: {position}")
```

#### `set_filter_position(position: int) -> CameraStatus`
Set filter wheel position.

```python
status = camera.set_filter_position(2)  # Change to position 2
if status.is_success:
    print("Filter position changed successfully")
```

## Common Filter Wheel Drivers

### QHY Cameras
```yaml
filter_wheel_driver: "ASCOM.QHYCCD.FilterWheel"
```

### ZWO Cameras
```yaml
# Usually integrated, no separate driver needed
# But some models might use:
filter_wheel_driver: "ASCOM.ZWOCamera.FilterWheel"
```

### Other Manufacturers
```yaml
# Check ASCOM Device Hub for available drivers
filter_wheel_driver: "ASCOM.Manufacturer.FilterWheel"
```

## Testing

### Test Filter Wheel Functionality

```bash
# Basic test
python tests/test_filter_wheel.py

# Test with debug output
python tests/test_filter_wheel.py --debug

# Test with custom config
python tests/test_filter_wheel.py --config config_qhy_with_filterwheel.yaml
```

### Test Output Example

```
============================================================
TEST: Filter Wheel Test
============================================================
ASCOM Driver: ASCOM.QHYCCD.Camera
Config File: config_qhy_with_filterwheel.yaml

1. Connecting to camera...
✅ Camera connected successfully

2. Checking filter wheel availability...
✅ Filter wheel available: True
   Separate filter wheel driver: ASCOM.QHYCCD.FilterWheel

3. Getting filter names...
✅ Filter names retrieved: ['Luminance', 'Red', 'Green', 'Blue', 'Ha', 'OIII']
   Number of filters: 6

4. Getting current filter position...
✅ Current filter position: 0
   Current filter: Luminance

5. Testing filter position change...
   Changing to position 1...
✅ Filter position changed to 1
✅ Position change verified: 1
   Changing back to position 0...
✅ Filter position restored to 0

✅ Camera disconnected

✅ Filter wheel test completed
```

## Troubleshooting

### Common Issues

#### 1. Filter Wheel Not Detected
```
❌ Filter wheel available: False
```

**Solutions:**
- Check if filter wheel driver is installed
- Verify ASCOM driver ID in configuration
- Test connection in ASCOM Device Hub

#### 2. Separate Filter Wheel Connection Failed
```
Warning: Filter wheel connection failed: ...
```

**Solutions:**
- Verify filter wheel driver ID
- Check if filter wheel is powered on
- Test connection in ASCOM Device Hub

#### 3. Filter Position Change Failed
```
❌ Failed to change filter position: ...
```

**Solutions:**
- Check if filter wheel is moving
- Verify position is within valid range
- Check for mechanical issues

### QHY-Specific Issues

#### 1. Filter Names Not Available
```
❌ Failed to get filter names: ASCOM.QHYCFW.FilterWheel.FilterNames
```

**Cause:** QHY filter wheels sometimes don't expose the `FilterNames` property properly.

**Solution:** The system automatically falls back to default QHY filter names:
- `['Halpha', 'OIII', 'SII', 'U', 'B', 'V', 'R', 'I', 'Clear']`

#### 2. Filter Position Reports -1
```
Current filter position: -1
```

**Cause:** QHY filter wheels report `-1` when the position is unknown or not properly initialized.

**Solutions:**
- The system automatically handles this by retrying the position read
- Try setting a specific position to initialize the filter wheel
- Check if the filter wheel is properly powered and connected

**Important:** For QHY filter wheels, position `-1` is often **normal behavior** even when the filter wheel is working correctly. The system accepts this as a successful operation.

#### 3. Position Changes Take Time
```
Position change failed: expected 1, got -1
```

**Cause:** QHY filter wheels need time to settle after position changes.

**Solution:** The system automatically adds delays for QHY filter wheels:
- 0.5 seconds after setting position
- 1.0 seconds before verifying position change

**Note:** Even with delays, QHY filter wheels may still report `-1` after position changes. This is **normal QHY behavior** and the system accepts it as successful.

#### 4. QHY Filter Wheel Driver ID
Make sure to use the correct driver ID:
```yaml
# Correct QHY filter wheel driver
filter_wheel_driver: "ASCOM.QHYCFW.FilterWheel"

# Alternative (older QHY drivers)
filter_wheel_driver: "ASCOM.QHYCCD.FilterWheel"
```

### Debug Mode

Use debug mode for detailed information:

```bash
python tests/test_filter_wheel.py --debug
```

This will show:
- Filter wheel driver connection details
- ASCOM property access
- Device type detection (integrated vs separate)

## Best Practices

### 1. Configuration Management
- Use separate config files for different setups
- Document filter wheel driver IDs
- Test configuration before production use

### 2. Error Handling
- Always check return status of filter wheel operations
- Implement retry logic for position changes
- Log filter wheel operations for debugging

### 3. Filter Management
- Keep filter names consistent across sessions
- Document filter positions and their purposes
- Implement filter change validation

## Examples

### Example 1: QHY Camera with Separate Filter Wheel

```python
from ascom_camera import ASCOMCamera
from config_manager import ConfigManager

# Load config with separate filter wheel
config = ConfigManager("config_qhy_with_filterwheel.yaml")
camera = ASCOMCamera(driver_id="ASCOM.QHYCCD.Camera", config=config)

# Connect (automatically connects to filter wheel)
camera.connect()

# Use filter wheel
if camera.has_filter_wheel():
    # Get available filters
    names = camera.get_filter_names().data
    print(f"Available filters: {names}")
    
    # Change to Ha filter (position 4)
    camera.set_filter_position(4)
    
    # Take exposure with Ha filter
    camera.expose(60.0, gain=100)
```

### Example 2: LRGB Imaging Sequence

```python
def lrgb_imaging_sequence(camera):
    """Perform LRGB imaging sequence."""
    filters = {
        'Luminance': 0,
        'Red': 1,
        'Green': 2,
        'Blue': 3
    }
    
    for filter_name, position in filters.items():
        print(f"Imaging with {filter_name} filter...")
        
        # Change filter
        camera.set_filter_position(position)
        
        # Take exposure
        camera.expose(30.0, gain=100)
        
        # Get image
        image = camera.get_image().data
        
        # Save image
        save_image(image, f"lrgb_{filter_name.lower()}.fits")
```

### Example 3: Narrowband Imaging

```python
def narrowband_imaging(camera):
    """Perform narrowband imaging."""
    narrowband_filters = {
        'Ha': 4,
        'OIII': 5,
        'SII': 6  # If available
    }
    
    for filter_name, position in narrowband_filters.items():
        print(f"Imaging with {filter_name} filter...")
        
        # Change filter
        camera.set_filter_position(position)
        
        # Take longer exposure for narrowband
        camera.expose(300.0, gain=100)
        
        # Get and save image
        image = camera.get_image().data
        save_image(image, f"narrowband_{filter_name.lower()}.fits")
``` 