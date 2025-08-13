# Calibration Workflow Guide

## Overview

The OST Telescope Streaming system now includes a unified calibration workflow that combines dark capture, flat capture, and master frame creation into a single, streamlined process. All calibration operations use one configuration file for consistency and simplicity.

## Features

### 1. Unified Configuration
- **Single Config File**: All settings in `config_calibration_frames.yaml`
- **Consistent Settings**: Shared video configuration across all operations
- **Clear Documentation**: Inline comments and workflow examples
- **Modular Design**: Can run individual steps or complete workflow

### 2. Complete Workflow
- **Step 1**: Dark frame capture (bias, science, extended range)
- **Step 2**: Flat frame capture (with automatic exposure optimization)
- **Step 3**: Master frame creation (with dark subtraction and normalization)

### 3. Flexible Execution
- **Complete Workflow**: Run all steps in sequence
- **Individual Steps**: Run specific calibration steps
- **Batch Mode**: Skip confirmation prompts for automation
- **Debug Mode**: Detailed logging for troubleshooting

## Quick Start

### 1. Configuration

Use the unified configuration file:

```yaml
# config_calibration_frames.yaml
dark_capture:
  num_darks: 40
  science_exposure_time: 5.0
  exposure_factors: [0.5, 1.0, 2.0, 4.0]
  output_dir: "darks"

flat_capture:
  target_count_rate: 0.5
  num_flats: 40
  output_dir: "flats"

master_frames:
  rejection_method: "sigma_clip"
  normalization_method: "mean"
  output_dir: "master_frames"

video:
  camera_type: "ascom"
  ascom:
    camera_name: "QHY600M"
    exposure_time: 5.0
```

### 2. Run Complete Workflow

```bash
# Complete calibration workflow
python calibration/calibration_workflow.py --config config_calibration_frames.yaml
```

### 3. Run Individual Steps

```bash
# Dark capture only
python calibration/calibration_workflow.py --config config_calibration_frames.yaml --step darks

# Flat capture only
python calibration/calibration_workflow.py --config config_calibration_frames.yaml --step flats

# Master frame creation only
python calibration/calibration_workflow.py --config config_calibration_frames.yaml --step masters
```

## Configuration Options

### Dark Capture Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_darks` | 40 | Number of dark frames per exposure time |
| `flat_exposure_time` | null | Flat exposure time (auto-detected) |
| `science_exposure_time` | 5.0 | Science image exposure time |
| `min_exposure` | 0.001 | Minimum exposure time for bias frames |
| `max_exposure` | 60.0 | Maximum exposure time |
| `exposure_factors` | [0.5, 1.0, 2.0, 4.0] | Factors for extended range |
| `output_dir` | "darks" | Output directory for dark frames |

### Flat Capture Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `target_count_rate` | 0.5 | Target count rate (50% of max) |
| `count_tolerance` | 0.1 | Tolerance for count rate |
| `num_flats` | 40 | Number of flat frames |
| `min_exposure` | 0.001 | Minimum exposure time |
| `max_exposure` | 10.0 | Maximum exposure time |
| `exposure_step_factor` | 1.5 | Exposure adjustment factor |
| `max_adjustment_attempts` | 10 | Maximum adjustment attempts |
| `output_dir` | "flats" | Output directory for flat frames |

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
python calibration_workflow.py [OPTIONS]

Options:
  --config CONFIG_FILE        Configuration file path
  --step STEP                 Calibration step (darks/flats/masters/all)
  --no-confirm                Skip confirmation prompts
  --debug                     Enable debug logging
  --log-level LEVEL           Logging level
```

## Workflow Examples

### Complete Calibration Workflow

```bash
# Run complete workflow with confirmations
python calibration_workflow.py --config config_calibration_frames.yaml
```

This will:
1. **Capture Darks**: Bias frames, science darks, extended range darks
2. **Capture Flats**: Auto-optimized exposure for 50% count rate
3. **Create Masters**: Master bias, darks, and flats with dark subtraction

### Individual Steps

```bash
# Step 1: Dark capture only
python calibration_workflow.py --config config_calibration_frames.yaml --step darks

