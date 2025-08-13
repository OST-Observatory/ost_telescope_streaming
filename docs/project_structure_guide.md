# Project Structure Guide

## Overview

The OST Telescope Streaming project has been reorganized to provide a clear separation between the **main application** and **test scripts**.

## Main Application

### `overlay_runner.py` 🚀
The **main application** that provides the complete automated telescope streaming system:

- **Location**: Root directory
- **Purpose**: Complete automated system with video capture, plate-solving, and overlay generation
- **Usage**: `python overlay_runner.py --config config_ost_qhy600m.yaml`

**Features:**
- Automatic video capture from ASCOM or OpenCV cameras
- Real-time plate-solving with PlateSolve 2
- Continuous overlay generation based on telescope position
- Dual-format saving (FITS for processing, PNG/JPG for display)
- Integrated mount control and coordinate tracking

## Core Modules (`code/`)

### Core System Modules
- **`overlay_runner.py`**: Main automation loop (core module)
- **`config_manager.py`**: Configuration management
- **`status.py`**: Status objects and error handling
- **`exceptions.py`**: Custom exceptions

### Hardware Interface Modules
- **`ascom_mount.py`**: Telescope control and coordinate reading
- **`ascom_camera.py`**: ASCOM camera interface with cooling and filter wheel support

### Processing Modules
- **`video_capture.py`**: Video capture module
- **`video_processor.py`**: Video processing and plate solving
- **`generate_overlay.py`**: Overlay generator (class-based)

### Plate-Solving Modules
- **`plate_solver.py`**: Plate solving interface
- **`platesolve2_automated.py`**: Automated PlateSolve 2 integration

## Test Scripts (`tests/`)

### Test Utilities
- **`test_utils.py`**: Test utilities and helpers
- **`README.md`**: Test documentation

### Basic Functionality Tests
- **`test_basic_functionality.py`**: Configuration, SIMBAD, coordinates
- **`test_status_system.py`**: Status objects and error handling

### Hardware Integration Tests
- **`test_ascom_camera.py`**: ASCOM camera functionality
- **`test_filter_wheel.py`**: Filter wheel functionality

### Video System Tests
- **`test_video_system.py`**: Video capture and processing

### Plate-Solving Tests
- **`test_automated_platesolve2.py`**: PlateSolve 2 automation

### System Integration Tests
- **`test_integration.py`**: System integration
- **`test_final_integration.py`**: End-to-end system test

### Cache Functionality Tests
- **`test_cooling_cache.py`**: ASCOM cooling cache
- **`test_persistent_cache.py`**: Persistent cache functionality
- **`test_cache_debug.py`**: Cache debugging

### Utility Tests
- **`analyze_objects.py`**: SIMBAD object analysis utility

## Configuration Files

### Main Configuration
- **`config.yaml`**: Default configuration file
- **`config_ost_qhy600m.yaml`**: QHY600M-specific configuration

### Documentation
- **`docs/ascom_camera_guide.md`**: ASCOM camera setup guide
- **`docs/ascom_cooling_cache_guide.md`**: Cooling cache documentation
- **`docs/filter_wheel_guide.md`**: Filter wheel setup guide
- **`docs/dual_format_saving_guide.md`**: Dual-format saving documentation

## Usage Patterns

### Main Application Usage
```bash
# Use default configuration
python overlay_runner.py

# Use specific configuration
python overlay_runner.py --config config_ost_qhy600m.yaml
```

### Test Script Usage
```bash
cd tests

# Basic tests
python test_basic_functionality.py

# Hardware tests with configuration
python test_ascom_camera.py --config ../config_ost_qhy600m.yaml

# System tests
python test_final_integration.py --config ../config_ost_qhy600m.yaml
```

## File Organization Benefits

### Clear Separation
- **Main application** is easily identifiable
- **Test scripts** are organized in dedicated directory
- **Core modules** are separated from test code

### Easy Navigation
- **`overlay_runner.py`** is the obvious entry point
- **Test scripts** are grouped by functionality
- **Documentation** is centralized in `docs/`

### Configuration Management
- **Default config** for general use
- **Specific configs** for different hardware setups
- **Test configs** can be passed via `--config`

## Development Workflow

### For Users
1. **Main application**: `python overlay_runner.py`
2. **Configuration**: Edit `config.yaml` or use specific config file
3. **Troubleshooting**: Use test scripts to verify components

### For Developers
1. **Core development**: Work in `code/` directory
2. **Testing**: Use scripts in `tests/` directory
3. **Documentation**: Update files in `docs/` directory

### For Testing
1. **Component tests**: Individual test scripts
2. **Integration tests**: System-wide test scripts
3. **Hardware tests**: ASCOM-specific test scripts
