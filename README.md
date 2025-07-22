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

### Generate Single Overlay

```bash
python code/generate_overlay.py --ra 180.0 --dec 45.0
```

**Parameters:**
- `--ra`: Right Ascension in degrees (0-360)
- `--dec`: Declination in degrees (-90 to +90)
- `--output`: Output file (optional, default from config)

### Continuous Streaming with Overlay Generation

```bash
python code/overlay_runner.py
```

The runner automatically creates a new overlay every 30 seconds based on the current telescope position.

### Video Capture and Plate Solving

```bash
python code/video_processor.py
```

Automatically captures video frames and performs plate solving to determine coordinates.

### Test Telescope Coordinates

```bash
python code/ascom_mount.py
```

Continuously displays current RA/Dec coordinates of the mount.

## 🧪 Testing

The project includes a comprehensive test suite to verify all components:

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
python test_basic_functionality.py    # Configuration, SIMBAD, coordinates
python test_video_system.py           # Video capture and processing
python test_integration.py            # System integration
python test_automated_platesolve2.py  # PlateSolve 2 automation
python test_final_integration.py      # End-to-end system test
```

### Video System Testing

```bash
# List available cameras
python test_video_system.py --list

# Test specific camera
python test_video_system.py --test-camera --camera 0

# Skip hardware tests (software-only)
python test_video_system.py --skip-camera
```

### Test Results

All tests provide detailed output with:
- ✅ Successful tests
- ❌ Failed tests
- 📋 Summary at the end

## 📁 Project Structure

```
ost_telescope_streaming/
├── code/
│   ├── ascom_mount.py           # Telescope control and coordinate reading
│   ├── generate_overlay.py      # Overlay generator (class-based)
│   ├── overlay_runner.py        # Main automation loop
│   ├── config_manager.py        # Configuration management
│   ├── plate_solver.py          # Plate solving interface
│   ├── plate_solver_automated.py # Automated PlateSolve 2 integration
│   ├── video_capture.py         # Video capture module
│   └── video_processor.py       # Video processing and plate solving
├── tests/
│   ├── README.md                # Test documentation
│   ├── test_basic_functionality.py    # Configuration, SIMBAD, coordinates
│   ├── test_video_system.py           # Video capture and processing
│   ├── test_integration.py            # System integration
│   ├── test_automated_platesolve2.py  # PlateSolve 2 automation
│   ├── test_final_integration.py      # End-to-end system test
│   └── analyze_objects.py             # SIMBAD object analysis utility
├── config.yaml                 # Configuration file
├── requirements.txt            # Dependencies
├── clean_cache.py              # Cache cleaning utility
└── README.md                   # This file
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

- **OverlayGenerator**: Class-based overlay generation with direct import capability
- **PlateSolve2Automated**: Automated PlateSolve 2 integration with .apm file parsing
- **VideoProcessor**: Modular video capture and processing system
- **OverlayRunner**: Main automation loop with integrated components

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
