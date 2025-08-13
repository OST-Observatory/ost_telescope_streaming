# Image Combination Guide

## Overview

The OST Telescope Streaming system now includes functionality to combine astronomical overlays with captured telescope images. This creates annotated images that show both the original telescope view and the astronomical annotations (stars, deep sky objects, etc.).

## Features

### 1. Automatic Image Combination
- **Real-time Processing**: Combines overlays with captured frames automatically
- **Transparency Support**: Overlays are applied with alpha blending for natural appearance
- **Size Matching**: Automatically resizes overlays to match captured image dimensions
- **Quality Preservation**: Maintains high image quality in the output

### 2. File Management
- **Timestamped Files**: Option to include timestamps in filenames
- **Organized Output**: Separate files for overlays and combined images
- **Format Support**: Outputs high-quality PNG images

### 3. Integration
- **Plate-Solving Integration**: Uses plate-solving results for accurate overlay positioning
- **Video Processing**: Integrates with existing video capture system
- **Mount Coordinates**: Can use mount coordinates as fallback

## Usage

### Command Line Interface

```bash
# Basic usage with image combination
python overlay_runner.py --enable-video

# With custom interval and plate-solving
python overlay_runner.py --enable-video --wait-for-plate-solve --interval 60

# With debug logging
python overlay_runner.py --enable-video --debug
```

### Configuration

Add the following to your `config.yaml`:

```yaml
overlay:
  update:
    update_interval: 30  # seconds
    max_retries: 3
    retry_delay: 5
  use_timestamps: true
  timestamp_format: "%Y%m%d_%H%M%S"
  wait_for_plate_solve: true  # Wait for plate-solving before generating overlays

video:
  video_enabled: true  # Enable video processing
  camera_type: "opencv"  # or "ascom"
  opencv:
    frame_width: 1920
    frame_height: 1080
```

## Output Files

The system generates three types of files:

1. **Overlay Files**: `overlay_YYYYMMDD_HHMMSS.png`
   - Pure astronomical overlay with transparency
   - Shows stars, deep sky objects, and annotations

2. **Combined Files**: `combined_YYYYMMDD_HHMMSS.png`
   - Captured telescope image with overlay applied
   - Final annotated image for viewing/analysis

3. **Log Files**: `overlay_runner_YYYYMMDD.log`
   - Detailed logging of all operations

## Technical Details

### Image Processing Pipeline

1. **Frame Capture**: Captures frame from telescope camera
2. **Plate-Solving**: Determines exact coordinates and field of view
3. **Overlay Generation**: Creates astronomical overlay based on coordinates
4. **Image Combination**: Merges overlay with captured frame
5. **File Saving**: Saves combined image with appropriate naming

### Alpha Blending

The system uses alpha blending to combine images:
- Base image: Captured telescope frame
- Overlay: Astronomical annotations with transparency
- Result: Natural-looking annotated image

### Error Handling

- **Missing Files**: Graceful handling of missing overlay or image files
- **Size Mismatches**: Automatic resizing of overlays to match images
- **Processing Errors**: Detailed error logging and recovery

## API Reference

### VideoProcessor Methods

```python
# Combine overlay with captured image
combine_overlay_with_image(image_path, overlay_path, output_path=None)

# Get latest captured frame path
get_latest_frame_path()

# Capture and combine in one operation
capture_and_combine_with_overlay(overlay_path, output_path=None)
```

### OverlayRunner Integration

The `OverlayRunner` class automatically:
- Generates overlays based on coordinates
- Captures frames from video stream
- Combines overlays with captured images
- Saves annotated results

## Troubleshooting

### Common Issues

1. **No Combined Images Generated**
   - Check if video processing is enabled
   - Verify camera configuration
   - Check log files for errors

2. **Overlay Not Aligned**
   - Ensure plate-solving is working correctly
   - Check coordinate accuracy
   - Verify field of view parameters

3. **Poor Image Quality**
   - Check camera resolution settings
   - Verify PNG quality settings
   - Ensure sufficient disk space

### Debug Mode

Enable debug logging for detailed information:

```bash
python overlay_runner.py --debug --enable-video
```

This will show:
- Frame capture details
- Overlay generation parameters
- Image combination steps
- File paths and sizes

## Examples

### Basic Workflow

```python
from code.overlay_runner import OverlayRunner
from code.config_manager import ConfigManager

# Load configuration
config = ConfigManager('config.yaml')

# Create overlay runner
runner = OverlayRunner(config=config)

# Run with image combination
runner.run()
```

### Custom Image Combination

```python
from code.video_processor import VideoProcessor

# Create video processor
processor = VideoProcessor(config=config)

# Combine specific images
result = processor.combine_overlay_with_image(
    'captured_frame.jpg',
    'astronomical_overlay.png',
    'annotated_image.png'
)

if result.is_success:
    print(f"Combined image saved: {result.data}")
else:
    print(f"Error: {result.message}")
```

## Performance Considerations

- **Memory Usage**: Large images may require significant memory
- **Processing Time**: Combination adds ~100-500ms per image
- **Storage**: Combined images are typically 2-5MB each
- **Disk Space**: Monitor available space for long-running sessions

## Future Enhancements

- **Batch Processing**: Process multiple images at once
- **Video Output**: Create annotated video streams
- **Advanced Blending**: Multiple overlay layers
- **Real-time Streaming**: Live annotated video output
