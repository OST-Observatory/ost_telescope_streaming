# Camera Cooling Guide

## Overview

The OST Telescope Streaming system now includes comprehensive camera cooling support for ASCOM-compatible cameras. This feature allows automatic temperature control to reduce thermal noise and improve image quality for astronomical observations.

## Features

### 1. Automatic Cooling Control
- **Temperature Setting**: Configure target temperature in Celsius
- **Power Control**: Adjust cooling power percentage
- **Auto-cooling Mode**: Automatic temperature regulation
- **Timeout Handling**: Configurable cooling timeout

### 2. Temperature Monitoring
- **Real-time Monitoring**: Continuous temperature tracking
- **Stability Detection**: Automatic detection of temperature stability
- **Tolerance Control**: Configurable temperature tolerance
- **Status Reporting**: Detailed cooling status information

### 3. Integration
- **ASCOM Integration**: Seamless integration with ASCOM camera drivers
- **Automatic Initialization**: Cooling starts automatically on camera connection
- **Configuration-based**: All settings controlled via configuration files
- **Error Handling**: Robust error handling and recovery

## Configuration

### Camera Cooling Settings

```yaml
camera:
  # Sensor parameters
  sensor_width: 36.0    # Sensor width in mm
  sensor_height: 24.0   # Sensor height in mm
  pixel_size: 3.76      # Pixel size in micrometers
  type: "mono"          # Camera type (mono, color)
  bit_depth: 16         # Bit depth
  
  # Cooling settings for ASCOM cameras
  cooling:
    enable_cooling: true           # Enable camera cooling
    target_temperature: -10.0      # Target temperature in Celsius
    auto_cooling: true             # Auto-cooling mode
    cooling_timeout: 300           # Cooling timeout in seconds
    temperature_tolerance: 1.0     # Temperature tolerance in Celsius
    wait_for_cooling: true         # Wait for target temperature before capture
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enable_cooling` | false | Enable camera cooling system |
| `target_temperature` | -10.0 | Target temperature in Celsius |
| `auto_cooling` | true | Enable automatic cooling mode |
| `cooling_timeout` | 300 | Cooling timeout in seconds |
| `temperature_tolerance` | 1.0 | Temperature tolerance in Celsius |
| `wait_for_cooling` | true | Wait for target temperature before capture |

## Usage Examples

### 1. Basic Cooling Setup

```python
# Camera automatically initializes cooling on connection
video_capture = VideoCapture(config=config)
video_capture.connect()

# Check cooling status
cooling_status = video_capture.get_cooling_status()
print(f"Current temperature: {cooling_status['current_temperature']}°C")
print(f"Target temperature: {cooling_status['target_temperature']}°C")
print(f"Cooler on: {cooling_status['cooler_on']}")
```

### 2. Manual Cooling Control

```python
# Enable cooling system
status = video_capture.enable_cooling_system()
if status.is_success:
    print("Cooling system enabled")

# Set specific target temperature
status = video_capture.set_target_temperature(-15.0)
if status.is_success:
    print("Target temperature set to -15°C")

# Wait for target temperature
status = video_capture.wait_for_target_temperature()
if status.is_success:
    print("Target temperature reached")

# Disable cooling
status = video_capture.disable_cooling_system()
if status.is_success:
    print("Cooling system disabled")
```

### 3. Cooling Status Monitoring

```python
# Get comprehensive camera information including cooling
camera_info = video_capture.get_camera_info()

if camera_info['has_cooling']:
    print("Camera supports cooling")
    if camera_info['cooling_enabled']:
        print(f"Cooling enabled, target: {camera_info['target_temperature']}°C")
        
        # Get detailed cooling status
        cooling_status = video_capture.get_cooling_status()
        print(f"Current temperature: {cooling_status['current_temperature']}°C")
        print(f"Cooler power: {cooling_status['cooler_power']}%")
        print(f"Temperature stable: {cooling_status['temperature_stable']}")
else:
    print("Camera does not support cooling")
```

## How It Works

### 1. Cooling Initialization

```python
def initialize_cooling(self):
    # Check if cooling is supported
    if not self.has_cooling():
        return success_status("Cooling not supported")
    
    # Check if cooling is enabled in config
    if not self.enable_cooling:
        return success_status("Cooling disabled")
    
    # Enable cooling system
    cooling_status = self.enable_cooling_system()
    
    # Wait for target temperature if configured
    if self.wait_for_cooling:
        return self.wait_for_target_temperature()
    
    return success_status("Cooling system initialized")
```

### 2. Temperature Monitoring

