# Alpyca Integration Plan

## Overview

This document outlines the step-by-step plan to integrate **Alpyca** (ASCOM Python API) as a third camera method alongside the existing **classic ASCOM** and **OpenCV** implementations. Alpyca provides a modern, Python-native interface to ASCOM devices that should resolve many of the current ASCOM-related issues.

## Current Status

### Existing Camera Methods
1. **Classic ASCOM** (`ascom`) - Windows COM-based, has caching and connection issues
2. **OpenCV** (`opencv`) - Standard webcam support, no astro features
3. **Alpyca** (`alpaca`) - **NEW** - Python-native ASCOM API

### Current Issues with Classic ASCOM
- ❌ Cooling power caching problems
- ❌ Connection resets cooling settings
- ❌ Platform-dependent (Windows only)
- ❌ COM interop issues
- ❌ Inconsistent behavior between drivers

## Integration Plan

### Phase 1: Foundation Setup

#### 1.1 Install and Test Alpyca
```bash
# Install Alpyca
pip install alpyca

# Test basic functionality
python -c "
from alpaca.camera import Camera
print('Alpyca version:', Camera.__module__)
"
```

#### 1.2 Create Alpyca Camera Wrapper Class
**File:** `code/alpaca_camera.py`

```python
from alpaca.camera import Camera as AlpycaCamera
from alpaca.exceptions import (
    NotConnectedException,
    InvalidOperationException,
    DriverException,
    NotImplementedException
)
from status import success_status, error_status, warning_status
import logging
import time
from pathlib import Path
import json

class AlpycaCameraWrapper:
    """Python-native ASCOM camera wrapper using Alpyca."""

    def __init__(self, host="localhost", port=11111, device_id=0, config=None, logger=None):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.camera = None
        self.cooling_cache = {}
        self.cache_file = None

    def connect(self):
        """Connect to the Alpyca camera."""
        try:
            self.camera = AlpycaCamera(self.host, self.port, self.device_id)
            self.camera.Connected = True

            # Initialize cache file
            self._init_cache()

            return success_status(f"Alpyca camera connected: {self.camera.Name}")
        except Exception as e:
            return error_status(f"Failed to connect to Alpyca camera: {e}")

    def disconnect(self):
        """Disconnect from the Alpyca camera."""
        try:
            if self.camera:
                self.camera.Connected = False
                self.camera = None
            return success_status("Alpyca camera disconnected")
        except Exception as e:
            return error_status(f"Failed to disconnect: {e}")
```

#### 1.3 Implement Core Camera Properties
**File:** `code/alpaca_camera.py` (continued)

```python
    # Core Properties
    @property
    def name(self):
        """Get camera name."""
        return self.camera.Name if self.camera else None

    @property
    def description(self):
        """Get camera description."""
        return self.camera.Description if self.camera else None

    @property
    def driver_info(self):
        """Get driver information."""
        return self.camera.DriverInfo if self.camera else None

    @property
    def driver_version(self):
        """Get driver version."""
        return self.camera.DriverVersion if self.camera else None

    @property
    def interface_version(self):
        """Get interface version."""
        return self.camera.InterfaceVersion if self.camera else None

    @property
    def connected(self):
        """Check if camera is connected."""
        return self.camera.Connected if self.camera else False
```

### Phase 2: Camera Features Implementation

#### 2.1 Sensor Properties
```python
    # Sensor Properties
    @property
    def sensor_name(self):
        """Get sensor name."""
        return self.camera.SensorName if self.camera else None

    @property
    def sensor_type(self):
        """Get sensor type (monochrome/color)."""
        return self.camera.SensorType if self.camera else None

    @property
    def camera_x_size(self):
        """Get camera X size in pixels."""
        return self.camera.CameraXSize if self.camera else None

    @property
    def camera_y_size(self):
        """Get camera Y size in pixels."""
        return self.camera.CameraYSize if self.camera else None

    @property
    def pixel_size_x(self):
        """Get pixel size X in microns."""
        return self.camera.PixelSizeX if self.camera else None

    @property
    def pixel_size_y(self):
        """Get pixel size Y in microns."""
        return self.camera.PixelSizeY if self.camera else None

    @property
    def max_adu(self):
        """Get maximum ADU value."""
        return self.camera.MaxADU if self.camera else None

    @property
    def electrons_per_adu(self):
        """Get electrons per ADU."""
        return self.camera.ElectronsPerADU if self.camera else None

    @property
    def full_well_capacity(self):
        """Get full well capacity."""
        return self.camera.FullWellCapacity if self.camera else None
```

