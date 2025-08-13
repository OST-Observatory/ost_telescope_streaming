# ASCOM Camera Guide

## Overview

The OST Telescope Streaming system provides comprehensive support for ASCOM-compatible cameras, including advanced features like cooling, offset control, and readout mode selection.

## Features

### 1. Basic Camera Control
- **Connection Management**: Automatic connection and disconnection
- **Exposure Control**: Manual exposure time setting
- **Gain Control**: Adjustable gain settings
- **Binning**: Configurable binning factors

### 2. Advanced Camera Features
- **Cooling Control**: Automatic temperature regulation
- **Offset Control**: Adjustable offset settings (0-255 typically)
- **Readout Mode Selection**: Camera-specific readout modes
- **Filter Wheel Support**: Integrated and separate filter wheel support

### 3. Image Processing
- **Debayering**: Automatic Bayer pattern detection and conversion
- **FITS Support**: Native FITS file format with astronomical headers
- **Calibration**: Automatic dark and flat frame correction

## Configuration

### ASCOM Camera Settings

```yaml
video:
  camera_type: "ascom"
  ascom:
    ascom_driver: "ASCOM.ASICamera2.Camera"  # ASCOM driver ID
    exposure_time: 5.0                       # Exposure time in seconds
    gain: 1.0                                # Gain setting
    offset: 0                                # Offset setting (0-255)
    readout_mode: 0                          # Readout mode (camera-specific)
    binning: 1                               # Binning factor
    filter_wheel_driver: null                # Optional separate filter wheel
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ascom_driver` | - | ASCOM driver program ID |
| `exposure_time` | 1.0 | Exposure time in seconds |
| `gain` | 1.0 | Gain setting |
| `offset` | 0 | Offset setting (0-255 typically) |
| `readout_mode` | 0 | Readout mode index |
| `binning` | 1 | Binning factor (1x1, 2x2, etc.) |
| `filter_wheel_driver` | null | Separate filter wheel driver ID |

## Usage Examples

### 1. Basic Camera Setup

```python
from code.video_capture import VideoCapture
from code.config_manager import ConfigManager

# Load configuration
config = ConfigManager('config.yaml')

# Initialize camera
video_capture = VideoCapture(config=config)

# Connection is handled during initialization; verify via adapter
if hasattr(video_capture, 'camera') and video_capture.camera:
    print("Camera available via adapter")
    
    # Get camera information
    # Adapter-provided camera info when available
    if hasattr(video_capture, 'camera') and video_capture.camera and hasattr(video_capture.camera, 'get_camera_info'):
        info_status = video_capture.camera.get_camera_info()
        camera_info = info_status.data if info_status.is_success else {}
    else:
        camera_info = {}
    print(f"Camera: {camera_info['driver_id']}")
    print(f"Resolution: {camera_info['frame_width']}x{camera_info['frame_height']}")
```

### 2. Advanced Camera Control

```python
# Get camera capabilities
capabilities = video_capture.ascom_camera.get_camera_capabilities()
if capabilities.is_success:
    caps = capabilities.data
    print(f"Has cooling: {caps['has_cooling']}")
    print(f"Has offset: {caps['has_offset']}")
    print(f"Has readout mode: {caps['has_readout_mode']}")
    print(f"Is color: {caps['is_color']}")

# Set offset if supported
if caps['has_offset']:
    offset_status = video_capture.ascom_camera.set_offset(10)
    if offset_status.is_success:
        print(f"Offset set to: {offset_status.data['new_offset']}")

# Set readout mode if supported
if caps['has_readout_mode']:
    readout_status = video_capture.ascom_camera.set_readout_mode(1)
    if readout_status.is_success:
        print(f"Readout mode set to: {readout_status.data['new_mode']}")
```

### 3. Capture with Advanced Settings

```python
# Capture frame with all parameters
status = video_capture.capture_single_frame_ascom(
    exposure_time_s=5.0,
    gain=100,
    binning=2
)

if status.is_success:
    frame_data = status.data
    frame_details = status.details
    print(f"Frame captured: {frame_details['dimensions']}")
    print(f"Exposure: {frame_details['exposure_time_s']}s")
    print(f"Gain: {frame_details['gain']}")
    print(f"Offset: {frame_details['offset']}")
    print(f"Readout mode: {frame_details['readout_mode']}")
```

## Camera-Specific Features

### 1. Offset Control

The offset parameter adjusts the baseline level of the camera's analog-to-digital converter:

```python
# Check if offset is supported
if video_capture.ascom_camera.has_offset():
    # Get current offset
    offset_status = video_capture.ascom_camera.get_offset()
    print(f"Current offset: {offset_status.data}")
    
    # Set new offset
    set_status = video_capture.ascom_camera.set_offset(20)
    if set_status.is_success:
        print(f"Offset changed from {set_status.details['previous_offset']} to {set_status.details['new_offset']}")
```

**Offset Guidelines:**
- **Typical Range**: 0-255 for most cameras
- **Low Offset**: Reduces noise but may clip dark pixels
- **High Offset**: Prevents clipping but increases noise
- **Optimal Setting**: Depends on camera and imaging conditions

### 2. Readout Mode Selection

Readout modes control how the camera reads out the sensor data:

```python
# Check if readout mode is supported
if video_capture.ascom_camera.has_readout_mode():
    # Get available readout modes
    modes_status = video_capture.ascom_camera.get_readout_modes()
    if modes_status.is_success:
        print(f"Available readout modes: {modes_status.data}")
    
    # Get current readout mode
    current_status = video_capture.ascom_camera.get_readout_mode()
    print(f"Current readout mode: {current_status.data}")
    
    # Set readout mode
    set_status = video_capture.ascom_camera.set_readout_mode(1)
    if set_status.is_success:
        print(f"Readout mode changed from {set_status.details['previous_mode']} to {set_status.details['new_mode']}")
```

