# OST Telescope Streaming System

A comprehensive astronomical telescope streaming and overlay system with plate-solving capabilities.

## Features

- **Real-time Video Capture**: Support for ASCOM cameras and OpenCV
- **Plate-Solving**: Automated coordinate determination using PlateSolve2
- **Astronomical Overlays**: Generate overlays showing stars, deep sky objects, and annotations
- **Image Combination**: Combine overlays with captured telescope images
- **Mount Integration**: ASCOM mount support for coordinate tracking
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

# With video processing and image combination
python overlay_pipeline.py --enable-video --wait-for-plate-solve

# With custom interval and debug logging
python overlay_pipeline.py --enable-video --interval 60 --debug
```

## Command Line Options

```bash
python overlay_pipeline.py [OPTIONS]

Options:
  --config, -c CONFIG_FILE    Configuration file path (default: config.yaml)
  --interval, -i SECONDS      Update interval in seconds (default: 30)
  --debug, -d                 Enable debug logging
  --wait-for-plate-solve      Wait for plate-solving results before generating overlays
  --enable-video              Enable video processing and frame capture
  --log-level LEVEL           Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

## Examples

### Basic Overlay Generation
```bash
python overlay_pipeline.py --config my_config.yaml
```

### Full System with Image Combination
```bash
python overlay_pipeline.py --enable-video --wait-for-plate-solve --interval 60
```

### Debug Mode
```bash
python overlay_pipeline.py --enable-video --debug
```

## Output Files

The system generates several types of files:

- **Overlay Files**: `overlay_YYYYMMDD_HHMMSS.png` - Pure astronomical overlays
- **Combined Files**: `combined_YYYYMMDD_HHMMSS.png` - Captured images with overlays
- **Log Files**: `overlay_runner_YYYYMMDD.log` - Detailed operation logs

## Configuration

### Video Configuration
```yaml
video:
  video_enabled: true
  camera_type: "opencv"  # or "ascom"
  opencv:
    frame_width: 1920
    frame_height: 1080
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

## Requirements

- Python 3.7+
- PlateSolve2 (for plate-solving)
- ASCOM Platform (for mount/camera integration)
- OpenCV (for video processing)
- Astropy (for astronomical calculations)

## License

See [LICENSE](LICENSE) file for details.