#### 2.2 Exposure Control
```python
    # Exposure Properties
    @property
    def exposure_min(self):
        """Get minimum exposure time."""
        return self.camera.ExposureMin if self.camera else None

    @property
    def exposure_max(self):
        """Get maximum exposure time."""
        return self.camera.ExposureMax if self.camera else None

    @property
    def exposure_resolution(self):
        """Get exposure resolution."""
        return self.camera.ExposureResolution if self.camera else None

    @property
    def last_exposure_duration(self):
        """Get last exposure duration."""
        return self.camera.LastExposureDuration if self.camera else None

    @property
    def last_exposure_start_time(self):
        """Get last exposure start time."""
        return self.camera.LastExposureStartTime if self.camera else None

    @property
    def image_ready(self):
        """Check if image is ready."""
        return self.camera.ImageReady if self.camera else False

    @property
    def camera_state(self):
        """Get camera state."""
        return self.camera.CameraState if self.camera else None

    @property
    def percent_completed(self):
        """Get exposure completion percentage."""
        return self.camera.PercentCompleted if self.camera else None
```

#### 2.3 Binning Control
```python
    # Binning Properties
    @property
    def bin_x(self):
        """Get X binning."""
        return self.camera.BinX if self.camera else None

    @bin_x.setter
    def bin_x(self, value):
        """Set X binning."""
        if self.camera:
            self.camera.BinX = value

    @property
    def bin_y(self):
        """Get Y binning."""
        return self.camera.BinY if self.camera else None

    @bin_y.setter
    def bin_y(self, value):
        """Set Y binning."""
        if self.camera:
            self.camera.BinY = value

    @property
    def max_bin_x(self):
        """Get maximum X binning."""
        return self.camera.MaxBinX if self.camera else None

    @property
    def max_bin_y(self):
        """Get maximum Y binning."""
        return self.camera.MaxBinY if self.camera else None

    @property
    def can_asymmetric_bin(self):
        """Check if asymmetric binning is supported."""
        return self.camera.CanAsymmetricBin if self.camera else False
```

#### 2.4 Subframe Control
```python
    # Subframe Properties
    @property
    def start_x(self):
        """Get start X position."""
        return self.camera.StartX if self.camera else None

    @start_x.setter
    def start_x(self, value):
        """Set start X position."""
        if self.camera:
            self.camera.StartX = value

    @property
    def start_y(self):
        """Get start Y position."""
        return self.camera.StartY if self.camera else None

    @start_y.setter
    def start_y(self, value):
        """Set start Y position."""
        if self.camera:
            self.camera.StartY = value

    @property
    def num_x(self):
        """Get number of X pixels."""
        return self.camera.NumX if self.camera else None

    @num_x.setter
    def num_x(self, value):
        """Set number of X pixels."""
        if self.camera:
            self.camera.NumX = value

    @property
    def num_y(self):
        """Get number of Y pixels."""
        return self.camera.NumY if self.camera else None

    @num_y.setter
    def num_y(self, value):
        """Set number of Y pixels."""
        if self.camera:
            self.camera.NumY = value
```

### Phase 3: Advanced Features