**Common Readout Modes:**
- **Mode 0**: Standard readout (default)
- **Mode 1**: High-speed readout
- **Mode 2**: Low-noise readout
- **Mode 3**: High-gain readout
- **Mode 4**: Low-gain readout

*Note: Available modes vary by camera model*

### 3. Filter Wheel Support

The system supports both integrated and separate filter wheels:

```python
# Check if filter wheel is available
if video_capture.ascom_camera.has_filter_wheel():
    # Get filter names
    filters_status = video_capture.ascom_camera.get_filter_names()
    if filters_status.is_success:
        print(f"Available filters: {filters_status.data}")
    
    # Get current filter position
    position_status = video_capture.ascom_camera.get_filter_position()
    print(f"Current filter position: {position_status.data}")
    
    # Set filter position
    set_status = video_capture.ascom_camera.set_filter_position(2)
    if set_status.is_success:
        print("Filter position set successfully")
```

## Camera Capabilities Detection

The system automatically detects camera capabilities:

```python
# Get comprehensive camera capabilities
capabilities = video_capture.ascom_camera.get_camera_capabilities()
if capabilities.is_success:
    caps = capabilities.data
    
    print("Camera Capabilities:")
    print(f"  Cooling: {caps['has_cooling']}")
    print(f"  Offset: {caps['has_offset']}")
    print(f"  Readout Mode: {caps['has_readout_mode']}")
    print(f"  Gain: {caps['has_gain']}")
    print(f"  Binning: {caps['has_binning']}")
    print(f"  Color: {caps['is_color']}")
    print(f"  Filter Wheel: {caps['has_filter_wheel']}")
    
    # Show current values for supported features
    if caps['has_offset']:
        print(f"  Current Offset: {caps['current_offset']}")
    
    if caps['has_readout_mode']:
        print(f"  Current Readout Mode: {caps['current_readout_mode']}")
        print(f"  Available Readout Modes: {caps['available_readout_modes']}")
    
    if caps['has_gain']:
        print(f"  Current Gain: {caps['current_gain']}")
    
    if caps['has_binning']:
        print(f"  Current Binning: {caps['current_binning_x']}x{caps['current_binning_y']}")
```

## Error Handling

The system provides comprehensive error handling:

```python
# Example: Setting unsupported parameter
if not video_capture.ascom_camera.has_offset():
    offset_status = video_capture.ascom_camera.set_offset(10)
    if not offset_status.is_success:
        print(f"Offset error: {offset_status.message}")

# Example: Invalid parameter value
readout_status = video_capture.ascom_camera.set_readout_mode(999)
if not readout_status.is_success:
    print(f"Readout mode error: {readout_status.message}")
```

## Best Practices

### 1. Parameter Optimization

**Offset Settings:**
- Start with default offset (usually 0)
- Adjust based on dark frame analysis
- Avoid clipping in dark areas
- Consider camera temperature

**Readout Mode Selection:**
- Use standard mode for general imaging
- Use high-speed mode for planetary imaging
- Use low-noise mode for deep-sky imaging
- Test different modes for your specific use case

### 2. Configuration Management

```yaml
# Example: Optimized configuration for deep-sky imaging
video:
  ascom:
    ascom_driver: "ASCOM.ASICamera2.Camera"
    exposure_time: 300.0  # 5 minutes
    gain: 139             # Unity gain for ASI2600MM Pro
    offset: 21            # Optimized offset
    readout_mode: 2       # Low-noise mode
    binning: 1            # No binning for maximum resolution
```

### 3. Performance Monitoring

```python
# Monitor camera performance during long sessions
while imaging_session_active:
    # Get current camera status
    if hasattr(video_capture, 'camera') and video_capture.camera and hasattr(video_capture.camera, 'get_camera_info'):
        info_status = video_capture.camera.get_camera_info()
        camera_info = info_status.data if info_status.is_success else {}
    else:
        camera_info = {}
    
    # Log important parameters
    print(f"Temperature: {camera_info.get('current_temperature', 'N/A')}°C")
    print(f"Gain: {camera_info.get('gain', 'N/A')}")
    print(f"Offset: {camera_info.get('offset', 'N/A')}")
    print(f"Readout Mode: {camera_info.get('readout_mode', 'N/A')}")
    
    time.sleep(60)  # Check every minute
```

## Troubleshooting

### Common Issues

1. **Parameter Not Supported**
   ```python
   if not video_capture.ascom_camera.has_offset():
       print("This camera does not support offset control")
   ```

2. **Invalid Parameter Values**
   ```python
   # Check parameter ranges
   if offset < 0 or offset > 255:
       print("Offset must be between 0 and 255")
   ```

3. **Driver Compatibility**
   ```python
   # Check driver version and capabilities
   capabilities = video_capture.ascom_camera.get_camera_capabilities()
   print(f"Driver supports advanced features: {capabilities.is_success}")
   ```

### Debug Information

Enable debug logging for detailed information:

```python
import logging
logging.getLogger('ascom_camera').setLevel(logging.DEBUG)
```

This will show:
- Parameter setting attempts
- Driver interactions
- Error details and diagnostics
- Capability detection results

## Future Enhancements

- **Parameter Validation**: Automatic validation of parameter ranges
- **Camera Profiles**: Pre-configured settings for different imaging types
- **Auto-Optimization**: Automatic parameter optimization based on conditions
- **Multi-Camera Support**: Support for multiple cameras simultaneously
- **Advanced Filtering**: Enhanced filter wheel control and automation 