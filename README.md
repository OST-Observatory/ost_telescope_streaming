# OST Telescope Streaming

An automated sky overlay system for telescope streaming and astronomical observations with integrated plate-solving capabilities.

## 🌟 Features

- **Real-time Overlays**: Automatic generation of sky overlays based on telescope position
- **SIMBAD Integration**: Uses astronomical database for precise object information
- **ASCOM Support**: Compatible with 10Micron and other ASCOM-compatible mounts
- **Automated Plate Solving**: Integrated PlateSolve 2 support for automatic coordinate determination
- **Video Capture**: Modular video system for frame capture and processing
- **Cross-platform**: Works on Windows, Linux and macOS
- **Robust Error Handling**: Automatic recovery from connection issues
- **Configuration System**: Flexible YAML-based configuration
- **Modular Architecture**: Clean separation of concerns with reusable components

## 📋 Requirements

- Python 3.7 or higher
- ASCOM Platform (Windows only, for telescope control)
- 10Micron mount or other ASCOM-compatible mount
- PlateSolve 2 (optional, for automated plate solving)
- Internet connection for SIMBAD queries
- Camera hardware (optional, for video capture)

## 🚀 Installation

1. **Clone repository:**
```bash
git clone https://github.com/your-username/ost_telescope_streaming.git
cd ost_telescope_streaming
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Windows-specific (Windows only):**
```bash
pip install pywin32
```

## ⚙️ Configuration

The system uses a YAML configuration file (`config.yaml`) for all settings:

### Key Configuration Sections:

- **Mount Settings**: ASCOM driver, connection timeout, coordinate validation
- **Telescope Settings**: Focal length, aperture, mount type
- **Camera Settings**: Sensor dimensions, pixel size, camera index
- **Video Settings**: Capture interval, plate solving options, processing parameters
- **Plate Solve Settings**: PlateSolve 2 path, automation settings, solver parameters
- **Overlay Settings**: Field of view, magnitude limit, image size, font settings
- **Streaming Settings**: Update interval, retry limits, timestamp options
- **Display Settings**: Colors, marker size, text positioning
- **Logging Settings**: Verbosity, log file options
- **Platform Settings**: Font paths for different operating systems

### Example Configuration:
```yaml
telescope:
  focal_length: 1000        # Focal length in mm
  aperture: 200             # Aperture in mm

camera:
  sensor_width: 6.17        # Sensor width in mm
  sensor_height: 4.55       # Sensor height in mm
  camera_index: 0           # Camera device index

video:
  plate_solving_enabled: true
  capture_interval: 30      # Capture interval in seconds
  auto_solve: true

plate_solve:
  default_solver: "platesolve2"
  platesolve2_path: "C:\\Program Files (x86)\\PlaneWave Instruments\\PWI3\\PlateSolve2\\PlateSolve2.exe"
  number_of_regions: 999
  auto_mode: true

overlay:
  field_of_view: 1.5        # Field of view in degrees
  magnitude_limit: 10.0     # Maximum magnitude of displayed objects
  image_size: [1920, 1080]  # Image size in pixels

streaming:
  update_interval: 30       # Update interval in seconds
  max_retries: 3           # Maximum retry attempts
```

## 📖 Usage

### Main Application - Overlay Runner

The **main application** is `overlay_runner.py`, which provides the complete automated telescope streaming system:

```bash
python overlay_runner.py
```

**Features:**
- Automatic video capture from ASCOM or OpenCV cameras
- Real-time plate-solving with PlateSolve 2
- Continuous overlay generation based on telescope position
- Dual-format saving (FITS for processing, PNG/JPG for display)
- Integrated mount control and coordinate tracking

**Configuration:**
```bash
# Use specific configuration file
python overlay_runner.py --config config_ost_qhy600m.yaml