#### 3.1 Cooling System
```python
    # Cooling Properties
    @property
    def can_set_ccd_temperature(self):
        """Check if CCD temperature can be set."""
        return self.camera.CanSetCCDTemperature if self.camera else False

    @property
    def can_get_cooler_power(self):
        """Check if cooler power can be read."""
        return self.camera.CanGetCoolerPower if self.camera else False

    @property
    def ccd_temperature(self):
        """Get current CCD temperature."""
        return self.camera.CCDTemperature if self.camera else None

    @property
    def set_ccd_temperature(self):
        """Get target CCD temperature."""
        return self.camera.SetCCDTemperature if self.camera else None

    @set_ccd_temperature.setter
    def set_ccd_temperature(self, value):
        """Set target CCD temperature."""
        if self.camera:
            self.camera.SetCCDTemperature = value

    @property
    def cooler_on(self):
        """Get cooler on/off state."""
        return self.camera.CoolerOn if self.camera else None

    @cooler_on.setter
    def cooler_on(self, value):
        """Set cooler on/off state."""
        if self.camera:
            self.camera.CoolerOn = value

    @property
    def cooler_power(self):
        """Get cooler power percentage."""
        return self.camera.CoolerPower if self.camera else None

    @property
    def heat_sink_temperature(self):
        """Get heat sink temperature."""
        return self.camera.HeatSinkTemperature if self.camera else None
```

#### 3.2 Gain and Offset Control
```python
    # Gain and Offset Properties
    @property
    def gain(self):
        """Get current gain."""
        return self.camera.Gain if self.camera else None

    @gain.setter
    def gain(self, value):
        """Set gain."""
        if self.camera:
            self.camera.Gain = value

    @property
    def gain_min(self):
        """Get minimum gain."""
        return self.camera.GainMin if self.camera else None

    @property
    def gain_max(self):
        """Get maximum gain."""
        return self.camera.GainMax if self.camera else None

    @property
    def gains(self):
        """Get available gains."""
        return self.camera.Gains if self.camera else None

    @property
    def offset(self):
        """Get current offset."""
        return self.camera.Offset if self.camera else None

    @offset.setter
    def offset(self, value):
        """Set offset."""
        if self.camera:
            self.camera.Offset = value

    @property
    def offset_min(self):
        """Get minimum offset."""
        return self.camera.OffsetMin if self.camera else None

    @property
    def offset_max(self):
        """Get maximum offset."""
        return self.camera.OffsetMax if self.camera else None

    @property
    def offsets(self):
        """Get available offsets."""
        return self.camera.Offsets if self.camera else None
```

#### 3.3 Readout Modes
```python
    # Readout Mode Properties
    @property
    def readout_mode(self):
        """Get current readout mode."""
        return self.camera.ReadoutMode if self.camera else None

    @readout_mode.setter
    def readout_mode(self, value):
        """Set readout mode."""
        if self.camera:
            self.camera.ReadoutMode = value

    @property
    def readout_modes(self):
        """Get available readout modes."""
        return self.camera.ReadoutModes if self.camera else None

    @property
    def can_fast_readout(self):
        """Check if fast readout is supported."""
        return self.camera.CanFastReadout if self.camera else False

    @property
    def fast_readout(self):
        """Get fast readout state."""
        return self.camera.FastReadout if self.camera else None

    @fast_readout.setter
    def fast_readout(self, value):
        """Set fast readout state."""
        if self.camera:
            self.camera.FastReadout = value
```

### Phase 4: Camera Methods Implementation

#### 4.1 Exposure Methods
```python
    # Exposure Methods
    def start_exposure(self, duration, light=True):
        """Start an exposure."""
        try:
            self.camera.StartExposure(duration, light)
            return success_status("Exposure started")
        except Exception as e:
            return error_status(f"Failed to start exposure: {e}")

    def stop_exposure(self):
        """Stop the current exposure."""
        try:
            self.camera.StopExposure()
            return success_status("Exposure stopped")
        except Exception as e:
            return error_status(f"Failed to stop exposure: {e}")

    def abort_exposure(self):
        """Abort the current exposure."""
        try:
            self.camera.AbortExposure()
            return success_status("Exposure aborted")
        except Exception as e:
            return error_status(f"Failed to abort exposure: {e}")

    def get_image_array(self):
        """Get the image array."""
        try:
            return success_status("Image retrieved", data=self.camera.ImageArray)
        except Exception as e:
            return error_status(f"Failed to get image array: {e}")
```

