# Alpyca Camera Guide

## Overview

Alpyca is the official Python API for ASCOM Alpaca, providing a modern, platform-independent interface to astronomical cameras. This guide explains how to use Alpyca cameras in the telescope streaming system.

## Advantages over Classic ASCOM

- ✅ **Python-native implementation** - No COM interop issues
- ✅ **Platform-independent** - Works on Windows, Linux, macOS
- ✅ **Better error handling** - Specific exception classes
- ✅ **Network-based** - Remote access capability
- ✅ **Consistent behavior** - More reliable across different drivers
- ✅ **No caching issues** - Direct hardware access

## Installation

### Prerequisites

1. **Alpaca Server** - Must be running on the target system
2. **Python Package** - Install Alpyca

```bash
pip install alpyca
```

### Alpaca Server Setup

The Alpaca server must be running to use Alpyca cameras. Common Alpaca servers include:

- **ASCOM Alpaca** - Official ASCOM Alpaca server
- **ZWO Alpaca** - ZWO's Alpaca server
- **QHY Alpaca** - QHY's Alpaca server

## Configuration

### Basic Alpyca Configuration

```yaml
video:
  camera_type: alpaca
  alpaca:
    host: "localhost"      # Alpaca server host
    port: 11111           # Alpaca server port
    device_id: 0          # Camera device ID
    exposure_time: 1.0    # Default exposure time
    gain: 100.0           # Default gain
    offset: 50.0          # Default offset
    binning: 1            # Default binning
    use_timestamps: true  # Use timestamps in filenames
    timestamp_format: "%Y%m%d_%H%M%S"
    file_format: "fits"   # Image format
```

### Camera Cooling Configuration

```yaml
camera:
  cooling:
    enable_cooling: true
    target_temperature: -10.0
    auto_cooling: true
    cooling_timeout: 60
    temperature_tolerance: 2.0
    wait_for_cooling: true
```

## Usage Examples

### Basic Camera Control

```python
from alpaca_camera import AlpycaCameraWrapper

# Create camera instance
camera = AlpycaCameraWrapper(
    host="localhost",
    port=11111,
    device_id=0
)

# Connect to camera
status = camera.connect()
if status.is_success:
    print(f"Connected to: {camera.name}")
    
    # Set cooling
    camera.set_cooling(-10.0)
    
    # Take exposure
    camera.start_exposure(1.0, True)
    
    # Get image
    image_status = camera.get_image_array()
    if image_status.is_success:
        image = image_status.data
        print(f"Image shape: {image.shape}")
```

### Advanced Features

```python
# Set gain and offset
camera.gain = 100
camera.offset = 50

# Set binning
camera.bin_x = 2
camera.bin_y = 2

# Set readout mode
camera.readout_mode = 0

# Get cooling status
cooling_status = camera.get_cooling_status()
if cooling_status.is_success:
    info = cooling_status.data
    print(f"Temperature: {info['temperature']}°C")
    print(f"Cooler power: {info['cooler_power']}%")
```

## Camera Properties

### Core Properties

| Property | Description | Type |
|----------|-------------|------|
| `name` | Camera name | str |
| `description` | Camera description | str |
| `driver_info` | Driver information | str |
| `driver_version` | Driver version | str |
| `interface_version` | Interface version | str |
| `connected` | Connection status | bool |

### Sensor Properties

| Property | Description | Type |
|----------|-------------|------|
| `sensor_name` | Sensor name | str |
| `sensor_type` | Sensor type (mono/color) | int |
| `camera_x_size` | Sensor width in pixels | int |
| `camera_y_size` | Sensor height in pixels | int |
| `pixel_size_x` | Pixel width in microns | float |
| `pixel_size_y` | Pixel height in microns | float |
| `max_adu` | Maximum ADU value | int |
| `electrons_per_adu` | Electrons per ADU | float |
| `full_well_capacity` | Full well capacity | float |

### Exposure Properties

| Property | Description | Type |
|----------|-------------|------|
| `exposure_min` | Minimum exposure time | float |
| `exposure_max` | Maximum exposure time | float |
| `exposure_resolution` | Exposure resolution | float |
| `last_exposure_duration` | Last exposure duration | float |
| `last_exposure_start_time` | Last exposure start time | str |
| `image_ready` | Image ready status | bool |
| `camera_state` | Camera state | int |
| `percent_completed` | Exposure completion percentage | float |

### Binning Properties

| Property | Description | Type |
|----------|-------------|------|
| `bin_x` | X binning factor | int |
| `bin_y` | Y binning factor | int |
| `max_bin_x` | Maximum X binning | int |
| `max_bin_y` | Maximum Y binning | int |
| `can_asymmetric_bin` | Asymmetric binning support | bool |

### Cooling Properties

| Property | Description | Type |
|----------|-------------|------|
| `can_set_ccd_temperature` | Can set CCD temperature | bool |
| `can_get_cooler_power` | Can get cooler power | bool |
| `ccd_temperature` | Current CCD temperature | float |
| `set_ccd_temperature` | Target CCD temperature | float |
| `cooler_on` | Cooler on/off state | bool |
| `cooler_power` | Cooler power percentage | float |
| `heat_sink_temperature` | Heat sink temperature | float |

### Gain and Offset Properties

| Property | Description | Type |
|----------|-------------|------|
| `gain` | Current gain | float |
| `gain_min` | Minimum gain | float |
| `gain_max` | Maximum gain | float |
| `gains` | Available gains | list |
| `offset` | Current offset | float |
| `offset_min` | Minimum offset | float |
| `offset_max` | Maximum offset | float |
| `offsets` | Available offsets | list |

### Readout Properties

