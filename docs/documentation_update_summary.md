# Documentation Update Summary

## Overview

This document summarizes all documentation updates made to reflect the new project structure where `overlay_runner.py` is the main application and all other scripts are test scripts in the `tests/` directory.

## Updated Files

### 1. README.md ✅
**Major Updates:**
- **Main Application Section**: Clearly identifies `overlay_runner.py` as the main application
- **Usage Section**: Updated to focus on main application with test examples
- **Project Structure**: Updated with clear separation between main app and tests
- **Testing Section**: Reorganized to show test scripts in `tests/` directory
- **Architecture Section**: Updated key components list

**Key Changes:**
```bash
# Before
python code/overlay_runner.py

# After
python overlay_runner.py --config config_ost_qhy600m.yaml
```

### 2. docs/project_structure_guide.md ✅
**New File Created:**
- **Complete project structure explanation**
- **Main application vs test scripts separation**
- **Usage patterns for both main app and tests**
- **Development workflow guidelines**

### 3. docs/ascom_camera_guide.md ✅
**Updated:**
- **Command Line Interface Section**: Changed from `main_video_capture.py` to test scripts
- **Usage Examples**: Updated to use test scripts in `tests/` directory

**Key Changes:**
```bash
# Before
python main_video_capture.py --camera-type ascom --ascom-driver "ASCOM.QHYCamera.Camera"

# After
cd tests
python test_ascom_camera.py --config ../config_ost_qhy600m.yaml
```

### 4. docs/ascom_cooling_cache_guide.md ✅
**Updated:**
- **Testing Section**: Updated to use test scripts with `--config` option
- **Test Commands**: Added proper directory navigation and configuration

**Key Changes:**
```bash
# Before
python tests/test_cooling_cache.py

# After
cd tests
python test_cooling_cache.py --config ../config_ost_qhy600m.yaml
```

### 5. docs/filter_wheel_guide.md ✅
**Updated:**
- **Command Line Usage**: Updated to use test scripts with proper configuration
- **Test Examples**: Added `--config` and `--debug` options

**Key Changes:**
```bash
# Before
python tests/test_filter_wheel.py

# After
cd tests
python test_filter_wheel.py --config ../config_ost_qhy600m.yaml --debug
```

### 6. tests/README.md ✅
**Already Current:**
- **Comprehensive test documentation**
- **All test scripts documented**
- **Configuration options explained**
- **Best practices included**

## New Project Structure

### Main Application
```
overlay_runner.py  # 🚀 MAIN APPLICATION
```

### Core Modules
```
code/
├── overlay_runner.py        # Core automation loop
├── config_manager.py        # Configuration management
├── status.py               # Status objects
├── exceptions.py           # Custom exceptions
├── ascom_mount.py          # Telescope control
├── ascom_camera.py         # ASCOM camera interface
├── video_capture.py        # Video capture
├── video_processor.py      # Video processing
├── generate_overlay.py     # Overlay generator
├── plate_solver.py         # Plate solving interface
└── platesolve2_automated.py # PlateSolve 2 integration
```

### Test Scripts
```
tests/
├── test_utils.py           # Test utilities
├── test_basic_functionality.py
├── test_status_system.py
├── test_ascom_camera.py
├── test_filter_wheel.py
├── test_video_system.py
├── test_automated_platesolve2.py
├── test_integration.py
├── test_final_integration.py
├── test_cooling_cache.py
├── test_persistent_cache.py
├── test_cache_debug.py
└── analyze_objects.py
```

## Usage Patterns

### Main Application
```bash
# Standard usage
python overlay_runner.py

# With specific configuration
python overlay_runner.py --config config_ost_qhy600m.yaml
```

### Test Scripts
```bash
cd tests

# Basic tests
python test_basic_functionality.py

# Hardware tests with configuration
python test_ascom_camera.py --config ../config_ost_qhy600m.yaml

# System tests
python test_final_integration.py --config ../config_ost_qhy600m.yaml
```

## Benefits of Updated Documentation

### 1. Clear Separation
- **Main application** is easily identifiable
- **Test scripts** are clearly separated
- **Usage patterns** are distinct

### 2. Consistent Configuration
- **All tests** support `--config` option
- **Proper directory navigation** for tests
- **Standardized command patterns**

### 3. Better User Experience
- **Obvious entry point** (`overlay_runner.py`)
- **Clear test organization** in `tests/` directory
- **Comprehensive documentation** for all aspects

### 4. Developer Friendly
- **Easy to find** main application
- **Organized test structure**
- **Clear development workflow**

## Documentation Standards

### File Naming
- **Main application**: `overlay_runner.py` (root directory)
- **Test scripts**: `test_*.py` (in `tests/` directory)
- **Documentation**: `docs/*.md`

### Command Patterns
- **Main app**: `python overlay_runner.py [--config file]`
- **Tests**: `cd tests && python test_*.py --config ../config.yaml`

### Configuration
- **Default**: `config.yaml`
- **Specific**: `config_ost_qhy600m.yaml`
- **Test**: `test_config_example.yaml`

## Summary

All documentation has been updated to reflect the new project structure:

✅ **README.md** - Main project documentation updated
✅ **docs/project_structure_guide.md** - New comprehensive structure guide
✅ **docs/ascom_camera_guide.md** - Updated CLI examples
✅ **docs/ascom_cooling_cache_guide.md** - Updated test commands
✅ **docs/filter_wheel_guide.md** - Updated test commands
✅ **tests/README.md** - Already current and comprehensive

The documentation now provides a clear, consistent, and user-friendly guide to the reorganized project structure.