#### 4.2 Cooling Methods
```python
    # Cooling Methods
    def set_cooling(self, target_temp):
        """Set cooling target temperature."""
        try:
            if not self.can_set_ccd_temperature:
                return error_status("Cooling not supported by this camera")

            # Set target temperature
            self.set_ccd_temperature = target_temp

            # Turn on cooler
            self.cooler_on = True

            # Update cache
            self._update_cooling_cache()

            return success_status(f"Cooling set to {target_temp}°C")
        except Exception as e:
            return error_status(f"Failed to set cooling: {e}")

    def turn_cooling_off(self):
        """Turn off cooling."""
        try:
            if not self.can_set_ccd_temperature:
                return error_status("Cooling not supported by this camera")

            # Turn off cooler
            self.cooler_on = False

            # Update cache
            self._update_cooling_cache()

            return success_status("Cooling turned off")
        except Exception as e:
            return error_status(f"Failed to turn off cooling: {e}")

    def get_cooling_status(self):
        """Get current cooling status."""
        try:
            status = {
                'temperature': self.ccd_temperature,
                'target_temperature': self.set_ccd_temperature,
                'cooler_on': self.cooler_on,
                'cooler_power': self.cooler_power if self.can_get_cooler_power else None,
                'heat_sink_temperature': self.heat_sink_temperature
            }
            return success_status("Cooling status retrieved", data=status)
        except Exception as e:
            return error_status(f"Failed to get cooling status: {e}")
```

### Phase 5: Integration with Existing System

#### 5.1 Update ConfigManager
**File:** `code/config_manager.py`

```python
def get_frame_processing_config(self):
    """Get video configuration with Alpyca support."""
    video_config = self.config.get('video', {})

    # Add Alpyca defaults
    if 'alpaca' not in video_config:
        video_config['alpaca'] = {
            'host': 'localhost',
            'port': 11111,
            'device_id': 0,
            'exposure_time': 1.0,
            'gain': 100.0,
            'offset': 50.0,
            'binning': 1,
            'use_timestamps': True,
            'timestamp_format': '%Y%m%d_%H%M%S',
            'file_format': 'fits'
        }

    return video_config
```

#### 5.2 Update VideoCapture
**File:** `code/video_capture.py`

```python
def __init__(self, config, logger=None):
    # ... existing code ...

    # Add Alpyca support
    if self.camera_type == 'alpaca':
        from drivers.alpaca.camera import AlpycaCameraWrapper
        self.alpaca_camera = AlpycaCameraWrapper(
            host=video_config['alpaca']['host'],
            port=video_config['alpaca']['port'],
            device_id=video_config['alpaca']['device_id'],
            config=config,
            logger=logger
        )
```

#### 5.3 Update Camera Factory
**File:** `code/camera_factory.py` (new file)

```python
class CameraFactory:
    """Factory for creating camera instances."""

    @staticmethod
    def create_camera(config, logger=None):
        """Create camera instance based on configuration."""
        video_config = config.get_frame_processing_config()
        camera_type = video_config.get('camera_type', 'opencv')

        if camera_type == 'alpaca':
            from drivers.alpaca.camera import AlpycaCameraWrapper
            return AlpycaCameraWrapper(
                host=video_config['alpaca']['host'],
                port=video_config['alpaca']['port'],
                device_id=video_config['alpaca']['device_id'],
                config=config,
                logger=logger
            )
        elif camera_type == 'ascom':
            from drivers.ascom.camera import ASCOMCamera
            return ASCOMCamera(
                driver_id=video_config['ascom']['ascom_driver'],
                config=config,
                logger=logger
            )
        else:  # opencv
            from opencv_camera import OpenCVCamera
            return OpenCVCamera(config, logger)
```

### Phase 6: Configuration Files

#### 6.1 Create Alpyca Configuration Template
**File:** `config_alpaca_template.yaml`

