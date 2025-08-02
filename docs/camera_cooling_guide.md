# Camera Cooling Guide

This guide explains how to use the camera cooling features in the telescope streaming system.

## Overview

The camera cooling system provides automatic temperature control for astronomical cameras to reduce thermal noise and improve image quality. The system includes advanced features for reliable cooling status detection and stabilization monitoring.

## Features

### ✅ **Automatic Cooling Control**
- Set target temperature via configuration
- Automatic cooler activation
- Temperature monitoring and logging

### ✅ **Advanced Status Detection**
- **Force Refresh**: Solves ASCOM driver caching issues
- **Stabilization Monitoring**: Waits for cooling to stabilize
- **Power Consumption Tracking**: Monitors cooler power usage
- **Temperature Change Monitoring**: Alternative verification method

### ✅ **Robust Error Handling**
- Graceful handling of unsupported cameras
- Detailed logging and status reporting
- Fallback mechanisms for different camera types

## Configuration

### Basic Cooling Settings

```yaml
camera:
  cooling:
    enable_cooling: true
    target_temperature: -10.0
    auto_cooling: true
    cooling_timeout: 60
    temperature_tolerance: 2.0
    wait_for_cooling: true
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_cooling` | bool | `false` | Enable cooling system |
| `target_temperature` | float | `20.0` | Target temperature in °C |
| `auto_cooling` | bool | `true` | Automatic cooling control |
| `cooling_timeout` | int | `60` | Timeout for cooling operations (seconds) |
| `temperature_tolerance` | float | `2.0` | Temperature tolerance in °C |
| `wait_for_cooling` | bool | `true` | Wait for cooling to stabilize |

## Usage

### Automatic Initialization

The cooling system is automatically initialized when connecting to an ASCOM camera:

```python
from video_capture import VideoCapture

# Initialize with cooling enabled
video_capture = VideoCapture(config=config)
status = video_capture.connect()  # Cooling initialized automatically
```

### Manual Cooling Control

```python
# Enable cooling system
status = video_capture.enable_cooling_system()
if status.is_success:
    print(f"Cooling enabled: {status.message}")

# Set target temperature
status = video_capture.set_target_temperature(-10.0)
if status.is_success:
    print(f"Target temperature set: {status.message}")

# Get cooling status
status = video_capture.get_cooling_status()
if status.is_success:
    info = status.data
    print(f"Temperature: {info['temperature']}°C")
    print(f"Cooler power: {info['cooler_power']}%")
    print(f"Cooler on: {info['cooler_on']}")
```

### Advanced Cooling Features

#### Force Refresh Cooling Status

```python
# Force refresh to solve ASCOM driver caching issues
refresh_status = video_capture.ascom_camera.force_refresh_cooling_status()
if refresh_status.is_success:
    info = refresh_status.data
    print(f"Refreshed: temp={info['temperature']}°C, power={info['cooler_power']}%")
```

#### Wait for Cooling Stabilization

```python
# Wait for cooling to stabilize and show power consumption
stabilization_status = video_capture.ascom_camera.wait_for_cooling_stabilization(
    timeout=60, 
    check_interval=2.0
)
if stabilization_status.is_success:
    info = stabilization_status.data
    print(f"Stabilized: temp={info['temperature']}°C, power={info['cooler_power']}%")
```

## Testing

### Basic Cooling Test

```bash
python tests/test_video_capture.py --config config.yaml --action cooling --cooling-temp -10.0
```

### Keep Cooling Active After Test

```bash
# Cooling will remain on after the test
python tests/test_video_capture.py --config config.yaml --action cooling --cooling-temp -10.0 anke
```

### Check Cooling Status Without Affecting It

```bash
# Only check status, don't change anything
python tests/test_video_capture.py --config config.yaml --action cooling-status
```

### Advanced Cooling Debug

```bash
python tests/test_cooling_debug.py --config config.yaml --target-temp -10.0
```

### Cooling Power Diagnosis

```bash
python tests/test_cooling_power.py --config config.yaml --target-temp -10.0
```

## Troubleshooting

### Common Issues

#### 1. **Cooler Power Shows 0%**
**Problem**: ASCOM driver caching or hardware delay
**Solution**: Use force refresh method
```python
refresh_status = camera.force_refresh_cooling_status()
```

#### 2. **Temperature Not Dropping**
**Problem**: Cooling system not active or hardware issue
**Solution**: Check cooler status and wait for stabilization
```python
stabilization_status = camera.wait_for_cooling_stabilization(timeout=60)
```

#### 3. **Cooling Not Supported**
**Problem**: Camera doesn't support cooling
**Solution**: Check camera capabilities
```python
if camera.has_cooling():
    # Use cooling features
else:
    # Cooling not available
```

### Debug Information

The system provides detailed logging for troubleshooting:

```
2025-08-02 21:46:31 - INFO - Setting cooling target temperature to -10.0°C
2025-08-02 21:46:31 - INFO - Cooler turned on
2025-08-02 21:46:32 - INFO - Target temperature set to -10.0°C
2025-08-02 21:46:32 - INFO - Forcing cooling status refresh...
2025-08-02 21:46:33 - INFO - Cooling status refreshed: temp=23.8°C, power=0.0%, on=True
2025-08-02 21:46:42 - INFO - Cooling status refreshed: temp=23.1°C, power=1.0%, on=True
2025-08-02 21:46:48 - INFO - Cooling status refreshed: temp=22.3°C, power=4.0%, on=True
2025-08-02 21:46:54 - INFO - Cooling status refreshed: temp=21.4°C, power=5.0%, on=True
```

## Best Practices

### 1. **Temperature Settings**
- Set target temperature 10-20°C below ambient
- Allow sufficient time for cooling stabilization
- Monitor temperature changes for verification

