# Master Frames Guide

## Overview

The OST Telescope Streaming system now includes automatic master frame creation functionality. This system processes captured dark and flat frames to create high-quality master calibration frames with proper dark subtraction and normalization.

## Features

### 1. Master Dark Creation
- **Multiple Exposure Times**: Creates master darks for all captured exposure times
- **Rejection Methods**: Sigma clipping or min/max rejection for outlier removal
- **Quality Control**: Validates frame quality and statistics
- **Automatic Organization**: Organizes by exposure time

### 2. Master Flat Creation
- **Dark Subtraction**: Automatically subtracts corresponding master dark
- **Normalization**: Normalizes to mean, median, or maximum value
- **Quality Control**: Ensures proper flat field correction
- **Exposure Matching**: Finds correct master dark for flat exposure time

### 3. Advanced Processing
- **Sigma Clipping**: Removes outliers using statistical methods
- **Min/Max Rejection**: Removes highest and lowest values
- **Multiple Normalization**: Mean, median, or maximum normalization
- **Quality Metrics**: Provides detailed quality statistics

## Quick Start

### 1. Configuration

Create a master frame configuration file:

```yaml
master_frames:
  output_dir: "master_frames"           # Output directory
  rejection_method: "sigma_clip"        # 'sigma_clip' or 'minmax'
  sigma_threshold: 3.0                  # Sigma threshold
  normalization_method: "mean"          # 'mean', 'median', 'max'
  quality_control: true                 # Enable quality control
  save_individual_masters: true         # Save individual masters
  create_master_bias: true              # Create master bias
  create_master_darks: true             # Create master darks
  create_master_flats: true             # Create master flats
```

### 2. Run Master Frame Creation

```bash
# Create all master frames (darks and flats)
python master_frame_runner.py --config config_master_frames.yaml

# Create only master darks
python master_frame_runner.py --config config_master_frames.yaml --darks-only

# Create only master flats
python master_frame_runner.py --config config_master_frames.yaml --flats-only
```

## Configuration Options

### Master Frame Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `output_dir` | "master_frames" | Output directory for master frames |
| `rejection_method` | "sigma_clip" | Frame rejection method |
| `sigma_threshold` | 3.0 | Sigma threshold for rejection |
| `normalization_method` | "mean" | Normalization method for flats |
| `quality_control` | true | Enable quality control |
| `save_individual_masters` | true | Save individual master frames |
| `create_master_bias` | true | Create master bias frame |
| `create_master_darks` | true | Create master dark frames |
| `create_master_flats` | true | Create master flat frames |

### Command Line Options

```bash
python master_frame_runner.py [OPTIONS]

Options:
  --config CONFIG_FILE        Configuration file path
  --darks-only                Create only master darks
  --flats-only                Create only master flats
  --rejection-method METHOD   Frame rejection method
  --sigma-threshold VALUE     Sigma threshold for rejection
  --normalization-method METHOD Normalization method
  --debug                     Enable debug logging
  --log-level LEVEL           Logging level
```

## How It Works

### 1. Master Dark Creation Process

```python
# For each exposure time directory
for exp_dir in exposure_directories:
    exposure_time = extract_exposure_time(exp_dir)
    
    # Load all dark frames for this exposure time
    dark_frames = load_frames_from_directory(exp_dir)
    
    # Apply rejection method
    if rejection_method == 'sigma_clip':
        master_dark = sigma_clip_combine(dark_frames)
    else:
        master_dark = minmax_combine(dark_frames)
    
    # Save master dark
    save_master_dark(master_dark, exposure_time)
```

### 2. Master Flat Creation Process

```python
# Load flat frames
flat_frames = load_flat_frames()

# Determine flat exposure time
flat_exposure_time = determine_exposure_time(flat_frames)

# Find corresponding master dark
master_dark = find_master_dark(flat_exposure_time)

# Dark subtraction for each flat
for flat_frame in flat_frames:
    dark_subtracted = flat_frame - master_dark
    dark_subtracted_flats.append(dark_subtracted)

# Combine dark-subtracted flats
master_flat = combine_frames(dark_subtracted_flats)

# Normalize master flat
master_flat_normalized = normalize_master_flat(master_flat)

# Save master flat
save_master_flat(master_flat_normalized, flat_exposure_time)
```