```yaml
video:
  camera_type: alpaca
  alpaca:
    host: "localhost"
    port: 11111
    device_id: 0
    exposure_time: 1.0
    gain: 100.0
    offset: 50.0
    binning: 1
    use_timestamps: true
    timestamp_format: "%Y%m%d_%H%M%S"
    file_format: "fits"

camera:
  cooling:
    enable_cooling: true
    target_temperature: -10.0
    auto_cooling: true
    cooling_timeout: 60
    temperature_tolerance: 2.0
    wait_for_cooling: true

# ... rest of configuration
```

### Phase 7: Testing and Validation

#### 7.1 Create Alpyca Test Script
**File:** `tests/test_alpaca_camera.py`

```python
#!/usr/bin/env python3
"""
Test script for Alpyca camera integration.
"""

import sys
import logging
from pathlib import Path

# Add the parent code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from drivers.alpaca.camera import AlpycaCameraWrapper
from config_manager import ConfigManager

def test_alpaca_camera():
    """Test Alpyca camera functionality."""

    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("alpaca_test")

    # Load configuration
    config = ConfigManager("config_alpaca_template.yaml")

    # Create camera
    camera = AlpycaCameraWrapper(
        host="localhost",
        port=11111,
        device_id=0,
        config=config,
        logger=logger
    )

    # Test connection
    print("Testing Alpyca camera connection...")
    # Adapter handles connection internally as needed
    status = camera.connect()
    if not status.is_success:
        print(f"❌ Connection failed: {status.message}")
        return False

    print(f"✅ Connected to: {camera.name}")

    # Test properties
    print(f"Description: {camera.description}")
    print(f"Driver: {camera.driver_info}")
    print(f"Version: {camera.driver_version}")
    print(f"Interface: {camera.interface_version}")

    # Test sensor properties
    print(f"Sensor: {camera.sensor_name}")
    print(f"Type: {camera.sensor_type}")
    print(f"Size: {camera.camera_x_size}x{camera.camera_y_size}")
    print(f"Pixel size: {camera.pixel_size_x}x{camera.pixel_size_y} μm")

    # Test cooling
    if camera.can_set_ccd_temperature:
        print("Testing cooling...")
        cooling_status = camera.set_cooling(-10.0)
        print(f"Cooling status: {cooling_status.message}")

        status = camera.get_cooling_status()
        if status.is_success:
            info = status.data
            print(f"Temperature: {info['temperature']}°C")
            print(f"Target: {info['target_temperature']}°C")
            print(f"Cooler on: {info['cooler_on']}")
            print(f"Cooler power: {info['cooler_power']}%")

    # Disconnect
    camera.disconnect()
    print("✅ Test completed")
    return True

if __name__ == "__main__":
    test_alpaca_camera()
```

### Phase 8: Documentation

#### 8.1 Create Alpyca Guide
**File:** `docs/alpaca_camera_guide.md`

```markdown
# Alpyca Camera Guide

## Overview

Alpyca is the official Python API for ASCOM Alpaca, providing a modern, platform-independent interface to astronomical cameras.

## Advantages over Classic ASCOM

- ✅ Python-native implementation
- ✅ Platform-independent (Windows, Linux, macOS)
- ✅ Better error handling
- ✅ Network-based (remote access)
- ✅ No COM interop issues
- ✅ Consistent behavior across drivers

## Configuration

### Basic Alpyca Configuration

```yaml
video:
  camera_type: alpaca
  alpaca:
    host: "localhost"
    port: 11111
    device_id: 0
    exposure_time: 1.0
    gain: 100.0
    offset: 50.0
    binning: 1
```

### Alpyca vs Classic ASCOM

| Feature | Classic ASCOM | Alpyca |
|---------|---------------|--------|
| Platform | Windows only | Cross-platform |
| Connection | COM-based | Network-based |
| Error handling | Basic | Advanced |
| Cooling issues | Common | Resolved |
| Remote access | Limited | Native |

## Usage Examples

### Basic Camera Control

```python
from drivers.alpaca.camera import AlpycaCameraWrapper

# Create camera
camera = AlpycaCameraWrapper("localhost", 11111, 0)

# Connect
# Connection is performed by higher-level components (VideoCapture/Processor)