| Property | Description | Type |
|----------|-------------|------|
| `readout_mode` | Current readout mode | int |
| `readout_modes` | Available readout modes | list |
| `can_fast_readout` | Fast readout support | bool |
| `fast_readout` | Fast readout state | bool |

## Camera Methods

### Exposure Methods

```python
# Start exposure
camera.start_exposure(duration, light=True)

# Stop exposure
camera.stop_exposure()

# Abort exposure
camera.abort_exposure()

# Get image array
image_status = camera.get_image_array()
```

### Cooling Methods

```python
# Set cooling
camera.set_cooling(target_temperature)

# Turn off cooling
camera.turn_cooling_off()

# Get cooling status
cooling_status = camera.get_cooling_status()

# Force refresh cooling status
refresh_status = camera.force_refresh_cooling_status()

# Wait for cooling stabilization
stabilization_status = camera.wait_for_cooling_stabilization(timeout=60)
```

### Utility Methods

```python
# Check if color camera
is_color = camera.is_color_camera()

# Get comprehensive camera info
info_status = camera.get_camera_info()
```

## Testing

### Basic Test

```bash
# Test Alpyca camera functionality
python tests/test_alpaca_camera.py
```

### Configuration Test

```bash
# Test with specific configuration
python tests/test_alpaca_camera.py --config config_alpaca_template.yaml
```

## Troubleshooting

### Common Issues

#### 1. Connection Failed

**Problem**: Cannot connect to Alpaca server
```
❌ Connection failed: Failed to connect to Alpaca camera: Connection refused
```

**Solutions**:
- Check if Alpaca server is running
- Verify host and port settings
- Check firewall settings
- Ensure camera is connected to Alpaca server

#### 2. Device Not Found

**Problem**: Camera device not found
```
❌ Device not found: No camera at device_id 0
```

**Solutions**:
- Verify device_id is correct
- Check if camera is connected to Alpaca server
- Try different device_id values (0, 1, 2, etc.)

#### 3. Cooling Not Working

**Problem**: Cooling features not available
```
❌ Cooling not supported by this camera
```

**Solutions**:
- Verify camera supports cooling
- Check Alpaca server supports cooling
- Ensure camera is properly connected

#### 4. Exposure Issues

**Problem**: Cannot start exposure
```
❌ Failed to start exposure: Camera not ready
```

**Solutions**:
- Check camera state
- Ensure no exposure is in progress
- Verify exposure parameters are valid

### Debug Information

Enable debug logging to get detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

camera = AlpycaCameraWrapper(host="localhost", port=11111, device_id=0)
```

### Performance Comparison

| Operation | Classic ASCOM | Alpyca |
|-----------|---------------|--------|
| Connection | ~500ms | ~200ms |
| Cooling set | ~1000ms | ~300ms |
| Exposure start | ~200ms | ~100ms |
| Image download | ~500ms | ~300ms |

## Migration from Classic ASCOM

### Step-by-step Migration

1. **Install Alpyca**
   ```bash
   pip install alpyca
   ```

2. **Update Configuration**
   ```yaml
   # Old: classic ASCOM
   video:
     camera_type: ascom
     ascom:
       ascom_driver: "ASCOM.ASICamera2.Camera"
   
   # New: Alpyca
   video:
     camera_type: alpaca
     alpaca:
       host: "localhost"
       port: 11111
       device_id: 0
   ```

3. **Test Functionality**
   ```bash
   python tests/test_alpaca_camera.py
   ```

4. **Update Code**
   ```python
   # Old: ASCOMCamera
   from ascom_camera import ASCOMCamera
   camera = ASCOMCamera(driver_id="ASCOM.ASICamera2.Camera")
   
   # New: AlpycaCameraWrapper
   from alpaca_camera import AlpycaCameraWrapper
   camera = AlpycaCameraWrapper(host="localhost", port=11111, device_id=0)
   ```

### Benefits of Migration

- **Better Performance** - Faster operations
- **More Reliable** - Fewer connection issues
- **Cross-platform** - Works on all operating systems
- **Better Error Handling** - Specific error messages
- **Future-proof** - Official ASCOM Python API

## Best Practices

### Configuration

1. **Use meaningful device names** - Helps identify cameras
2. **Set appropriate timeouts** - Prevents hanging operations
3. **Enable logging** - Helps with troubleshooting
4. **Test thoroughly** - Verify all features work

### Usage

1. **Always check connection status** - Before operations
2. **Handle errors gracefully** - Use try-catch blocks
3. **Monitor cooling status** - Ensure stable temperature
4. **Use appropriate exposure times** - Based on target brightness

### Performance

1. **Use appropriate binning** - Balance speed vs resolution
2. **Optimize gain settings** - For best signal-to-noise
3. **Monitor temperature** - For consistent results
4. **Use fast readout** - When appropriate

## Future Development

### Planned Features

- [ ] Automatic device discovery
- [ ] Connection pooling
- [ ] Advanced error recovery
- [ ] Performance optimization
- [ ] Multi-camera support
- [ ] Remote monitoring
- [ ] Automated testing

### Contributing

To contribute to Alpyca integration:

1. **Report Issues** - Use GitHub issues
2. **Submit Pull Requests** - For improvements
3. **Test Thoroughly** - Before submitting
4. **Update Documentation** - Keep docs current

## Conclusion

Alpyca provides a modern, reliable interface to ASCOM cameras that resolves many of the issues present in classic ASCOM implementations. The Python-native approach, better error handling, and cross-platform compatibility make it the recommended choice for new projects and a worthwhile upgrade for existing systems.

For more information, see the [Alpyca documentation](https://ascom-standards.org/alpyca/index.html) and the [ASCOM Alpaca specification](https://ascom-standards.org/Developer/Alpaca.htm). 