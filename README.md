# OST Telescope Streaming

An automated sky overlay system for telescope streaming and astronomical observations.

## 🌟 Features

- **Real-time Overlays**: Automatic generation of sky overlays based on telescope position
- **SIMBAD Integration**: Uses astronomical database for precise object information
- **ASCOM Support**: Compatible with 10Micron and other ASCOM-compatible mounts
- **Cross-platform**: Works on Windows, Linux and macOS
- **Robust Error Handling**: Automatic recovery from connection issues
- **Configuration System**: Flexible YAML-based configuration

## 📋 Requirements

- Python 3.7 or higher
- ASCOM Platform (Windows only)
- 10Micron mount or other ASCOM-compatible mount
- Internet connection for SIMBAD queries

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
- **Overlay Settings**: Field of view, magnitude limit, image size, font settings
- **Streaming Settings**: Update interval, retry limits, timestamp options
- **Display Settings**: Colors, marker size, text positioning
- **Logging Settings**: Verbosity, log file options
- **Platform Settings**: Font paths for different operating systems

### Example Configuration:
```yaml
overlay:
  field_of_view: 1.5        # Field of view in degrees
  magnitude_limit: 10.0     # Maximum magnitude of displayed objects
  image_size: [800, 800]    # Image size in pixels

streaming:
  update_interval: 30       # Update interval in seconds
  max_retries: 3           # Maximum retry attempts
```

## 🎯 Usage

### Generate Single Overlay

```bash
python code/generate_overlay.py --ra 180.0 --dec 45.0
```

**Parameters:**
- `--ra`: Right Ascension in degrees (0-360)
- `--dec`: Declination in degrees (-90 to +90)
- `--output`: Output file (optional, default from config)

### Continuous Streaming

```bash
python code/overlay_runner.py
```

The runner automatically creates a new overlay every 30 seconds based on the current telescope position.

### Test Telescope Coordinates

```bash
python code/ascom_mount.py
```

Continuously displays current RA/Dec coordinates of the mount.

### Test Configuration

```bash
python test_config.py
```

Tests the configuration system to ensure it's working correctly.

## 🔧 Troubleshooting

### Common Issues:

1. **"ASCOM mount is only available on Windows"**
   - Solution: The system only runs on Windows with ASCOM Platform installed

2. **"Failed to connect to mount"**
   - Check if mount is powered on and connected
   - Verify ASCOM driver installation
   - Test connection in ASCOM Device Hub

3. **"Could not load TrueType font"**
   - System automatically uses fallback font
   - Functionality remains intact

4. **"SIMBAD query running..." (hangs)**
   - Check internet connection
   - Query has 30-second timeout

5. **UnicodeEncodeError with charmap codec**
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

## 📁 Project Structure

```
ost_telescope_streaming/
├── code/
│   ├── ascom_mount.py      # Telescope control
│   ├── generate_overlay.py # Overlay generator
│   ├── overlay_runner.py   # Automation
│   └── config_manager.py   # Configuration management
├── config.yaml             # Configuration file
├── requirements.txt        # Dependencies
├── test_config.py          # Configuration test script
├── clean_cache.py          # Cache cleaning utility
└── README.md              # This file
```

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

# Reload configuration
config.reload()
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.

## 🙏 Acknowledgments

- [ASCOM](http://ascom-standards.org/) for telescope protocol
- [SIMBAD](http://simbad.u-strasbg.fr/) for astronomical data
- [AstroPy](https://www.astropy.org/) for astronomical calculations
