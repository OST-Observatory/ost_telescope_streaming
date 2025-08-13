# Dark Capture Guide

## Overview

The OST Telescope Streaming system now includes automatic dark frame capture functionality. This system captures dark frames for multiple exposure times to provide comprehensive calibration data for different observation scenarios.

## Features

### 1. Multiple Exposure Times
- **Bias Frames**: Minimum exposure time (typically 1ms)
- **Flat Darks**: Same exposure time as flat frames
- **Science Darks**: Same exposure time as science images
- **Extended Range**: 0.5x, 2x, 4x science exposure time

### 2. Automatic Detection
- **Flat Exposure Detection**: Automatically detects flat exposure time
- **Smart Organization**: Organizes darks by exposure time
- **Quality Control**: Validates captured frames

### 3. Flexible Capture Modes
- **Complete Capture**: All exposure times
- **Bias Only**: Only bias frames
- **Science Only**: Only science exposure time
- **Custom Ranges**: Configurable exposure factors

## Quick Start

### 1. Configuration

Create a dark capture configuration file:

```yaml
dark_capture:
  num_darks: 20                    # Darks per exposure time
  flat_exposure_time: null         # Auto-detected from flats
  science_exposure_time: 1.0       # Science image exposure
  min_exposure: 0.001              # 1ms for bias frames
  max_exposure: 60.0               # 60s maximum
  exposure_factors: [0.5, 1.0, 2.0, 4.0]  # Extended range
  output_dir: "darks"              # Output directory
```

### 2. Run Dark Capture

```bash
# Complete dark capture (all exposure times)
python calibration/dark_capture_runner.py --config config_dark_capture.yaml

# Bias frames only
python calibration/dark_capture_runner.py --config config_dark_capture.yaml --bias-only

# Science darks only
python calibration/dark_capture_runner.py --config config_dark_capture.yaml --science-only
```

## Configuration Options

### Dark Capture Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_darks` | 20 | Number of dark frames per exposure time |
| `flat_exposure_time` | None | Flat exposure time (auto-detected) |
| `science_exposure_time` | 1.0 | Science image exposure time |
| `min_exposure` | 0.001 | Minimum exposure time for bias frames |
| `max_exposure` | 60.0 | Maximum exposure time |
| `exposure_factors` | [0.5, 1.0, 2.0, 4.0] | Factors for extended range |
| `output_dir` | "darks" | Output directory for dark frames |

### Command Line Options

```bash
python calibration/dark_capture_runner.py [OPTIONS]

Options:
  --config CONFIG_FILE        Configuration file path
  --num-darks COUNT           Number of dark frames per exposure
  --science-exposure-time SEC Science exposure time in seconds
  --bias-only                 Capture only bias frames
  --science-only              Capture only science darks
  --debug                     Enable debug logging
  --log-level LEVEL           Logging level
```

## How It Works

### 1. Exposure Time Calculation

The system calculates all required exposure times:

```python
exposure_times = [
    min_exposure,                    # Bias frames (1ms)
    flat_exposure_time,              # Flat darks (auto-detected)
    science_exposure_time * 0.5,     # 0.5x science exposure
    science_exposure_time * 1.0,     # Science exposure
    science_exposure_time * 2.0,     # 2x science exposure
    science_exposure_time * 4.0      # 4x science exposure
]
```

### 2. Dark Capture Process

1. **Setup**: Initialize camera and dark capture system
2. **Detection**: Auto-detect flat exposure time from existing flats
3. **Calculation**: Calculate all required exposure times
4. **Capture**: Take darks for each exposure time
5. **Organization**: Save darks in exposure-specific subdirectories
6. **Validation**: Ensure all frames are captured successfully

### 3. File Organization

```
darks/
├── exp_0.001s/           # Bias frames
│   ├── bias_20250729_143022_001.fits
│   ├── bias_20250729_143022_002.fits
│   └── ...
├── exp_1.000s/           # Flat darks
│   ├── dark_20250729_143022_001.fits
│   ├── dark_20250729_143022_002.fits
│   └── ...
├── exp_0.500s/           # 0.5x science exposure
├── exp_1.000s/           # Science exposure
├── exp_2.000s/           # 2x science exposure
└── exp_4.000s/           # 4x science exposure
```

## Examples

### Complete Dark Capture

```bash
# Capture darks for all exposure times
python calibration/dark_capture_runner.py --config config_dark_capture.yaml
```

### Bias Frames Only

```bash
# Capture only bias frames (1ms exposure)
python calibration/dark_capture_runner.py \
  --config config_dark_capture.yaml \
  --bias-only
```

### Science Darks Only

```bash
# Capture only science exposure darks
python calibration/dark_capture_runner.py \
  --config config_dark_capture.yaml \
  --science-only
```

### Custom Settings