### 2. **Power Monitoring**
- Use force refresh for accurate power readings
- Wait for power to stabilize before imaging
- Monitor power consumption for system health

### 3. **Error Handling**
- Always check cooling status before imaging
- Handle unsupported cameras gracefully
- Log cooling operations for troubleshooting

### 4. **Performance Optimization**
- Enable cooling well before imaging sessions
- Use stabilization monitoring for reliable results
- Monitor temperature and power trends

## Integration with Other Systems

### Calibration Frames
Cooling is essential for dark frame capture:
```python
# Cooling must be stable before capturing darks
stabilization_status = camera.wait_for_cooling_stabilization(timeout=60)
if stabilization_status.is_success:
    # Proceed with dark frame capture
    dark_capture.capture_darks()
```

### Live Imaging
Cooling is automatically managed during live capture:
```python
# Cooling is initialized and monitored automatically
video_processor.start_capture()
```

## Technical Details

### ASCOM Integration
The system uses standard ASCOM cooling properties:
- `CanSetCCDTemperature`: Check if cooling is supported
- `CCDTemperature`: Current sensor temperature
- `SetCCDTemperature`: Target temperature setting
- `CoolerOn`: Cooler activation status
- `CoolerPower`: Current cooler power consumption

### Caching and Refresh
ASCOM drivers may cache cooling values. The system includes:
- **Force Refresh**: Multiple reads to update cached values
- **Stabilization Monitoring**: Wait for consistent readings
- **Temperature Monitoring**: Alternative verification method

### Error Recovery
The system includes robust error handling:
- Graceful degradation for unsupported features
- Detailed error reporting and logging
- Automatic retry mechanisms for transient failures

## Examples

### Complete Cooling Workflow

```python
from video_capture import VideoCapture
from config_manager import ConfigManager

# Load configuration
config = ConfigManager("config.yaml")

# Initialize video capture with cooling
video_capture = VideoCapture(config=config)

# Connect (cooling initialized automatically)
status = video_capture.connect()
if not status.is_success:
    print(f"Connection failed: {status.message}")
    exit(1)

# Wait for cooling to stabilize
stabilization_status = video_capture.ascom_camera.wait_for_cooling_stabilization(
    timeout=60, 
    check_interval=2.0
)

if stabilization_status.is_success:
    info = stabilization_status.data
    print(f"Cooling ready: temp={info['temperature']}°C, power={info['cooler_power']}%")
    
    # Start imaging
    video_capture.start_capture()
else:
    print(f"Cooling stabilization failed: {stabilization_status.message}")

# Disconnect
video_capture.disconnect()
```

## Cooling Management

### Starting Cooling

```bash
# Start cooling and keep it active after disconnect
python tests/test_video_capture.py --config config.yaml --action cooling --cooling-temp -10.0 --keep-cooling
```

### Checking Cooling Status

#### **Safe Status Check (Recommended)**
```bash
# Check status from cache without affecting cooling settings
python tests/test_video_capture.py --config config.yaml --action cooling-status-cache
```

#### **Live Status Check (May Reset Settings)**
```bash
# Check live status - may reset cooling settings on some cameras
python tests/test_video_capture.py --config config.yaml --action cooling-status
```

### Status Check Methods

#### **1. `cooling-status-cache` (Recommended)**
- **✅ Safe**: Reads from cache, no camera connection
- **✅ Non-intrusive**: Doesn't affect cooling settings
- **✅ Fast**: No connection overhead
- **⚠️ Cached data**: May not be real-time

#### **2. `cooling-status` (Use with caution)**
- **✅ Real-time**: Live camera connection
- **✅ Accurate**: Current status from camera
- **⚠️ May reset settings**: Some ASCOM drivers reset cooling on connect
- **⚠️ Intrusive**: Creates new connection

### When to Use Each Method

#### **Use `cooling-status-cache` for:**
- **✅ Regular monitoring** during live sessions
- **✅ Quick status checks** without affecting cooling
- **✅ Troubleshooting** cooling issues
- **✅ Verifying** cooling persistence

#### **Use `cooling-status` for:**
- **✅ Initial setup** verification
- **✅ Debugging** connection issues
- **✅ When cache is outdated** or missing
- **✅ Final verification** before imaging

### Stopping Cooling

```bash
# Explicitly turn off cooling and disconnect
python tests/test_video_capture.py --config config.yaml --action cooling-off
```

### Cooling Workflow

#### 1. **Start Cooling for Live Session:**
```bash
# Start cooling and keep it active
python tests/test_video_capture.py --config config.yaml --action cooling --cooling-temp -10.0 --keep-cooling
```

#### 2. **Monitor Cooling During Session:**
```bash
# Check status periodically
python tests/test_video_capture.py --config config.yaml --action cooling-status
```

#### 3. **Stop Cooling After Session:**
```bash
# Turn off cooling when done
python tests/test_video_capture.py --config config.yaml --action cooling-off
```

### Important Notes

#### **⚠️ Cooling Persistence:**
- **With `--keep-cooling`**: Cooling remains active even after script ends
- **Without `--keep-cooling`**: Cooling is turned off when disconnecting
- **Always use `cooling-off`**: To explicitly turn off cooling when done

#### **🔧 ASCOM Behavior:**
- **Connection**: Cooling can be controlled
- **Disconnect**: Cooling is automatically turned off (unless using `--keep-cooling`)
- **Keep-Alive**: `--keep-cooling` prevents automatic cooling shutdown

#### **📊 Status Monitoring:**
- **`cooling-status`**: Safe status check, no changes
- **`cooling`**: Changes cooling settings
- **`cooling-off`**: Explicitly turns off cooling 