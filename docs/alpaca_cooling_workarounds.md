# Alpyca Cooling Workarounds

## Problem Summary

The Alpyca interface for ZWO cameras has a known issue with cooling functionality:
- **Cooler Power remains at 0.0%** even when cooler is turned on
- **Target temperature is not properly set** via Alpyca
- **Temperature does not change** despite cooler being "on"

## Root Cause

This is a **ZWO Alpaca Server limitation** - the ZWO ASI driver does not fully implement all cooling properties through the Alpaca interface, even though they are reported as available.

## Workarounds

### 1. Use ZWO ASI Studio for Cooling Control

**Recommended approach for now:**

1. **Open ZWO ASI Studio**
2. **Connect to your camera**
3. **Go to the Cooling tab**
4. **Set target temperature and turn on cooling**
5. **Keep ASI Studio running in background**
6. **Use Alpyca for image capture only**

```bash
# Use Alpyca only for capture, not cooling
python tests/test_video_capture.py --config config_80mm-apo_asi2600ms-pro.yaml --action capture
```

### 2. Hybrid Approach: ASCOM + Alpyca

**Use ASCOM for cooling, Alpyca for capture:**

```yaml
# config_hybrid.yaml
video:
  camera_type: ascom  # Use ASCOM for cooling
  ascom:
    ascom_driver: "ASCOM.ASICamera2.Camera"
    exposure_time: 10.0
    gain: 100.0
    offset: 50.0
    binning: 1

# For capture, switch to Alpyca
capture:
  camera_type: alpaca
  alpaca:
    host: "localhost"
    port: 11111
    device_id: 0
```

### 3. Direct ZWO ASI SDK (Advanced)

**For advanced users who need full control:**

```python
import zwoasi as asi

# Initialize ASI SDK
asi.init('/path/to/asi-sdk')

# Open camera
camera = asi.Camera(0)

# Set cooling
camera.set_control_value(asi.ASI_TARGET_TEMP, -100)  # -10.0°C
camera.set_control_value(asi.ASI_COOLER_ON, 1)

# Capture images
camera.capture_video_frame()
```

### 4. Manual Cooling Control Script

**Create a separate script for cooling control:**

```python
#!/usr/bin/env python3
"""
Manual cooling control for ZWO cameras.
Run this script separately to control cooling.
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from drivers.ascom.camera import ASCOMCamera
from config_manager import ConfigManager

def control_cooling(config_file, target_temp, action='set'):
    """Control cooling using ASCOM interface."""
    config = ConfigManager(config_file)
    video_config = config.get_video_config()

    camera = ASCOMCamera(
        driver_id=video_config['ascom']['ascom_driver'],
        config=config
    )

    if camera.connect().is_success:
        if action == 'set':
            status = camera.set_cooling(target_temp)
            print(f"Cooling set: {status.message}")
        elif action == 'off':
            status = camera.turn_cooling_off()
            print(f"Cooling off: {status.message}")
        elif action == 'status':
            status = camera.get_cooling_status()
            if status.is_success:
                info = status.data
                print(f"Temperature: {info['temperature']}°C")
                print(f"Cooler power: {info['cooler_power']}%")
                print(f"Cooler on: {info['cooler_on']}")

        camera.disconnect()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--temp", type=float, help="Target temperature")
    parser.add_argument("--action", choices=['set', 'off', 'status'], default='status')

    args = parser.parse_args()
    control_cooling(args.config, args.temp, args.action)
```

## Testing and Verification

### 1. Test Cooling with ASCOM

```bash
# Test ASCOM cooling (should work)
python tests/test_video_capture.py --config config_80mm-apo_asi2600ms-pro.yaml --action cooling --cooling-temp -10.0 --camera-type ascom
```

### 2. Test Capture with Alpyca

```bash
# Test Alpyca capture (should work)
python tests/test_video_capture.py --config config_80mm-apo_asi2600ms-pro.yaml --action capture --camera-type alpaca
```

### 3. Verify Cooling Status

```bash
# Check cooling status
python tests/test_video_capture.py --config config_80mm-apo_asi2600ms-pro.yaml --action cooling-status --camera-type ascom
```

## Recommended Workflow

### For Astrophotography:

1. **Start ZWO ASI Studio**
2. **Set cooling target temperature**
3. **Turn on cooling and wait for stabilization**
4. **Keep ASI Studio running**
5. **Use Alpyca for image capture**

### For Automated Systems:

1. **Use ASCOM for cooling control**
2. **Use Alpyca for image capture**
3. **Create separate scripts for each function**

## Future Solutions

### 1. ZWO Alpaca Server Update

ZWO may fix the cooling implementation in future Alpaca server versions.

### 2. Alternative Alpaca Servers

Other Alpaca server implementations might work better:
- **ASCOM Alpaca Server** (if available for ZWO)
- **Third-party Alpaca servers**

### 3. Direct Integration

For critical applications, consider direct ZWO ASI SDK integration.

## Troubleshooting

### If Cooling Still Doesn't Work:

1. **Check ZWO ASI Studio** → Does cooling work there?
2. **Update ZWO drivers** → Latest version installed?
3. **Check USB power** → Enough power for cooler?
4. **Check ambient temperature** → Too hot for cooling?
5. **Check cooler hardware** → Physical damage?

### If Capture Doesn't Work:

1. **Check Alpaca server** → Running on correct port?
2. **Check camera connection** → USB cable OK?
3. **Check other applications** → Camera not in use?
4. **Restart Alpaca server** → Sometimes needed

## Conclusion

The Alpyca cooling issue is a **known limitation** of the ZWO Alpaca server implementation. The recommended solution is to:

- **Use ZWO ASI Studio for cooling control**
- **Use Alpyca for image capture**
- **Keep both running simultaneously**

This provides the best of both worlds: reliable cooling control and modern Python-based image capture.