```bash
# Custom number of darks and science exposure time
python calibration/dark_capture_runner.py \
  --config config_dark_capture.yaml \
  --num-darks 30 \
  --science-exposure-time 2.0
```

### Debug Mode

```bash
# Enable debug logging for troubleshooting
python calibration/dark_capture_runner.py \
  --config config_dark_capture.yaml \
  --debug
```

## Output

### File Structure

```
darks/
├── exp_0.001s/           # Bias frames (1ms)
├── exp_1.000s/           # Flat darks (1s)
├── exp_0.500s/           # 0.5x science exposure
├── exp_1.000s/           # Science exposure
├── exp_2.000s/           # 2x science exposure
└── exp_4.000s/           # 4x science exposure
```

### Log Files

- **Console Output**: Real-time progress and status
- **Log File**: `dark_capture_YYYYMMDD.log` with detailed information

### Status Information

The system provides detailed status information including:
- Total frames captured
- Exposure times used
- Output directories
- Capture success/failure details

## Best Practices

### 1. Camera Preparation

- **Cover Camera**: Ensure no light can enter the camera
- **Stable Temperature**: Maintain consistent camera temperature
- **Same Settings**: Use same gain/offset as science images
- **Dark Environment**: Perform in complete darkness

### 2. Exposure Time Planning

- **Bias Frames**: Always capture (1ms exposure)
- **Flat Darks**: Match flat frame exposure time
- **Science Darks**: Match planned science exposure
- **Extended Range**: Plan for exposure adjustments

### 3. Quality Control

- **Check Histograms**: Ensure no light contamination
- **Monitor Temperature**: Maintain consistent conditions
- **Review Frames**: Check for artifacts or problems
- **Validate Organization**: Ensure proper file structure

## Use Cases

### 1. Deep Sky Imaging

- **Science Darks**: Match long exposure times
- **Extended Range**: Handle exposure adjustments
- **Multiple Sessions**: Capture darks for each session

### 2. Planetary Imaging

- **Bias Frames**: Essential for short exposures
- **Science Darks**: Match planetary exposure times
- **High Frame Rates**: Support for rapid capture

### 3. Solar System Imaging

- **Moon Darks**: Match lunar exposure times
- **Planet Darks**: Match planetary exposure times
- **Comet Darks**: Match comet exposure times

## Troubleshooting

### Common Issues

1. **Light Contamination**
   - Check camera cover
   - Verify dark environment
   - Review frame histograms

2. **Temperature Variations**
   - Maintain stable temperature
   - Allow camera to stabilize
   - Monitor temperature during capture

3. **File Organization Issues**
   - Check output directory permissions
   - Verify exposure time detection
   - Review file naming conventions

4. **Camera Connection Issues**
   - Verify ASCOM driver installation
   - Check camera permissions
   - Restart camera if needed

### Debug Information

Enable debug logging to get detailed information:

```bash
python calibration/dark_capture_runner.py --config config_dark_capture.yaml --debug
```

This will show:
- Exposure time calculations
- File organization details
- Capture progress information
- Error details and diagnostics

## Integration

### With Main System

The dark capture system can be integrated with the main overlay runner:

```python
from code.calibration.dark_capture import DarkCapture
from capture.controller import VideoCapture

# Initialize components
video_capture = VideoCapture(config=config)
dark_capture = DarkCapture(config=config)

# Capture darks
result = dark_capture.capture_darks()
```

### With Flat Capture

Dark capture works seamlessly with flat capture:

1. **Capture Flats**: Use flat capture system
2. **Auto-Detect**: Dark capture detects flat exposure time
3. **Capture Flat Darks**: Automatically capture matching darks
4. **Complete Calibration**: Full calibration dataset

### Future Enhancements

- **Master Dark Creation**: Automatic master dark generation
- **Temperature Tracking**: Temperature-dependent dark capture
- **Quality Assessment**: Advanced quality metrics
- **Integration**: Seamless integration with main system
- **Calibration Pipeline**: Automated calibration workflow

## API Reference

### DarkCapture Class

```python
class DarkCapture:
    def __init__(self, config=None, logger=None)
    def initialize(self, video_capture: VideoCapture) -> bool
    def capture_darks(self) -> Status
    def capture_bias_only(self) -> Status
    def capture_science_darks_only(self) -> Status
    def get_status(self) -> Dict[str, Any]
```

### Key Methods

- **`initialize()`**: Initialize with video capture
- **`capture_darks()`**: Capture darks for all exposure times
- **`capture_bias_only()`**: Capture only bias frames
- **`capture_science_darks_only()`**: Capture only science darks
- **`get_status()`**: Get system status

### Status Objects

All methods return Status objects with:
- **Success/Error**: Operation result
- **Data**: Captured file lists or error details
- **Details**: Additional information and statistics 