# OST Telescope Streaming System

<p align="left">
  <a href="https://github.com/OST-Observatory/ost_telescope_streaming/actions/workflows/ci.yml">
    <img src="https://github.com/OST-Observatory/ost_telescope_streaming/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/OST-Observatory/ost_telescope_streaming/actions/workflows/integration.yml">
    <img src="https://github.com/OST-Observatory/ost_telescope_streaming/actions/workflows/integration.yml/badge.svg" alt="Integration" />
  </a>
  <a href="https://results.pre-commit.ci/latest/github/OST-Observatory/ost_telescope_streaming/main">
    <img src="https://results.pre-commit.ci/badge/github/OST-Observatory/ost_telescope_streaming/main.svg" alt="pre-commit" />
  </a>
  <a href="https://codecov.io/gh/OST-Observatory/ost_telescope_streaming">
    <img src="https://codecov.io/gh/OST-Observatory/ost_telescope_streaming/branch/main/graph/badge.svg" alt="coverage" />
  </a>
</p>

A comprehensive astronomical telescope streaming and overlay system with plate-solving capabilities.

## Features

- **Real-time Video Capture**: Support for ASCOM, Alpaca, and OpenCV cameras
- **Plate-Solving**: Automated coordinate determination using PlateSolve2
- **Astronomical Overlays**: Generate overlays showing stars, deep sky objects, and annotations
- **Information Panel**: Display camera/telescope parameters and field of view information
- **Configurable Title**: Customizable header text for overlays
- **Secondary FOV Overlay**: Display field of view of a second telescope (camera or eyepiece)
- **Ellipse Overlays**: Realistic representation of galaxies and nebulae based on actual dimensions
- **Image Combination**: Combine overlays with captured telescope images
- **Mount Integration**: ASCOM mount support for coordinate tracking
- **Camera Cooling**: Advanced cooling management with thermal shock prevention
- **Configurable**: Flexible configuration system for all components
- **Telemetry & Timing**: Structured logs include capture_id and per-cycle timings (capture/save/solve)

## Architecture

The system is composed of modular subsystems orchestrated by the overlay runner.

```text
+------------------------------+
| overlay_pipeline.py (CLI)    |
+--------------+---------------+
               |
               v
+------------------------------+
| ConfigManager (YAML)         |
|  - loads/merges defaults     |
|  - provides get_*_config()   |
+--------------+---------------+
               |
               v
+------------------------------+
| OverlayRunner                |
|  - session lifecycle         |
|  - plate-solve/overlay loop  |
+----+--------------+----------+
     |              |
     v              v
+-----------+   +--------------------+
| Cooling   |   | VideoProcessor     |
| Service   |   | (code/processing)  |
+-----------+   +---------+----------+
                          |
        +-----------------+-------------------------------+
        |                 |               |               |
        v                 v               v               v
  Capture Adapters   Processing Chain  PlateSolve      Overlay
  (code/capture,     (format/normalize/ (code/platesolve, Generator
   drivers/*)         orientation)        WCS/FOV)        (code/overlay)
        |                 |               |               |
        +-----------------+-------+-------+---------------+
                                  v
                           Combine & Save
                         (services/frame_writer.py)
                                  v
                       Outputs (PNG/JPG, FITS, logs)
```

- Key configuration sections: `camera`, `telescope`, `mount`, `plate_solve`, `overlay`, `site`.
- `site` provides observer coordinates (`latitude`, `longitude`, `elevation_m`), consumed by `VideoProcessor`.

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

### View Timing Telemetry
When running with INFO level (default) you will see per-capture timing aggregation logs:
```
capture_id=42 timings_ms capture=10024.6 save=185.2 solve=920.5
```
and per-file save durations:
```
Frame saved: plate_solve_frames/capture_0042.PNG save_ms=120.4
FITS frame saved: plate_solve_frames/capture_0042.fits save_ms=62.7
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
  # Orientation policy for saved images (display + FITS). Default: long_side_horizontal
  orientation: long_side_horizontal
  # Normalization settings for display (PNG/JPG); FITS always uses uint16 scaling
  normalization:
    method: zscale   # zscale | hist
    contrast: 0.15   # only for zscale
  file_format: "PNG"
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
  title:
    enabled: true
    text: OST Telescope Streaming
  info_panel:
    enabled: true
    show_timestamp: true
    show_coordinates: true
    show_telescope_info: true
    show_camera_info: true
    show_fov_info: true
    # Optional: display cooling status in info panel if cooling is enabled
    show_cooling_info: false
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

## Module Renaming Map

To improve structure and clarity, several modules were renamed and moved. Update imports accordingly.

- code/video_capture.py → code/capture/controller.py
- code/video_processor.py → code/processing/processor.py
- code/ascom_camera.py → code/drivers/ascom/camera.py
- code/ascom_mount.py → code/drivers/ascom/mount.py
- code/alpaca_camera.py → code/drivers/alpaca/camera.py
- code/services/cooling_service.py → code/services/cooling/service.py
- code/services/cooling_backend.py → code/services/cooling/backend.py
- code/overlay_runner.py → code/overlay/runner.py
- code/plate_solver.py → code/platesolve/solver.py
- code/platesolve2_automated.py → code/platesolve/platesolve2.py
- code/dark_capture.py → code/calibration/dark_capture.py
- code/flat_capture.py → code/calibration/flat_capture.py
- code/master_frame_creator.py → code/calibration/master_frame_builder.py
- code/generate_overlay.py → code/overlay/generator.py

Import migration examples:

```python
# Old
from video_capture import VideoCapture
from video_processor import VideoProcessor
from ascom_camera import ASCOMCamera
from alpaca_camera import AlpycaCameraWrapper
from services.cooling_service import CoolingService
from services.cooling_backend import create_cooling_manager

# New
from capture.controller import VideoCapture
from processing.processor import VideoProcessor
from drivers.ascom.camera import ASCOMCamera
from drivers.alpaca.camera import AlpycaCameraWrapper
from services.cooling.service import CoolingService
from services.cooling.backend import create_cooling_manager
```

## Documentation

- [ASCOM Camera Guide](docs/ascom_camera_guide.md)
- [Image Combination Guide](docs/image_combination_guide.md)
- [Overlay Information Panel Guide](docs/overlay_info_panel_guide.md)
- [Secondary FOV Overlay Guide](docs/secondary_fov_guide.md)
- [Ellipse Overlay Guide](docs/ellipse_overlay_guide.md)
- [Integration Test Environment](docs/integration_test_env.md)

## Requirements

- Python 3.7+
- PlateSolve2 (for plate-solving)
- ASCOM Platform (for mount/camera integration)
- OpenCV (for video processing)
- Astropy (for astronomical calculations)

## Development

### Run tests

```bash
pip install -r requirements-dev.txt
# Unit tests by default
pytest -q -m "not integration"

# Run integration tests explicitly (may require hardware/ASCOM/PlateSolve2)
pytest -q -m integration

# Enable image regression tests (optional; requires real baseline images)
OST_ENABLE_IMAGE_REGRESSIONS=1 pytest -q -k overlay_image_regression_unit
```

CI:
- Unit job: Linting/typing + unit tests with coverage
- Integration job: optional, runs separately with `-m integration`
- Coverage report: see the Codecov project page (branch `main`)

Notes:
- `astroquery` is optional. Overlays work without it (empty catalog layer).
- Tests add `code/` to `PYTHONPATH` via `pytest.ini`.

## License

See [LICENSE](LICENSE) file for details.