### 3. Frame Combination Methods

#### Sigma Clipping
```python
def sigma_clip_combine(frames):
    mean = np.mean(frames, axis=0)
    std = np.std(frames, axis=0)
    
    # Create mask for pixels within sigma threshold
    mask = np.abs(frames - mean) <= (sigma_threshold * std)
    
    # Calculate mean of accepted pixels
    combined = np.zeros_like(mean)
    for i, j in pixel_coordinates:
        valid_pixels = frames[mask[:, i, j], i, j]
        if len(valid_pixels) > 0:
            combined[i, j] = np.mean(valid_pixels)
        else:
            combined[i, j] = mean[i, j]
    
    return combined
```

#### Min/Max Rejection
```python
def minmax_combine(frames):
    # Sort along first axis
    sorted_frames = np.sort(frames, axis=0)
    
    # Remove min and max values
    n_frames = sorted_frames.shape[0]
    if n_frames > 2:
        trimmed = sorted_frames[1:-1, :, :]
        return np.mean(trimmed, axis=0)
    else:
        return np.mean(sorted_frames, axis=0)
```

### 4. Normalization Methods

#### Mean Normalization
```python
def normalize_mean(master_flat):
    norm_factor = np.mean(master_flat)
    return master_flat / norm_factor
```

#### Median Normalization
```python
def normalize_median(master_flat):
    norm_factor = np.median(master_flat)
    return master_flat / norm_factor
```

#### Maximum Normalization
```python
def normalize_max(master_flat):
    norm_factor = np.max(master_flat)
    return master_flat / norm_factor
```

## Examples

### Complete Master Frame Creation

```bash
# Create all master frames
python master_frame_runner.py --config config_master_frames.yaml
```

### Master Darks Only

```bash
# Create only master darks
python master_frame_runner.py \
  --config config_master_frames.yaml \
  --darks-only
```

### Master Flats Only

```bash
# Create only master flats
python master_frame_runner.py \
  --config config_master_frames.yaml \
  --flats-only
```

### Custom Rejection Method

```bash
# Use min/max rejection instead of sigma clipping
python master_frame_runner.py \
  --config config_master_frames.yaml \
  --rejection-method minmax
```

### Custom Sigma Threshold

```bash
# Use custom sigma threshold
python master_frame_runner.py \
  --config config_master_frames.yaml \
  --sigma-threshold 2.5
```

### Custom Normalization

```bash
# Use median normalization for master flats
python master_frame_runner.py \
  --config config_master_frames.yaml \
  --normalization-method median
```

### Debug Mode

```bash
# Enable debug logging
python master_frame_runner.py \
  --config config_master_frames.yaml \
  --debug
```

## Output

### File Structure

```
master_frames/
├── master_bias_20250729_143022.fits      # Master bias frame
├── master_dark_0.500s_20250729_143022.fits  # 0.5x science exposure
├── master_dark_1.000s_20250729_143022.fits  # Flat exposure time
├── master_dark_2.000s_20250729_143022.fits  # Science exposure time
├── master_dark_5.000s_20250729_143022.fits  # Science exposure time
├── master_dark_10.000s_20250729_143022.fits # 2x science exposure
├── master_dark_20.000s_20250729_143022.fits # 4x science exposure
└── master_flat_1.000s_20250729_143022.fits  # Master flat frame
```

### Log Files

- **Console Output**: Real-time progress and status
- **Log File**: `master_frames_YYYYMMDD.log` with detailed information

### Status Information

The system provides detailed status information including:
- Number of master darks created
- Number of master flats created
- Exposure times processed
- Quality metrics and statistics
- Output file paths

## Quality Control

### 1. Frame Validation

- **File Integrity**: Check if all input files are valid
- **Frame Dimensions**: Ensure consistent frame sizes
- **Data Range**: Validate pixel value ranges
- **Statistics**: Calculate mean, std dev, min, max