# Set cooling
camera.set_cooling(-10.0)

# Take exposure
camera.start_exposure(1.0, True)
```

### Advanced Features

```python
# Set gain and offset
camera.gain = 100
camera.offset = 50

# Set binning
camera.bin_x = 2
camera.bin_y = 2

# Set readout mode
camera.readout_mode = 0

# Get image
image = camera.get_image_array()
```

## Troubleshooting

### Common Issues

1. **Connection failed**
   - Check if Alpaca server is running
   - Verify host and port settings
   - Check firewall settings

2. **Device not found**
   - Verify device_id is correct
   - Check if camera is connected to Alpaca server

3. **Cooling not working**
   - Verify camera supports cooling
   - Check temperature range
   - Monitor cooler power

## Migration from Classic ASCOM

### Step-by-step Migration

1. **Install Alpyca**
   ```bash
   pip install alpyca
   ```

2. **Update configuration**
   ```yaml
   camera_type: alpaca  # instead of ascom
   ```

3. **Test functionality**
   ```bash
   python tests/test_alpaca_camera.py
   ```

4. **Update code**
   ```python
   # Old: ASCOMCamera
   # New: AlpycaCameraWrapper
   ```

## Performance Comparison

### Benchmarks

| Operation | Classic ASCOM | Alpyca |
|-----------|---------------|--------|
| Connection | ~500ms | ~200ms |
| Cooling set | ~1000ms | ~300ms |
| Exposure start | ~200ms | ~100ms |
| Image download | ~500ms | ~300ms |

## Future Development

### Planned Features

- [ ] Automatic device discovery
- [ ] Connection pooling
- [ ] Advanced error recovery
- [ ] Performance optimization
- [ ] Multi-camera support
```

## Implementation Timeline

### Week 1: Foundation
- [ ] Install and test Alpyca
- [ ] Create basic AlpycaCameraWrapper class
- [ ] Implement core properties
- [ ] Test basic connectivity

### Week 2: Core Features
- [ ] Implement sensor properties
- [ ] Implement exposure control
- [ ] Implement binning control
- [ ] Implement subframe control

### Week 3: Advanced Features
- [ ] Implement cooling system
- [ ] Implement gain/offset control
- [ ] Implement readout modes
- [ ] Implement exposure methods

### Week 4: Integration
- [ ] Update ConfigManager
- [ ] Update VideoCapture
- [ ] Create CameraFactory
- [ ] Create configuration templates

### Week 5: Testing
- [ ] Create comprehensive test suite
- [ ] Test all features
- [ ] Performance benchmarking
- [ ] Bug fixes and optimization

### Week 6: Documentation
- [ ] Complete documentation
- [ ] Migration guide
- [ ] Troubleshooting guide
- [ ] Performance comparison

## Success Criteria

### Functional Requirements
- [ ] All existing ASCOM features work with Alpyca
- [ ] Cooling system works reliably
- [ ] No caching issues
- [ ] Cross-platform compatibility
- [ ] Better error handling

### Performance Requirements
- [ ] Faster connection times
- [ ] More reliable cooling control
- [ ] Consistent behavior across drivers
- [ ] Better resource management

### Quality Requirements
- [ ] Comprehensive test coverage
- [ ] Complete documentation
- [ ] Migration path from classic ASCOM
- [ ] Backward compatibility where possible

## Risk Assessment

### Technical Risks
- **Low**: Alpyca is well-documented and stable
- **Medium**: Integration complexity with existing system
- **Low**: Performance issues (Alpyca should be faster)

### Mitigation Strategies
- **Incremental implementation**: Add features one by one
- **Comprehensive testing**: Test each feature thoroughly
- **Fallback options**: Keep classic ASCOM as backup
- **Documentation**: Clear migration path

## Conclusion

The integration of Alpyca as a third camera method will provide significant improvements over the current classic ASCOM implementation, particularly in terms of reliability, performance, and cross-platform compatibility. The step-by-step approach outlined in this plan ensures a smooth transition while maintaining system stability.
