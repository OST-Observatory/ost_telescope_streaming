# ASCOM Camera Cooling Cache Guide

## 🔍 Problem Overview

ASCOM cameras, especially **QHY cameras**, have a known problem with **caching of cooling values**. This causes values like `CCDTemperature`, `CoolerPower`, and `CoolerOn` to not be updated correctly.

### Symptoms:
- ✅ Cooling works when turned on
- ✅ Values are correct immediately after turning on
- ❌ Values are incorrect or outdated in all other cases

## 🔧 Implemented Solutions

### 1. **Multiple Queries (get_cooling_info)**
```python
# Reads values multiple times with delays
for i in range(3):
    temp_reads.append(self.camera.CCDTemperature)
    time.sleep(0.1)
```

### 2. **Fresh Query (get_fresh_cooling_info)**
```python
# Simulates a cooling operation to update the cache
self.camera.SetCCDTemperature = current_target
```

### 3. **Internal Cache (get_cached_cooling_info)**
```python
# Uses internally stored values from successful operations
self.last_cooling_info = {
    'temperature': new_temp,
    'cooler_power': new_power,
    'cooler_on': new_cooler_on
}
```

### 4. **Smart Selection (get_smart_cooling_info)**
```python
# Automatically selects the best method based on camera type
if 'QHYCCD' in self.driver_id:
    return self.get_cached_cooling_info()
else:
    return self.get_cooling_info()
```

## 🎯 Recommended Usage

### For normal applications:
```python
# Use the smart method
status = camera.get_smart_cooling_info()
if status.is_success:
    info = status.data
    print(f"Temperature: {info['temperature']}°C")
```

### For specific use cases:
```python
# Directly after cooling operations
status = camera.get_cooling_info()  # Should be correct

# For QHY cameras
status = camera.get_cached_cooling_info()  # Bypass ASCOM cache

# For other cameras
status = camera.get_fresh_cooling_info()  # Force refresh
```

## 🧪 Testing

Use the special test for cooling cache issues:

```bash
python tests/test_cooling_cache.py
```

This test:
- Compares all 4 methods
- Tests cooling operations
- Checks cache consistency
- Shows debug information

## 📋 Known Issues

### QHY Cameras:
- **Problem**: Aggressive caching in ASCOM drivers
- **Solution**: Use `get_cached_cooling_info()` or `get_smart_cooling_info()`

### ZWO Cameras:
- **Problem**: Less aggressive, but sometimes delayed updates
- **Solution**: Use `get_fresh_cooling_info()` if problems occur

### Other ASCOM Cameras:
- **Problem**: Varies by driver implementation
- **Solution**: `get_smart_cooling_info()` automatically selects the best method

## 🔄 Cache Management

### Automatic Cache Updates:
```python
# Cache is automatically updated during:
camera.set_cooling(-10.0)      # After setting cooling
camera.turn_cooling_off()      # After turning off cooling
camera.set_cooler_on(True)     # After turning cooler on/off
```

### Manual Cache Updates:
```python
# Manually update cache (if needed)
camera.update_cooling_cache({
    'temperature': -15.0,
    'cooler_power': 75.0,
    'cooler_on': True,
    'target_temperature': -10.0
})
```

**Note**: The cache is automatically updated by all cooling operations, so manual updates are rarely needed.

## 🚨 Troubleshooting

### Problem: Values are still incorrect
1. **Check camera type**: Is it a QHY camera?
2. **Use debug mode**: Enable detailed logging
3. **Test all methods**: Use `test_cooling_cache.py`

### Problem: Cache is empty
1. **Perform cooling operation**: `set_cooling()` or `turn_cooling_off()`
2. **Wait for update**: Cache is automatically filled
3. **Use fallback**: `get_cooling_info()` as backup

### Problem: Performance issues
1. **Use cache**: `get_cached_cooling_info()` is fastest
2. **Reduce queries**: Don't query too frequently
3. **Use smart method**: Automatic optimization

## 📊 Method Comparison

| Method | Speed | Accuracy | QHY Compatibility |
|--------|-------|----------|-------------------|
| `get_cooling_info()` | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| `get_fresh_cooling_info()` | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| `get_cached_cooling_info()` | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| `get_smart_cooling_info()` | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 🔮 Future Improvements

1. **Automatic cache validation**: Check cache validity
2. **Driver-specific optimizations**: Special handling for known drivers
3. **Cache persistence**: Save cache between sessions
4. **Intelligent retry logic**: Automatic retry on errors

## 📝 Code Examples

### Complete Example:
```python
from ascom_camera import ASCOMCamera
from config_manager import ConfigManager

# Setup
config = ConfigManager()
camera = ASCOMCamera(driver_id="ASCOM.QHYCCD.Camera", config=config)

# Connect
camera.connect()

# Turn on cooling
camera.set_cooling(-10.0)

# Get values (automatically uses best method)
status = camera.get_smart_cooling_info()
if status.is_success:
    info = status.data
    print(f"Temperature: {info['temperature']}°C")
    print(f"Cooler Power: {info['cooler_power']}%")
    print(f"Cooler On: {info['cooler_on']}")

# Disconnect
camera.disconnect()
```

### Monitoring Loop:
```python
import time

while True:
    status = camera.get_smart_cooling_info()
    if status.is_success:
        info = status.data
        print(f"Temp: {info['temperature']:.1f}°C, Power: {info['cooler_power']:.1f}%")
    time.sleep(5)  # Every 5 seconds
``` 