# Step 2: Flat capture only
python calibration_workflow.py --config config_calibration_frames.yaml --step flats

# Step 3: Master frame creation only
python calibration_workflow.py --config config_calibration_frames.yaml --step masters
```

### Batch Mode (No Confirmations)

```bash
# Run complete workflow without confirmations
python calibration/calibration_workflow.py \
  --config config_calibration_frames.yaml \
  --no-confirm
```

### Debug Mode

```bash
# Enable debug logging
python calibration/calibration_workflow.py \
  --config config_calibration_frames.yaml \
  --debug
```

## Workflow Process

### Step 1: Dark Frame Capture

```python
# Initialize dark capture
dark_capture = DarkCapture(config=config)
dark_capture.initialize(video_capture)

# Capture darks for all exposure times
result = dark_capture.capture_darks()

# Exposure times captured:
# - 0.001s (bias frames)
# - 1.000s (flat exposure - auto-detected)
# - 2.500s (0.5x science exposure)
# - 5.000s (science exposure)
# - 10.000s (2x science exposure)
# - 20.000s (4x science exposure)
```

### Step 2: Flat Frame Capture

```python
# Initialize flat capture
flat_capture = FlatCapture(config=config)
flat_capture.initialize(video_capture)

# Capture flats with auto-optimized exposure
result = flat_capture.capture_flats()

# Process:
# 1. Take test frames to measure count rate
# 2. Adjust exposure time to achieve 50% count rate
# 3. Capture 40 flat frames with optimized exposure
# 4. Save to 'flats' directory
```

### Step 3: Master Frame Creation

```python
# Initialize master frame creator
master_creator = MasterFrameCreator(config=config)

# Create all master frames
result = master_creator.create_all_master_frames()

# Process:
# 1. Create master bias from bias frames
# 2. Create master darks for each exposure time
# 3. Create master flats with dark subtraction
# 4. Apply normalization to master flats
# 5. Save to 'master_frames' directory
```

## Output Structure

### Directory Organization

```
project_root/
├── config_calibration_frames.yaml    # Unified configuration
├── calibration/calibration_workflow.py           # Main workflow script
├── darks/                            # Dark frame output
│   ├── exp_0.001s/                   # Bias frames (1ms)
│   ├── exp_1.000s/                   # Flat darks (1s)
│   ├── exp_2.500s/                   # 0.5x science (2.5s)
│   ├── exp_5.000s/                   # Science (5s)
│   ├── exp_10.000s/                  # 2x science (10s)
│   └── exp_20.000s/                  # 4x science (20s)
├── flats/                            # Flat frame output
│   ├── flat_20250729_143022_001.fits
│   ├── flat_20250729_143022_002.fits
│   └── ... (40 flat frames)
└── master_frames/                    # Master frame output
    ├── master_bias_20250729_143022.fits
    ├── master_dark_0.001s_20250729_143022.fits
    ├── master_dark_1.000s_20250729_143022.fits
    ├── master_dark_2.500s_20250729_143022.fits
    ├── master_dark_5.000s_20250729_143022.fits
    ├── master_dark_10.000s_20250729_143022.fits
    ├── master_dark_20.000s_20250729_143022.fits
    └── master_flat_1.000s_20250729_143022.fits