```python
def wait_for_target_temperature(self):
    start_time = time.time()
    
    while time.time() - start_time < self.cooling_timeout:
        cooling_status = self.get_cooling_status()
        current_temp = cooling_status['current_temperature']
        target_temp = cooling_status['target_temperature']
        
        if current_temp and target_temp:
            temp_diff = abs(current_temp - target_temp)
            
            if temp_diff <= self.temperature_tolerance:
                return success_status("Target temperature reached")
        
        time.sleep(2)  # Check every 2 seconds
    
    return error_status("Cooling timeout")
```

### 3. ASCOM Integration

The cooling system integrates with ASCOM camera drivers:

```python
# ASCOM camera cooling methods
camera.has_cooling()                    # Check if cooling supported
camera.set_cooling(target_temp)         # Set target temperature
camera.set_cooler_on(True/False)        # Turn cooler on/off
camera.get_cooling_info()               # Get cooling status
camera.turn_cooling_off()               # Turn off cooling
```

## Best Practices

### 1. Temperature Settings

- **Target Temperature**: -10°C to -20°C is typical for most cameras
- **Tolerance**: 1°C tolerance is usually sufficient
- **Automatic Control**: Cooling power is automatically controlled by the camera
- **Timeout**: 300 seconds (5 minutes) is usually adequate

### 2. Initialization

- **Enable on Connection**: Cooling automatically initializes when camera connects
- **Wait for Stability**: Allow time for temperature to stabilize before capturing
- **Monitor Status**: Check cooling status before important captures

### 3. Power Management

- **Auto-cooling**: Enable for automatic temperature regulation
- **Automatic Power Control**: Camera automatically adjusts cooling power to maintain target temperature
- **Ambient Temperature**: Consider ambient temperature when setting targets

### 4. Error Handling

- **Timeout Handling**: Set appropriate timeouts for your environment
- **Error Recovery**: System continues operation even if cooling fails
- **Status Monitoring**: Regularly check cooling status during long sessions

## Troubleshooting

### Common Issues

1. **Cooling Not Supported**
   ```python
   if not video_capture.has_cooling():
       print("Camera does not support cooling")
   ```

2. **Cooling Disabled**
   ```python
   # Check configuration
   cooling_config = config.get_camera_config()['cooling']
   print(f"Cooling enabled: {cooling_config['enable_cooling']}")
   ```

3. **Temperature Not Reaching Target**
   ```python
   # Check cooling status
   status = video_capture.get_cooling_status()
   print(f"Current: {status['current_temperature']}°C")
   print(f"Target: {status['target_temperature']}°C")
   print(f"Cooler on: {status['cooler_on']}")
   print(f"Cooler power: {status['cooler_power']}%")
   ```

4. **Cooling Timeout**
   ```python
   # Increase timeout in configuration
   cooling:
     cooling_timeout: 600  # 10 minutes instead of 5
   ```

### Debug Information

Enable debug logging for detailed cooling information:

```python
import logging
logging.getLogger('video_capture').setLevel(logging.DEBUG)
```

This will show:
- Cooling initialization steps
- Temperature monitoring details
- ASCOM driver interactions
- Error details and diagnostics

## Performance Considerations

### 1. Cooling Time

- **Initial Cooling**: 5-15 minutes to reach target temperature
- **Temperature Stability**: 1-2 minutes after reaching target
- **Recovery Time**: 2-5 minutes after temperature changes

### 2. Power Consumption

- **Cooling Power**: 10-50W typical for cooled cameras
- **Power Efficiency**: Lower temperatures require more power
- **Ambient Temperature**: Higher ambient = more power needed

### 3. Image Quality

- **Thermal Noise**: Reduces significantly with cooling
- **Dark Current**: Decreases exponentially with temperature
- **Dynamic Range**: Improves with lower noise

## Integration with Other Systems

### 1. Calibration Integration

Cooling works seamlessly with the calibration system:

```python
# Cooling ensures consistent temperature for calibration frames
# Master darks are created at the same temperature as science frames
# This improves calibration quality and consistency
```

### 2. Observation Workflow

```python
# 1. Connect camera (cooling initializes automatically)
video_capture.connect()

# 2. Wait for temperature stability
video_capture.wait_for_target_temperature()

# 3. Capture calibration frames
# 4. Capture science frames
# 5. All frames benefit from consistent cooling
```

### 3. Long-term Monitoring

```python
# Monitor cooling during long observations
while observation_running:
    cooling_status = video_capture.get_cooling_status()
    log_temperature(cooling_status['current_temperature'])
    time.sleep(60)  # Check every minute
```

## Future Enhancements

- **Temperature Logging**: Automatic temperature logging over time
- **Adaptive Cooling**: Automatic temperature adjustment based on conditions
- **Power Optimization**: Intelligent power management
- **Multi-camera Support**: Cooling control for multiple cameras
- **Environmental Integration**: Consider ambient temperature and humidity 