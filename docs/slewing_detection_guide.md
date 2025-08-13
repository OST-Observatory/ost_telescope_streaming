# Slewing Detection Guide

## Overview

The OST Telescope Streaming system now includes intelligent slewing detection to prevent image captures during mount movement. This ensures that only stable, high-quality images are captured when the telescope is stationary and tracking properly.

## Why Slewing Detection is Important

### **Problem Without Slewing Detection**
- **Blurred Images**: Captures during movement result in streaked, unusable images
- **Wasted Time**: Processing blurry images wastes computational resources
- **Poor Plate-Solving**: Blurry images often fail plate-solving
- **Reduced Efficiency**: Manual intervention required to skip bad captures

### **Benefits With Slewing Detection**
- ✅ **Sharp Images**: Only captures when telescope is stationary
- ✅ **Efficient Processing**: No time wasted on blurry images
- ✅ **Better Plate-Solving**: Clear images improve solving success rate
- ✅ **Automated Operation**: No manual intervention needed

## How It Works

### **ASCOM Mount Integration**
The system uses the ASCOM `Slewing` property to detect mount movement:

```python
# Check if mount is slewing
is_slewing = self.telescope.Slewing
```

### **Two Operating Modes**

#### **Mode 1: Skip Mode (Default)**
When `wait_for_completion: false`:
- **Behavior**: Skip capture if mount is slewing
- **Use Case**: High-frequency imaging where you want to maximize capture opportunities
- **Log Message**: `"Mount is slewing, skipping capture"`

#### **Mode 2: Wait Mode**
When `wait_for_completion: true`:
- **Behavior**: Wait for slewing to complete, then capture
- **Use Case**: Critical imaging sequences where you need every possible frame
- **Log Message**: `"Mount is slewing, waiting for completion..."`

### **Capture Decision Logic**
Before each image capture, the system checks the slewing status:

```python
def _capture_and_solve(self) -> None:
    # Check if mount is slewing before capturing
    if hasattr(self, 'mount') and self.mount and self.slewing_detection_enabled:
        slewing_status = self.mount.is_slewing()
        if slewing_status.is_success and slewing_status.data:
            if self.slewing_wait_for_completion:
                # Wait for slewing to complete before capturing
                self.logger.info("Mount is slewing, waiting for completion...")
                wait_status = self.mount.wait_for_slewing_complete(
                    timeout=self.slewing_wait_timeout,
                    check_interval=self.slewing_check_interval
                )
                if wait_status.is_success and wait_status.data:
                    self.logger.info("Slewing completed, proceeding with capture")
                else:
                    self.logger.warning(f"Slewing wait failed or timed out: {wait_status.message}")
                    if not wait_status.data:  # Timeout
                        self.logger.info("Skipping capture due to slewing timeout")
                        return
                    else:  # Error
                        self.logger.warning("Continuing with capture despite slewing error")
            else:
                # Skip capture if slewing (default behavior)
                self.logger.debug("Mount is slewing, skipping capture")
                return
```

## Configuration

### **Mount Configuration**
```yaml
mount:
  # ASCOM driver program ID
  driver_id: "ASCOM.tenmicron_mount.Telescope"
  # Connection timeout in seconds
  connection_timeout: 10
  # Coordinate validation
  validate_coordinates: true
  # Slewing detection settings
  slewing_detection:
    enabled: true  # Enable slewing detection to prevent captures during movement
    check_before_capture: true  # Check slewing status before each capture
    wait_for_completion: false  # Wait for slewing to complete before capturing
    wait_timeout: 300  # Maximum wait time in seconds (5 minutes)
    check_interval: 1.0  # Interval between slewing checks in seconds
```

### **Configuration Options**

#### **`enabled`**
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Enable or disable slewing detection entirely

#### **`check_before_capture`**
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Check slewing status before each capture attempt

#### **`wait_for_completion`**
- **Type**: `boolean`
- **Default**: `false`
- **Description**: Wait for slewing to complete before proceeding (vs. skipping capture)

#### **`wait_timeout`**
- **Type**: `float`
- **Default**: `300` (5 minutes)
- **Description**: Maximum time to wait for slewing completion

#### **`check_interval`**
- **Type**: `float`
- **Default**: `1.0` (1 second)
- **Description**: Interval between slewing status checks

## Usage Examples

### **When to Use Each Mode**

