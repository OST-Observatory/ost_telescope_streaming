# ASCOM Camera Integration Guide

## Overview

The OST Telescope Streaming system now supports ASCOM-compatible astronomical cameras, including QHY and ZWO cameras. This integration provides access to advanced features like cooling, filter wheel control, and automatic debayering for color cameras.

## Features

### Core Camera Control
- **Connection Management**: Connect/disconnect to ASCOM camera drivers
- **Exposure Control**: Take exposures with configurable time, gain, and binning
- **Image Retrieval**: Download captured images from the camera

### Advanced Features
- **Cooling Control**: Set and monitor camera temperature (if supported)
- **Filter Wheel Control**: Control filter wheel position and get filter names (if available)
- **Automatic Debayering**: Process raw Bayer-pattern images from color cameras into RGB images

## Configuration

### Basic Setup

Add the following to your `config.yaml`:

```yaml
video:
  # Camera type: 'opencv' for regular video cameras, 'ascom' for astro cameras
  camera_type: "ascom"
  # ASCOM driver ID for your camera
  ascom_driver: "ASCOM.QHYCamera.Camera"  # or "ASCOM.ZWOCamera.Camera"
```

### Common ASCOM Driver IDs

- **QHY Cameras**: `"ASCOM.QHYCamera.Camera"`
- **ZWO Cameras**: `"ASCOM.ZWOCamera.Camera"`
- **Other ASCOM Cameras**: Check your camera's documentation for the correct driver ID

## Usage Examples

### Command Line Interface

The `main_video_capture.py` script provides a comprehensive CLI for ASCOM camera control:

#### Basic Capture
```bash
python main_video_capture.py --camera-type ascom --ascom-driver "ASCOM.QHYCamera.Camera" --exposure 5.0 --gain 20 --output test_image.jpg
```

#### Camera Information
```bash
python main_video_capture.py --camera-type ascom --ascom-driver "ASCOM.QHYCamera.Camera" --action info
```

#### Cooling Control
```bash
python main_video_capture.py --camera-type ascom --ascom-driver "ASCOM.QHYCamera.Camera" --action cooling --cooling-temp -10.0
```

#### Filter Wheel Control
```bash
python main_video_capture.py --camera-type ascom --ascom-driver "ASCOM.QHYCamera.Camera" --action filter --filter-position 2
```

#### Debayered Capture
```bash
python main_video_capture.py --camera-type ascom --ascom-driver "ASCOM.QHYCamera.Camera" --action debayer --exposure 3.0 --gain 15 --output color_image.jpg
```

### Python API

#### Basic Usage
```python
from code.ascom_camera import ASCOMCamera
from code.config_manager import config

# Create camera instance
camera = ASCOMCamera(driver_id="ASCOM.QHYCamera.Camera", config=config)

# Connect
status = camera.connect()
if status.is_success:
    print("Camera connected")
    
    # Take exposure
    expose_status = camera.expose(5.0, gain=20)  # 5 seconds, gain=20
    if expose_status.is_success:
        # Get image
        image_status = camera.get_image()
        if image_status.is_success:
            # Process image...
            pass
    
    # Disconnect
    camera.disconnect()
```

#### Cooling Control
```python
if camera.has_cooling():
    # Set cooling temperature
    cooling_status = camera.set_cooling(-10.0)  # -10°C
    
    # Get current temperature
    temp_status = camera.get_temperature()
    if temp_status.is_success:
        print(f"Current temperature: {temp_status.data}°C")
```

#### Filter Wheel Control
```python
if camera.has_filter_wheel():
    # Get available filters
    filters_status = camera.get_filter_names()
    if filters_status.is_success:
        print(f"Available filters: {filters_status.data}")
    
    # Set filter position
    filter_status = camera.set_filter_position(2)  # Position 2
    
    # Get current position
    pos_status = camera.get_filter_position()
    if pos_status.is_success:
        print(f"Current position: {pos_status.data}")
```

