# Automatic Calibration Guide

## Overview

The OST Telescope Streaming system now includes advanced automatic calibration that considers **camera settings matching** in addition to exposure time matching. This ensures that calibration frames are applied only when they were captured with the same camera settings as the science frames.

## Key Features

### 1. Camera Settings Matching
- **Gain Matching**: Ensures master frames were captured with the same gain setting
- **Offset Matching**: Ensures master frames were captured with the same offset setting
- **Readout Mode Matching**: Ensures master frames were captured with the same readout mode
- **Exposure Time Matching**: Ensures master darks match the frame exposure time

### 2. Intelligent Frame Selection
- **Weighted Scoring**: Exposure time has highest priority, followed by camera settings
- **Tolerance Control**: Configurable tolerance for setting differences
- **Fallback Handling**: Graceful degradation when exact matches aren't available

### 3. Comprehensive Logging
- **Detailed Matching Info**: Shows which master frames are used and why
- **Settings Comparison**: Logs the settings of both frame and master frames
- **Warning Messages**: Alerts when no suitable master frames are found

## Configuration

### Calibration Settings

```yaml
master_frames:
  # Output directory for master frames
  output_dir: "master_frames"

  # Automatic calibration settings
  enable_calibration: true          # Enable automatic calibration
  auto_load_masters: true           # Auto-load master frames on startup
  calibration_tolerance: 0.1        # 10% tolerance for matching
```

### Camera Settings in Frame Capture

```yaml
video:
  ascom:
    ascom_driver: "ASCOM.ASICamera2.Camera"
    exposure_time: 5.0              # Exposure time in seconds
    gain: 100.0                     # Gain setting
    offset: 50                      # Offset setting (0-255)
    readout_mode: 0                 # Readout mode (camera-specific)
    binning: 1                      # Binning factor
```

## How It Works

### 1. Frame Information Extraction

When a frame is captured, the system automatically extracts camera settings:

```python
# Frame information passed to calibration
frame_info = {
    'exposure_time': 5.0,
    'gain': 100.0,
    'offset': 50,
    'readout_mode': 0,
    'dimensions': '2048x2048',
    'debayered': True
}
```

### 2. Master Frame Matching Algorithm

The system uses a weighted scoring algorithm to find the best matching master frames:

```python
# Weighted scoring (exposure time is most important)
score = (exp_diff * 10.0 +      # Exposure time weight: 10
        gain_diff * 1.0 +       # Gain weight: 1
        offset_diff * 1.0 +     # Offset weight: 1
        readout_diff * 1.0)     # Readout mode weight: 1
```

### 3. Master Dark Selection

For master darks, the system considers:
- **Exposure Time**: Must be within tolerance (default: 10%)
- **Gain**: Should match exactly or be very close
- **Offset**: Should match exactly or be very close
- **Readout Mode**: Should match exactly

### 4. Master Flat Selection

For master flats, the system considers:
- **Gain**: Must match exactly or be very close
- **Offset**: Must match exactly or be very close
- **Readout Mode**: Must match exactly

## Usage Examples

### 1. Basic Calibration

```python
from code.video_capture import VideoCapture
from code.config_manager import ConfigManager

# Initialize camera with calibration
config = ConfigManager('config.yaml')
video_capture = VideoCapture(config=config)

# Capture frame (calibration applied automatically)
status = video_capture.capture_single_frame_ascom(
    exposure_time_s=300.0,  # 5 minutes
    gain=139,               # Unity gain
    binning=1               # No binning
)

if status.is_success:
    frame_data = status.data
    frame_details = status.details

    # Check calibration details
    if frame_details.get('calibration_applied', False):
        print("Frame was calibrated successfully")
        print(f"Dark subtraction: {frame_details['dark_subtraction_applied']}")
        print(f"Flat correction: {frame_details['flat_correction_applied']}")
        print(f"Master dark used: {frame_details['master_dark_used']}")
        print(f"Master flat used: {frame_details['master_flat_used']}")
```

### 2. Calibration Status Monitoring

```python
# Get calibration system status
calibration_status = video_capture.calibration_applier.get_calibration_status()

print("Calibration System Status:")
print(f"  Enabled: {calibration_status['enable_calibration']}")
print(f"  Auto-load: {calibration_status['auto_load_masters']}")
print(f"  Tolerance: {calibration_status['calibration_tolerance']}")
print(f"  Master darks loaded: {calibration_status['master_darks_loaded']}")
print(f"  Master flat loaded: {calibration_status['master_flat_loaded']}")
print(f"  Settings matching: {calibration_status['settings_matching_enabled']}")

# Show available master frames
for exp_time, settings in calibration_status['dark_settings'].items():
    print(f"  Dark {exp_time}: gain={settings['gain']}, offset={settings['offset']}, readout={settings['readout_mode']}")

if calibration_status['flat_settings']:
    flat = calibration_status['flat_settings']
    print(f"  Flat: gain={flat['gain']}, offset={flat['offset']}, readout={flat['readout_mode']}")
```

### 3. Manual Calibration Control

