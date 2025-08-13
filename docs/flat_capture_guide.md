# Flat Capture Guide

## Overview

The OST Telescope Streaming system now includes automatic flat field capture functionality. This system automatically adjusts exposure time to achieve target count rates and captures a series of flat field images for calibration.

## Features

### 1. Automatic Exposure Adjustment
- **Target Count Rate**: Configurable target (default: 50% of maximum)
- **Tolerance Control**: Configurable tolerance (default: 10%)
- **Smart Adjustment**: Automatic exposure time optimization
- **Range Limits**: Configurable min/max exposure times

### 2. Quality Control
- **Frame Analysis**: Automatic count rate calculation
- **Validation**: Ensures flats meet quality criteria
- **Error Handling**: Robust error recovery and reporting
- **Logging**: Detailed logging of all operations

### 3. Configuration
- **Flexible Settings**: All parameters configurable
- **Command Line Override**: Override config via command line
- **Multiple Formats**: Support for different camera types

## Quick Start

### 1. Configuration

Create a flat capture configuration file:

```yaml
flat_capture:
  target_count_rate: 0.5      # 50% of maximum count
  count_tolerance: 0.1        # 10% tolerance
  num_flats: 40               # Number of flat frames
  min_exposure: 0.001         # 1ms minimum
  max_exposure: 10.0          # 10s maximum
  exposure_step_factor: 1.5   # Adjustment factor
  max_adjustment_attempts: 10 # Max attempts
  output_dir: "flats"         # Output directory
```

### 2. Run Flat Capture

```bash
# Basic usage
python calibration/flat_capture_runner.py --config config_flat_capture.yaml

# Custom number of flats
python calibration/flat_capture_runner.py --config config_flat_capture.yaml --num-flats 50

# Custom target count rate
python calibration/flat_capture_runner.py --config config_flat_capture.yaml --target-count-rate 0.6
```

## Configuration Options

### Flat Capture Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `target_count_rate` | 0.5 | Target count rate as fraction of maximum |
| `count_tolerance` | 0.1 | Tolerance for count rate adjustment |
| `num_flats` | 40 | Number of flat frames to capture |
| `min_exposure` | 0.001 | Minimum exposure time (seconds) |
| `max_exposure` | 10.0 | Maximum exposure time (seconds) |
| `exposure_step_factor` | 1.5 | Factor for exposure adjustment |
| `max_adjustment_attempts` | 10 | Maximum attempts to adjust exposure |
| `output_dir` | "flats" | Output directory for flat frames |

### Command Line Options

```bash
python calibration/flat_capture_runner.py [OPTIONS]

Options:
  --config CONFIG_FILE        Configuration file path
  --num-flats COUNT           Number of flat frames to capture
  --target-count-rate RATE    Target count rate (0.0-1.0)
  --tolerance TOLERANCE       Count rate tolerance (0.0-1.0)
  --debug                     Enable debug logging
  --log-level LEVEL           Logging level
```

## How It Works

### 1. Exposure Adjustment Process

1. **Initial Capture**: Capture test frame with current exposure
2. **Analysis**: Calculate mean count rate and statistics
3. **Comparison**: Compare with target count rate
4. **Adjustment**: Increase/decrease exposure based on difference
5. **Validation**: Check if within tolerance
6. **Iteration**: Repeat until target achieved or max attempts reached

### 2. Flat Capture Process

1. **Setup**: Initialize camera and flat capture system
2. **Adjustment**: Optimize exposure for target count rate
3. **Capture**: Take specified number of flat frames
4. **Validation**: Ensure all frames meet quality criteria
5. **Output**: Save frames to specified directory

### 3. Quality Control

- **Count Rate Validation**: Ensures frames are within target range
- **Statistics Calculation**: Mean, std, min, max values
- **Bit Depth Detection**: Automatic detection of image bit depth
- **Error Handling**: Graceful handling of capture failures

## Examples

### Basic Flat Capture

```bash
# Use default settings
python calibration/flat_capture_runner.py --config config_flat_capture.yaml
```

### Custom Settings

```bash
# Capture 50 flats with 60% target count rate
python calibration/flat_capture_runner.py \
  --config config_flat_capture.yaml \
  --num-flats 50 \
  --target-count-rate 0.6 \
  --tolerance 0.15
```

### Debug Mode

```bash
# Enable debug logging for troubleshooting
python calibration/flat_capture_runner.py \
  --config config_flat_capture.yaml \
  --debug
```

## Output

### File Structure

```
flats/
├── flat_20250729_143022_001.fits
├── flat_20250729_143022_002.fits
├── flat_20250729_143022_003.fits
└── ...
```

### Log Files

- **Console Output**: Real-time progress and status
- **Log File**: `flat_capture_YYYYMMDD.log` with detailed information

### Status Information

The system provides detailed status information including:
- Number of frames captured
- Final exposure time
- Target count rate achieved
- Output directory
- Quality statistics

## Best Practices

### 1. Light Source Preparation

- **Twilight Sky**: Use evening/morning twilight for natural flats
- **Light Box**: Use uniform light box for controlled conditions
- **Avoid Stars**: Ensure no stars are visible in the field
- **Uniform Illumination**: Check for vignetting or gradients

### 2. Camera Settings

- **Gain**: Use same gain as science images
- **Offset**: Use same offset as science images
- **Temperature**: Maintain consistent temperature
- **Filter**: Use same filter as science images

### 3. Quality Control

- **Check Histograms**: Ensure no saturation
- **Monitor Count Rate**: Verify target count rate achieved
- **Review Frames**: Check for artifacts or problems
- **Validate Output**: Ensure all frames are usable

## Troubleshooting

### Common Issues

1. **Cannot Achieve Target Count Rate**
   - Check light source brightness
   - Adjust exposure range limits
   - Verify camera settings

2. **Exposure Time Too Long/Short**
   - Adjust min/max exposure settings
   - Check light source intensity
   - Verify camera sensitivity

3. **Poor Quality Flats**
   - Check for non-uniform illumination
   - Verify no stars in field
   - Ensure proper focus

4. **Camera Connection Issues**
   - Verify ASCOM driver installation
   - Check camera permissions
   - Restart camera if needed

### Debug Information

Enable debug logging to get detailed information:

```bash
python calibration/flat_capture_runner.py --config config_flat_capture.yaml --debug
```

This will show:
- Frame analysis details
- Exposure adjustment steps
- Count rate calculations
- Quality validation results

## Integration

### With Main System

The flat capture system can be integrated with the main overlay runner:

```python
from code.calibration.flat_capture import FlatCapture
from capture.controller import VideoCapture

# Initialize components
video_capture = VideoCapture(config=config)
flat_capture = FlatCapture(config=config)

# Capture flats
result = flat_capture.capture_flats()
```

### Future Enhancements

- **Dark Frame Capture**: Automatic dark frame acquisition
- **Bias Frame Capture**: Automatic bias frame acquisition
- **Master Frame Creation**: Automatic master flat creation
- **Quality Assessment**: Advanced quality metrics
- **Integration**: Seamless integration with main system

## API Reference

### FlatCapture Class

```python
class FlatCapture:
    def __init__(self, config=None, logger=None)
    def initialize(self, video_capture: VideoCapture) -> bool
    def capture_flats(self) -> Status
    def get_status(self) -> Dict[str, Any]
```

### Key Methods

- **`initialize()`**: Initialize with video capture
- **`capture_flats()`**: Capture flat field series
- **`get_status()`**: Get system status

### Status Objects

All methods return Status objects with:
- **Success/Error**: Operation result
- **Data**: Captured file list or error details
- **Details**: Additional information and statistics 