#### **Skip Mode (wait_for_completion: false)**
**Best for:**
- High-frequency imaging sequences
- When slewing is frequent and short
- Maximizing capture opportunities
- Real-time monitoring applications

**Example Configuration:**
```yaml
mount:
  slewing_detection:
    enabled: true
    wait_for_completion: false  # Skip captures during slewing
    wait_timeout: 300
    check_interval: 1.0
```

**Behavior:**
```
INFO: Mount is slewing, skipping capture
INFO: Mount is slewing, skipping capture
INFO: FITS frame saved: capture_001.fits  # Captures when stationary
```

#### **Wait Mode (wait_for_completion: true)**
**Best for:**
- Critical imaging sequences
- When you need every possible frame
- Long slewing operations
- Automated observation programs

**Example Configuration:**
```yaml
mount:
  slewing_detection:
    enabled: true
    wait_for_completion: true  # Wait for slewing to complete
    wait_timeout: 300
    check_interval: 1.0
```

**Behavior:**
```
INFO: Mount is slewing, waiting for completion...
INFO: Slewing completed, proceeding with capture
INFO: FITS frame saved: capture_001.fits
```

### **Basic Slewing Check**
```python
from ascom_mount import ASCOMMount

# Create mount connection
mount = ASCOMMount(config=config, logger=logger)

# Check if slewing
slewing_status = mount.is_slewing()
if slewing_status.is_success and slewing_status.data:
    print("Mount is moving - skip capture")
else:
    print("Mount is stationary - proceed with capture")
```

### **Wait for Slewing Completion**
```python
# Wait for slewing to complete before capturing
wait_status = mount.wait_for_slewing_complete(timeout=120)
if wait_status.is_success and wait_status.data:
    print("Slewing completed, ready to capture")
    # Proceed with image capture
else:
    print("Slewing timeout or error")
```

### **Continuous Monitoring**
```python
import time

# Monitor slewing status continuously
while True:
    slewing_status = mount.is_slewing()
    if slewing_status.is_success:
        if slewing_status.data:
            print("Mount is slewing...")
        else:
            print("Mount is stationary")
    else:
        print(f"Error checking slewing: {slewing_status.message}")

    time.sleep(1)  # Check every second
```

## API Reference

### **ASCOMMount Methods**

#### **`is_slewing()`**
```python
def is_slewing(self) -> MountStatus:
    """Check if the mount is currently slewing.
    Returns:
        MountStatus: Status object with slewing information.
    """
```

**Returns:**
- `MountStatus` with `data` containing `True` if slewing, `False` if not
- `details` containing connection and slewing status

**Example:**
```python
slewing_status = mount.is_slewing()
if slewing_status.is_success:
    is_slewing = slewing_status.data
    print(f"Mount is {'slewing' if is_slewing else 'not slewing'}")
```

#### **`wait_for_slewing_complete()`**
```python
def wait_for_slewing_complete(self, timeout: float = 300.0, check_interval: float = 1.0) -> MountStatus:
    """Wait for slewing to complete.
    Args:
        timeout: Maximum wait time in seconds
        check_interval: Interval between checks in seconds
    Returns:
        MountStatus: Status object with result.
    """
```

**Returns:**
- `MountStatus` with `data` containing `True` if completed, `False` if timeout
- `details` containing wait time and timeout information

**Example:**
```python
wait_status = mount.wait_for_slewing_complete(timeout=60)
if wait_status.is_success and wait_status.data:
    print("Slewing completed successfully")
else:
    print("Slewing timeout or error")
```

#### **`get_mount_status()`**
```python
def get_mount_status(self) -> MountStatus:
    """Get complete mount status including slewing information.
    Returns:
        MountStatus: Status object with all mount information.
    """
```

**Returns:**
- `MountStatus` with comprehensive mount information including:
  - `is_slewing`: Current slewing status
  - `coordinates`: Current RA/Dec coordinates
  - `at_park`: Whether mount is parked (if available)
  - `tracking`: Whether mount is tracking (if available)
  - `side_of_pier`: Current side of pier (if available)

## Testing

### **Run the Slewing Detection Test**
```bash
cd tests
python test_slewing_detection.py --config ../config_ost_qhy600m.yaml
```

### **Run the VideoProcessor Integration Test**
```bash
cd tests
python test_slewing_video_processor.py --config ../config_ost_qhy600m.yaml
```

