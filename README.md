# OST Telescope Streaming System

A comprehensive astronomical telescope streaming and overlay system with plate-solving capabilities.

## Features

- **Real-time Video Capture**: Support for ASCOM cameras and OpenCV
- **Plate-Solving**: Automated coordinate determination using PlateSolve2
- **Astronomical Overlays**: Generate overlays showing stars, deep sky objects, and annotations
- **Information Panel**: Display camera/telescope parameters and field of view information
- **Configurable Title**: Customizable header text for overlays
- **Secondary FOV Overlay**: Display field of view of a second telescope (camera or eyepiece)
- **Image Combination**: Combine overlays with captured telescope images
- **Mount Integration**: ASCOM mount support for coordinate tracking
- **Camera Cooling**: Advanced cooling management with thermal shock prevention
- **Configurable**: Flexible configuration system for all components

## Quick Start

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Configuration

Copy and modify the example configuration:

```bash
cp config.yaml my_config.yaml
# Edit my_config.yaml with your settings
```

### 3. Run the Overlay Runner

```bash
# Basic usage
python overlay_pipeline.py

# With frame processing and image combination
python overlay_pipeline.py --enable-frame-processing --wait-for-plate-solve

# With custom interval and debug logging
python overlay_pipeline.py --enable-frame-processing --interval 60 --debug

# With cooling enabled (status monitoring is automatic)
python overlay_pipeline.py --enable-cooling --cooling-temp -10.0
```

## Command Line Options

```bash
python overlay_pipeline.py [OPTIONS]

Options:
  --config, -c CONFIG_FILE    Configuration file path (default: config.yaml)
  --interval, -i SECONDS      Update interval in seconds (default: 30)
  --debug, -d                 Enable debug logging
  --wait-for-plate-solve      Wait for plate-solving results before generating overlays
  --enable-frame-processing   Enable frame processing and image capture
  --log-level LEVEL           Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

## Examples

### Basic Overlay Generation
```bash
python overlay_pipeline.py --config my_config.yaml
```

### Full System with Image Combination
```bash
python overlay_pipeline.py --enable-frame-processing --wait-for-plate-solve --interval 60
```

### Debug Mode
```bash
python overlay_pipeline.py --enable-frame-processing --debug
```

## Output Files

The system generates several types of files:

- **Overlay Files**: `overlay_YYYYMMDD_HHMMSS.png` - Pure astronomical overlays
- **Combined Files**: `combined_YYYYMMDD_HHMMSS.png` - Captured images with overlays
- **Log Files**: `overlay_runner_YYYYMMDD.log` - Detailed operation logs

## Configuration

### Frame Processing Configuration
```yaml
frame_processing:
  enabled: true
  auto_debayer: true
  output_dir: "captured_frames"
  cache_dir: "cache"
```

### Camera Configuration
```yaml
camera:
  camera_type: "alpaca"  # or "ascom", "opencv"
  alpaca:
    host: "localhost"
    port: 11111
    device_id: 0
    exposure_time: 10.0
    gain: 100.0
  
  # Cooling Configuration
  cooling:
    enable_cooling: true
    target_temperature: -10.0
    wait_for_cooling: true
    status_interval: 30  # Status update interval in seconds
```

### Overlay Configuration
```yaml
overlay:
  update:
    update_interval: 30
    max_retries: 3
  use_timestamps: true
  wait_for_plate_solve: true
```

### Plate-Solving Configuration
```yaml
plate_solve:
  auto_solve: true
  solver_path: "/path/to/platesolve2"
```

## Components

- **OverlayRunner**: Main orchestration class
- **VideoProcessor**: Handles video capture and plate-solving
- **OverlayGenerator**: Creates astronomical overlays
- **ASCOMMount**: Telescope mount integration
- **ConfigManager**: Configuration management

## Documentation

- [ASCOM Camera Guide](docs/ascom_camera_guide.md)
- [Image Combination Guide](docs/image_combination_guide.md)
- [Overlay Information Panel Guide](docs/overlay_info_panel_guide.md)
- [Secondary FOV Overlay Guide](docs/secondary_fov_guide.md)

## Requirements

- Python 3.7+
- PlateSolve2 (for plate-solving)
- ASCOM Platform (for mount/camera integration)
- OpenCV (for video processing)
- Astropy (for astronomical calculations)

## License

See [LICENSE](LICENSE) file for details.