### 2. Rejection Quality

- **Sigma Clipping**: Remove statistical outliers
- **Min/Max Rejection**: Remove extreme values
- **Frame Count**: Ensure sufficient frames remain
- **Consistency**: Check for systematic issues

### 3. Master Frame Quality

- **Signal-to-Noise**: Calculate S/N ratios
- **Uniformity**: Check for systematic patterns
- **Artifacts**: Detect and flag artifacts
- **Statistics**: Provide quality metrics

## Best Practices

### 1. Input Data Quality

- **Sufficient Frames**: Use at least 20-40 frames per master
- **Consistent Conditions**: Maintain stable temperature
- **Proper Exposure**: Use appropriate exposure times
- **No Light Leaks**: Ensure complete darkness for darks

### 2. Processing Settings

- **Rejection Method**: Use sigma clipping for most cases
- **Sigma Threshold**: 3.0 is usually appropriate
- **Normalization**: Mean normalization works well for most flats
- **Quality Control**: Always enable quality control

### 3. Validation

- **Check Histograms**: Review master frame histograms
- **Compare Statistics**: Compare with expected values
- **Test Calibration**: Apply to test images
- **Monitor Quality**: Track quality metrics over time

## Use Cases

### 1. Deep Sky Imaging

- **Long Exposure Darks**: Match science exposure times
- **Extended Range**: Handle exposure adjustments
- **High Quality**: Use sigma clipping for best results

### 2. Planetary Imaging

- **Bias Frames**: Essential for short exposures
- **Quick Processing**: Use min/max rejection for speed
- **Multiple Sessions**: Create masters per session

### 3. Solar System Imaging

- **Specific Exposures**: Match target exposure times
- **Quality Focus**: Use high-quality rejection methods
- **Consistent Calibration**: Maintain calibration quality

## Troubleshooting

### Common Issues

1. **No Input Files Found**
   - Check input directories exist
   - Verify file extensions (.fits, .fit)
   - Ensure proper file naming

2. **Exposure Time Mismatch**
   - Check flat exposure time detection
   - Verify master dark availability
   - Review exposure time extraction

3. **Poor Quality Masters**
   - Increase number of input frames
   - Adjust rejection parameters
   - Check input frame quality

4. **Processing Errors**
   - Verify file permissions
   - Check disk space
   - Review error logs

### Debug Information

Enable debug logging to get detailed information:

```bash
python master_frame_runner.py --config config_master_frames.yaml --debug
```

This will show:
- File loading details
- Processing statistics
- Quality metrics
- Error details and diagnostics

## Integration

### With Main System

The master frame creator can be integrated with the main system:

```python
from master_frame_creator import MasterFrameCreator

# Initialize master frame creator
master_creator = MasterFrameCreator(config=config)

# Create all master frames
result = master_creator.create_all_master_frames()
```

### With Calibration Pipeline

Master frames are used in the calibration pipeline:

```python
# Apply calibration to science images
calibrated_image = (science_image - master_dark) / master_flat
```

### Future Enhancements

- **Automatic Quality Assessment**: Advanced quality metrics
- **Temperature Tracking**: Temperature-dependent masters
- **Real-time Processing**: Live master frame updates
- **Advanced Rejection**: More sophisticated rejection methods
- **Calibration Pipeline**: Automated calibration workflow

## API Reference

### MasterFrameCreator Class

```python
class MasterFrameCreator:
    def __init__(self, config=None, logger=None)
    def create_all_master_frames(self) -> Status
    def create_master_darks(self) -> Status
    def create_master_flats(self) -> Status
    def get_status(self) -> Dict[str, Any]
```

### Key Methods

- **`create_all_master_frames()`**: Create all master frames
- **`create_master_darks()`**: Create only master darks
- **`create_master_flats()`**: Create only master flats
- **`get_status()`**: Get system status

### Status Objects

All methods return Status objects with:
- **Success/Error**: Operation result
- **Data**: Created file lists or error details
- **Details**: Additional information and statistics 