#### Debayering
```python
# Check if color camera
if camera.is_color_camera():
    # Take exposure
    camera.expose(3.0, gain=15)
    image_status = camera.get_image()
    
    if image_status.is_success:
        # Debayer the image
        debayer_status = camera.debayer(image_status.data)
        if debayer_status.is_success:
            # debayer_status.data contains the RGB image
            import cv2
            cv2.imwrite("debayered.jpg", debayer_status.data)
```

## API Reference

### ASCOMCamera Class

#### Constructor
```python
ASCOMCamera(driver_id: str, config=None, logger=None)
```

#### Methods

##### Connection
- `connect() -> CameraStatus`: Connect to the ASCOM camera
- `disconnect() -> CameraStatus`: Disconnect from the camera

##### Basic Control
- `expose(exposure_time_s: float, gain: Optional[int] = None, binning: int = 1) -> CameraStatus`: Start exposure
- `get_image() -> CameraStatus`: Retrieve captured image

##### Cooling (if supported)
- `has_cooling() -> bool`: Check if camera supports cooling
- `set_cooling(target_temp: float) -> CameraStatus`: Set cooling temperature
- `get_temperature() -> CameraStatus`: Get current temperature

##### Filter Wheel (if available)
- `has_filter_wheel() -> bool`: Check if camera has filter wheel
- `get_filter_names() -> CameraStatus`: Get list of filter names
- `set_filter_position(position: int) -> CameraStatus`: Set filter wheel position
- `get_filter_position() -> CameraStatus`: Get current filter position

##### Debayering
- `is_color_camera() -> bool`: Check if camera is color
- `debayer(img_array: Any, pattern: str = 'RGGB') -> CameraStatus`: Debayer raw image

## Status Objects

All methods return `CameraStatus` objects with the following structure:

```python
@dataclass
class CameraStatus(Status[Any]):
    level: StatusLevel  # SUCCESS, WARNING, ERROR, CRITICAL
    message: str        # Human-readable message
    data: Optional[Any] = None  # Return data (image, temperature, etc.)
    details: Optional[Dict[str, Any]] = None  # Additional details
```

### Status Properties
- `is_success`: True if level is SUCCESS
- `is_warning`: True if level is WARNING
- `is_error`: True if level is ERROR or CRITICAL

## Error Handling

The system provides comprehensive error handling through status objects:

```python
status = camera.connect()
if not status.is_success:
    print(f"Connection failed: {status.message}")
    if status.details:
        print(f"Details: {status.details}")
    return

# Check for warnings
if status.is_warning:
    print(f"Warning: {status.message}")
```

## Testing

Run the ASCOM camera tests:

```bash
python tests/test_ascom_camera.py
```

This will test:
- Basic camera functionality
- Method signatures
- Status object returns
- Configuration integration
- CLI integration

## Troubleshooting

### Common Issues

1. **Driver Not Found**: Ensure the ASCOM driver is properly installed and the driver ID is correct
2. **Connection Failed**: Check that the camera is connected and the driver is running
3. **Feature Not Supported**: Some features (cooling, filter wheel) may not be available on all cameras
4. **Debayering Errors**: Ensure OpenCV is installed for debayering functionality

### Debug Mode

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with VideoCapture

The `VideoCapture` class automatically integrates ASCOM cameras when configured:

```python
from code.video_capture import VideoCapture

# Configure for ASCOM camera
config['video']['camera_type'] = 'ascom'
config['video']['ascom_driver'] = 'ASCOM.QHYCamera.Camera'

capture = VideoCapture(config=config)

# Connect and capture
capture.connect()
status = capture.capture_single_frame_ascom(exposure_time_s=5.0, gain=20)
if status.is_success:
    capture.save_frame(status.data, "captured.jpg")
```

## Examples

See `examples/ascom_camera_example.py` for a complete working example that demonstrates all features. 