### **Test Output**
```
==================================================
TEST 1: Current slewing status
==================================================
INFO: Current slewing status: NOT SLEWING
INFO: Status details: {'is_connected': True, 'is_slewing': False}

==================================================
TEST 2: Full mount status
==================================================
INFO: Mount status: RA=295.1234°, Dec=40.5678°, Slewing=No
INFO: Coordinates: RA=295.1234°, Dec=40.5678°
INFO: Slewing: No

==================================================
TEST 4: Capture decision simulation
==================================================
INFO: ✅ CAPTURE PROCEEDING: Mount is not slewing
INFO: Capture decision: PROCEED

==================================================
TEST 4b: Wait for completion simulation
==================================================
INFO: ✅ MOUNT STATIONARY: Proceeding with capture
INFO: Wait for completion decision: PROCEED
```

## Performance Considerations

### **Check Frequency**
- **Before each capture**: Minimal overhead (~1ms per check)
- **Continuous monitoring**: Configurable interval (default: 1 second)
- **Performance impact**: Negligible for most applications

### **Timeout Settings**
- **Short slews**: 30-60 seconds timeout
- **Long slews**: 300+ seconds timeout
- **Default**: 300 seconds (5 minutes)

### **Error Handling**
- **Connection errors**: Logged but don't stop captures
- **Property errors**: Graceful fallback
- **Timeout errors**: Configurable behavior

## Troubleshooting

### **Common Issues**

#### **1. "Mount not connected" Error**
```bash
# Check mount connection
python test_slewing_detection.py --config ../config_ost_qhy600m.yaml
```

**Solutions:**
- Verify ASCOM driver is installed and working
- Check `driver_id` in configuration
- Ensure mount is powered on and connected

#### **2. "Could not check slewing status" Warning**
```python
# This is normal - system continues with capture
logger.warning(f"Could not check slewing status: {slewing_status.message}")
```

**Solutions:**
- Check mount driver compatibility
- Verify ASCOM properties are available
- System continues operation as fallback

#### **3. Performance Issues**
```python
# Reduce check frequency if needed
check_interval: 2.0  # Check every 2 seconds instead of 1
```

**Solutions:**
- Increase `check_interval` in configuration
- Disable slewing detection if not needed
- Use `wait_for_completion` instead of continuous checks

### **Debug Information**
```python
# Enable debug logging
logging.getLogger().setLevel(logging.DEBUG)

# Check slewing status with details
slewing_status = mount.is_slewing()
print(f"Status: {slewing_status.message}")
print(f"Details: {slewing_status.details}")
```

## Integration with Main Application

### **VideoProcessor Integration**
The slewing detection is automatically integrated into the `VideoProcessor`:

```python
# In _capture_and_solve method
if hasattr(self, 'mount') and self.mount:
    slewing_status = self.mount.is_slewing()
    if slewing_status.is_success and slewing_status.data:
        self.logger.debug("Mount is slewing, skipping capture")
        return
```

### **Overlay Runner Integration**
The main application automatically uses slewing detection:

```python
# Mount is initialized in VideoProcessor
video_processor = VideoProcessor(config=config, logger=logger)
# Slewing detection is automatically active
```

## Best Practices

### **1. Configure Appropriate Timeouts**
```yaml
mount:
  slewing_detection:
    wait_timeout: 300  # 5 minutes for long slews
    check_interval: 1.0  # 1 second for responsive detection
```

### **2. Monitor Performance**
```bash
# Run performance test
python test_slewing_detection.py --config ../config_ost_qhy600m.yaml
```

### **3. Handle Errors Gracefully**
```python
# System continues operation even if slewing detection fails
if not slewing_status.is_success:
    logger.warning(f"Could not check slewing status: {slewing_status.message}")
    # Continue with capture as fallback
```

### **4. Test with Your Mount**
```bash
# Test with your specific mount configuration
python test_slewing_detection.py --config your_mount_config.yaml
```

## Summary

The slewing detection feature provides:

🎯 **Automatic Protection**: Prevents captures during mount movement
🎯 **Configurable Behavior**: Flexible settings for different use cases
🎯 **Robust Error Handling**: Continues operation even if detection fails
🎯 **Performance Optimized**: Minimal overhead with maximum benefit
🎯 **Easy Integration**: Works automatically with existing workflows

This ensures that your astronomical imaging system only captures high-quality, stable images when the telescope is properly positioned and tracking.