# Use default configuration
python overlay_runner.py
```

### Test Scripts

The system includes comprehensive test scripts in the `tests/` directory:

#### Basic Functionality Tests
```bash
cd tests
python test_basic_functionality.py
```

#### Video System Tests
```bash
cd tests
python test_video_system.py --config ../config_ost_qhy600m.yaml
```

#### Integration Tests
```bash
cd tests
python test_integration.py --config ../config_ost_qhy600m.yaml
```

#### Plate-Solving Tests
```bash
cd tests
python test_automated_platesolve2.py --config ../config_ost_qhy600m.yaml
```

#### Complete System Tests
```bash
cd tests
python test_final_integration.py --config ../config_ost_qhy600m.yaml
```

#### ASCOM Camera Tests
```bash
cd tests
python test_ascom_camera.py --config ../config_ost_qhy600m.yaml
```

#### Filter Wheel Tests
```bash
cd tests
python test_filter_wheel.py --config ../config_ost_qhy600m.yaml
```

## 🧪 Testing

The project includes a comprehensive test suite in the `tests/` directory to verify all components:

### Quick Test Run

```bash
cd tests
python test_basic_functionality.py
python test_integration.py
python test_final_integration.py
```

### Complete Test Suite

```bash
cd tests
# Basic functionality tests
python test_basic_functionality.py    # Configuration, SIMBAD, coordinates
python test_status_system.py          # Status objects and error handling

# Hardware integration tests
python test_ascom_camera.py --config ../config_ost_qhy600m.yaml
python test_filter_wheel.py --config ../config_ost_qhy600m.yaml

# Video system tests
python test_video_system.py --config ../config_ost_qhy600m.yaml

# Plate-solving tests
python test_automated_platesolve2.py --config ../config_ost_qhy600m.yaml

# System integration tests
python test_integration.py --config ../config_ost_qhy600m.yaml
python test_final_integration.py --config ../config_ost_qhy600m.yaml

# Cache functionality tests
python test_cooling_cache.py --config ../config_ost_qhy600m.yaml
python test_persistent_cache.py --config ../config_ost_qhy600m.yaml
python test_cache_debug.py --config ../config_ost_qhy600m.yaml
```

### Test Configuration

All test scripts support configuration via `--config`:
```bash
python test_ascom_camera.py --config ../config_ost_qhy600m.yaml
python test_video_system.py --config ../config_ost_qhy600m.yaml
```

### Test Options

Most test scripts support additional options:
```bash
# Verbose output
python test_ascom_camera.py --verbose --config ../config_ost_qhy600m.yaml

# Debug mode
python test_ascom_camera.py --debug --config ../config_ost_qhy600m.yaml