```

### File Naming Convention

- **Dark Frames**: `dark_YYYYMMDD_HHMMSS_NNN.fits`
- **Bias Frames**: `bias_YYYYMMDD_HHMMSS_NNN.fits`
- **Flat Frames**: `flat_YYYYMMDD_HHMMSS_NNN.fits`
- **Master Darks**: `master_dark_EXPOSUREs_YYYYMMDD_HHMMSS.fits`
- **Master Bias**: `master_bias_YYYYMMDD_HHMMSS.fits`
- **Master Flats**: `master_flat_EXPOSUREs_YYYYMMDD_HHMMSS.fits`

## Quality Control

### 1. Dark Frame Quality

- **Bias Frames**: Check for read noise characteristics
- **Dark Frames**: Verify thermal noise patterns
- **Consistency**: Ensure stable temperature during capture
- **Statistics**: Monitor mean, std dev, min, max values

### 2. Flat Frame Quality

- **Count Rate**: Verify 50% ± 10% of maximum counts
- **Uniformity**: Check for vignetting and dust shadows
- **Exposure Optimization**: Confirm automatic adjustment worked
- **Statistics**: Monitor frame-to-frame consistency

### 3. Master Frame Quality

- **Rejection Quality**: Verify outlier removal effectiveness
- **Dark Subtraction**: Check for proper dark subtraction
- **Normalization**: Ensure proper flat field normalization
- **Artifacts**: Detect and flag any artifacts

## Best Practices

### 1. Preparation

- **Camera Cover**: Ensure complete darkness for darks
- **Light Source**: Set up uniform light source for flats
- **Temperature**: Maintain stable camera temperature
- **Settings**: Use same gain/offset as science images

### 2. Execution

- **Complete Workflow**: Run full workflow for consistency
- **Quality Check**: Verify each step before proceeding
- **Backup**: Keep original calibration frames
- **Documentation**: Record conditions and settings

### 3. Validation

- **Histogram Analysis**: Review frame histograms
- **Statistics Comparison**: Compare with expected values
- **Test Calibration**: Apply to test images
- **Quality Metrics**: Monitor quality over time

## Troubleshooting

### Common Issues

1. **Configuration Errors**
   - Check YAML syntax
   - Verify file paths exist
   - Ensure camera settings are correct

2. **Camera Connection Issues**
   - Verify ASCOM driver installation
   - Check camera permissions
   - Restart camera if needed

3. **Quality Issues**
   - Check for light leaks during dark capture
   - Verify flat light source uniformity
   - Monitor temperature stability

4. **Processing Errors**
   - Check disk space
   - Verify file permissions
   - Review error logs

### Debug Information

Enable debug logging for detailed information:

```bash
python calibration/calibration_workflow.py --config config_calibration_frames.yaml --debug
```

This will show:
- Configuration loading details
- Camera initialization steps
- Frame capture progress
- Processing statistics
- Error details and diagnostics

## Integration

### With Main System

The calibration workflow integrates with the main system:

```python
# Apply calibration to science images
from calibration.master_frame_builder import MasterFrameCreator

# Load master frames
master_creator = MasterFrameCreator(config=config)
master_dark = load_master_dark(exposure_time)
master_flat = load_master_flat()

# Apply calibration
calibrated_image = (science_image - master_dark) / master_flat
```

### With Existing Scripts

Individual scripts still work with the unified config:

```bash
# Dark capture with unified config
python calibration/dark_capture_runner.py --config config_calibration_frames.yaml

# Flat capture with unified config
python calibration/flat_capture_runner.py --config config_calibration_frames.yaml

# Master frame creation with unified config
python calibration/master_frame_runner.py --config config_calibration_frames.yaml
```

## Benefits

### 1. Simplified Management
- **Single Config File**: All settings in one place
- **Consistent Settings**: Shared configuration across operations
- **Clear Documentation**: Inline comments and examples
- **Easy Maintenance**: Update settings in one location

### 2. Streamlined Workflow
- **Complete Process**: Run entire calibration in one command
- **Individual Steps**: Run specific steps as needed
- **Batch Mode**: Automated execution without prompts
- **Progress Tracking**: Clear step-by-step progress

### 3. Quality Assurance
- **Consistent Settings**: Same configuration across all steps
- **Quality Control**: Built-in validation at each step
- **Error Handling**: Comprehensive error checking
- **Logging**: Detailed logs for troubleshooting

### 4. Flexibility
- **Modular Design**: Run individual steps or complete workflow
- **Customizable**: Easy to modify settings for different needs
- **Extensible**: Easy to add new calibration steps
- **Compatible**: Works with existing individual scripts

## Future Enhancements

- **Temperature Tracking**: Temperature-dependent calibration
- **Real-time Monitoring**: Live quality metrics during capture
- **Advanced Quality Control**: More sophisticated quality assessment
- **Automated Scheduling**: Automatic calibration at regular intervals
- **Integration**: Seamless integration with main observation system 