```python
# Reload master frames
success = video_capture.calibration_applier.reload_master_frames()
if success:
    print("Master frames reloaded successfully")
else:
    print("Failed to reload master frames")

# Get detailed master frame information
master_info = video_capture.calibration_applier.get_master_frame_info()

print("Master Frame Details:")
for exp_time, dark_info in master_info['master_darks'].items():
    print(f"  Dark {exp_time}:")
    print(f"    File: {dark_info['file']}")
    print(f"    Shape: {dark_info['shape']}")
    print(f"    Settings: gain={dark_info['gain']}, offset={dark_info['offset']}, readout={dark_info['readout_mode']}")

if master_info['master_flat']:
    flat = master_info['master_flat']
    print(f"  Flat:")
    print(f"    File: {flat['file']}")
    print(f"    Shape: {flat['shape']}")
    print(f"    Settings: gain={flat['gain']}, offset={flat['offset']}, readout={flat['readout_mode']}")
```

## Master Frame Requirements

### 1. Master Dark Requirements

Master darks must be captured with:
- **Same Gain**: Identical gain setting as science frames
- **Same Offset**: Identical offset setting as science frames
- **Same Readout Mode**: Identical readout mode as science frames
- **Matching Exposure Time**: Within tolerance of science frame exposure time
- **Same Temperature**: Captured at the same sensor temperature

### 2. Master Flat Requirements

Master flats must be captured with:
- **Same Gain**: Identical gain setting as science frames
- **Same Offset**: Identical offset setting as science frames
- **Same Readout Mode**: Identical readout mode as science frames
- **Same Filter**: If using filter wheel
- **Uniform Illumination**: Even illumination across the sensor

### 3. Master Bias Requirements

Master bias frames must be captured with:
- **Same Gain**: Identical gain setting as science frames
- **Same Offset**: Identical offset setting as science frames
- **Same Readout Mode**: Identical readout mode as science frames
- **Minimum Exposure**: Shortest possible exposure time

## Best Practices

### 1. Camera Settings Consistency

```yaml
# Example: Consistent settings for all calibration frames
video:
  ascom:
    # Science frame settings
    exposure_time: 300.0  # 5 minutes for science
    gain: 139             # Unity gain
    offset: 21            # Optimized offset
    readout_mode: 2       # Low-noise mode
    binning: 1            # No binning

# Calibration frames should use the same gain, offset, and readout_mode
# Only exposure time varies for darks
```

### 2. Calibration Workflow

```bash
# 1. Set camera settings for science imaging
# 2. Capture bias frames (same settings, 0.001s exposure)
python calibration/dark_capture_runner.py --bias-only

# 3. Capture dark frames (same settings, various exposures)
python calibration/dark_capture_runner.py

# 4. Capture flat frames (same settings, optimized exposure)
python calibration/flat_capture_runner.py

# 5. Create master frames
python calibration/master_frame_runner.py

# 6. Start science imaging (automatic calibration applied)
python overlay_runner.py
```

### 3. Settings Validation

```python
# Validate camera settings before capturing calibration frames
# Camera info via adapter when available
if hasattr(video_capture, 'camera') and video_capture.camera and hasattr(video_capture.camera, 'get_camera_info'):
    info_status = video_capture.camera.get_camera_info()
    if info_status.is_success:
        camera_info = info_status.data
    else:
        camera_info = {}
else:
    camera_info = {}
print(f"Current camera settings:")
print(f"  Gain: {camera_info['gain']}")
print(f"  Offset: {camera_info['offset']}")
print(f"  Readout Mode: {camera_info['readout_mode']}")

# Ensure settings are appropriate for calibration
if camera_info['gain'] != 139:
    print("Warning: Gain should be set to 139 for optimal calibration")
if camera_info['offset'] != 21:
    print("Warning: Offset should be set to 21 for optimal calibration")
```

## Troubleshooting

### Common Issues

1. **No Matching Master Frames**
   ```python
   # Check available master frames
   status = video_capture.calibration_applier.get_calibration_status()
   print(f"Available exposure times: {status['available_exposure_times']}")
   print(f"Dark settings: {status['dark_settings']}")
   print(f"Flat settings: {status['flat_settings']}")
   ```

2. **Settings Mismatch**
   ```python
   # Check frame settings vs master frame settings
   frame_details = status.details
   print(f"Frame settings: gain={frame_details['original_gain']}, "
         f"offset={frame_details['original_offset']}, "
         f"readout={frame_details['original_readout_mode']}")
   print(f"Master dark settings: {frame_details['master_dark_settings']}")
   print(f"Master flat settings: {frame_details['master_flat_settings']}")
   ```

3. **Calibration Not Applied**
   ```python
   # Check calibration status
   if not frame_details.get('calibration_applied', False):
       print("Calibration not applied. Possible reasons:")
       print(f"  - No master frames available")
       print(f"  - Settings don't match")
       print(f"  - Calibration disabled")
   ```

### Debug Information

Enable debug logging for detailed calibration information:

```python
import logging
logging.getLogger('calibration_applier').setLevel(logging.DEBUG)
```

This will show:
- Master frame loading details
- Settings matching process
- Frame selection decisions
- Calibration application steps

## Performance Considerations

### 1. Memory Usage
- Master frames are loaded into memory for fast access
- Large master frames may consume significant memory
- Consider reloading master frames periodically for long sessions

### 2. Processing Time
- Settings matching adds minimal overhead
- Calibration application is optimized for speed
- Real-time calibration is possible for most systems

### 3. Storage Requirements
- Master frames include camera settings metadata
- FITS headers store gain, offset, and readout mode information
- Additional storage overhead is minimal

## Future Enhancements

- **Adaptive Tolerance**: Automatic tolerance adjustment based on camera type
- **Settings Interpolation**: Interpolate between master frames with different settings
- **Quality Metrics**: Automatic quality assessment of calibration results
- **Multi-Camera Support**: Support for different camera settings simultaneously