# Quiet mode
python test_ascom_camera.py --quiet --config ../config_ost_qhy600m.yaml
```

### Test Results

All tests provide detailed output with:
- ✅ Successful tests
- ❌ Failed tests
- 📋 Summary at the end
- 🔍 Detailed logging for debugging

## 📁 Project Structure

```
ost_telescope_streaming/
├── overlay_runner.py            # 🚀 MAIN APPLICATION - Complete automated system
├── code/
│   ├── ascom_mount.py           # Telescope control and coordinate reading
│   ├── generate_overlay.py      # Overlay generator (class-based)
│   ├── overlay_runner.py        # Main automation loop (core module)
│   ├── config_manager.py        # Configuration management
│   ├── plate_solver.py          # Plate solving interface
│   ├── platesolve2_automated.py # Automated PlateSolve 2 integration
│   ├── video_capture.py         # Video capture module
│   ├── video_processor.py       # Video processing and plate solving
│   ├── ascom_camera.py          # ASCOM camera interface
│   ├── status.py                # Status objects and error handling
│   └── exceptions.py            # Custom exceptions
├── tests/                       # 🧪 TEST SCRIPTS
│   ├── README.md                # Test documentation
│   ├── test_utils.py            # Test utilities and helpers
│   ├── test_basic_functionality.py    # Configuration, SIMBAD, coordinates
│   ├── test_video_system.py           # Video capture and processing
│   ├── test_integration.py            # System integration
│   ├── test_automated_platesolve2.py  # PlateSolve 2 automation
│   ├── test_final_integration.py      # End-to-end system test
│   ├── test_ascom_camera.py           # ASCOM camera functionality
│   ├── test_filter_wheel.py           # Filter wheel functionality
│   ├── test_cooling_cache.py          # ASCOM cooling cache
│   ├── test_persistent_cache.py       # Persistent cache functionality
│   ├── test_cache_debug.py            # Cache debugging
│   ├── test_status_system.py          # Status object system
│   └── analyze_objects.py             # SIMBAD object analysis utility
├── docs/                        # 📚 DOCUMENTATION
│   ├── ascom_camera_guide.md    # ASCOM camera setup guide
│   ├── ascom_cooling_cache_guide.md # Cooling cache documentation
│   ├── filter_wheel_guide.md    # Filter wheel setup guide
│   └── dual_format_saving_guide.md # Dual-format saving documentation
├── config.yaml                  # Default configuration file
├── config_ost_qhy600m.yaml      # QHY600M-specific configuration
├── requirements.txt             # Dependencies
├── clean_cache.py               # Cache cleaning utility
├── LICENSE                      # License file
└── README.md                    # This file
```

## 🔧 Troubleshooting

### Common Issues:

1. **"ASCOM mount is only available on Windows"**
   - Solution: The system only runs on Windows with ASCOM Platform installed

2. **"Failed to connect to mount"**
   - Check if mount is powered on and connected
   - Verify ASCOM driver installation
   - Test connection in ASCOM Device Hub

3. **"PlateSolve 2 not found"**
   - Verify PlateSolve 2 installation path in `config.yaml`
   - Ensure PlateSolve 2 is properly installed
   - Check file permissions

4. **"Could not load TrueType font"**
   - System automatically uses fallback font
   - Functionality remains intact

5. **"SIMBAD query running..." (hangs)**
   - Check internet connection
   - SIMBAD queries may take some time depending on server load

6. **"Camera not accessible"**
   - Check if camera is in use by another application
   - Verify camera drivers are installed
   - Try different camera index in configuration

7. **UnicodeEncodeError with charmap codec**
   - This indicates cached Python files with old Unicode characters
   - Run the cache cleaning script:
   ```bash
   python clean_cache.py
   ```
   - Or manually delete `__pycache__` directories and `.pyc` files
   - Restart your Python environment

### Logs and Debugging:

- All errors are displayed with detailed messages
- Critical errors automatically stop the system
- Overlay files are saved with timestamps
- Configuration can be adjusted without code changes
- Test suite provides comprehensive diagnostics

## 🔄 Configuration Management

The system includes a robust configuration management system:

- **Automatic Fallback**: Uses defaults if config file is missing
- **Validation**: Validates configuration values
- **Hot Reload**: Configuration can be reloaded without restart
- **Platform Detection**: Automatically detects OS and applies appropriate settings

### Configuration Methods:

```python
from config_manager import config

# Get specific value
fov = config.get('overlay.field_of_view', 1.5)

# Get entire section
mount_config = config.get_mount_config()
telescope_config = config.get_telescope_config()
camera_config = config.get_camera_config()
video_config = config.get_video_config()
plate_solve_config = config.get_plate_solve_config()

# Reload configuration
config.reload()
```

## 🏗️ Architecture

The system uses a modular architecture with clear separation of concerns:

- **Configuration Layer**: Centralized configuration management
- **Hardware Layer**: Telescope and camera interfaces
- **Processing Layer**: Video capture, plate solving, and overlay generation
- **Integration Layer**: Main automation and coordination
- **Test Layer**: Comprehensive testing and validation

### Key Components:

- **OverlayRunner** (`overlay_runner.py`): Main application with complete automated system
- **OverlayGenerator**: Class-based overlay generation with direct import capability
- **PlateSolve2Automated**: Automated PlateSolve 2 integration with .apm file parsing
- **VideoProcessor**: Modular video capture and processing system with dual-format saving
- **ASCOMCamera**: ASCOM camera interface with cooling and filter wheel support
- **ConfigManager**: Centralized configuration management with validation
- **Status System**: Standardized error handling and status reporting

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run the test suite to ensure everything works
4. Commit your changes
5. Push to the branch
6. Create a Pull Request

### Development Guidelines:

- Follow the existing code structure and naming conventions
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass before submitting

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.

## 🙏 Acknowledgments

- [ASCOM](http://ascom-standards.org/) for telescope protocol
- [SIMBAD](http://simbad.u-strasbg.fr/) for astronomical data
- [AstroPy](https://www.astropy.org/) for astronomical calculations
- [PlateSolve 2](http://www.platesolve.com/) by Dave Rowe for plate solving capabilities
- [OpenCV](https://opencv.org/) for video capture and processing
