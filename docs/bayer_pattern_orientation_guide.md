# Bayer Pattern and Image Orientation Guide

## Overview

When working with ASCOM color cameras, the combination of Bayer patterns and image orientation correction requires special attention to ensure proper color reproduction. This guide explains how the system handles Bayer patterns during image transposition.

## The Problem

### **Bayer Pattern Basics**
Bayer patterns define the arrangement of color filters on the camera sensor:

```
RGGB Pattern:
R G R G R G
G B G B G B
R G R G R G
G B G B G B

GRBG Pattern:
G R G R G R
B G B G B G
G R G R G R
B G B G B G
```

### **ASCOM Image Orientation Issue**
ASCOM cameras often provide images with incorrect orientation compared to other software:
- **Expected**: Long side horizontal, short side vertical
- **ASCOM**: Long side vertical, short side vertical (90° rotated)

### **The Challenge**
When we transpose a Bayer pattern image to correct orientation, we need to ensure the **Bayer pattern interpretation remains correct**.

## Solution Analysis

### **Transpose Operation**
```python
# Before transpose: (height, width)
image_array = np.array([[R, G, R, G],
                        [G, B, G, B],
                        [R, G, R, G],
                        [G, B, G, B]])

# After transpose: (width, height)
image_array = np.transpose(image_array)
# Result: Same pattern, different dimensions
```

### **Bayer Pattern Behavior**
For a **90° rotation (transpose)**:
- **RGGB → RGGB** (no change)
- **GRBG → GRBG** (no change)
- **GBRG → GBRG** (no change)
- **BGGR → BGGR** (no change)

**Why no change?**
- Transpose swaps rows and columns
- Bayer pattern structure remains intact
- Color relationships preserved

## Implementation

### **Bayer Pattern Adjustment Function**
```python
def _adjust_bayer_pattern_for_transpose(self, bayer_pattern: str) -> str:
    """Adjust Bayer pattern when image is transposed.
    
    For transpose (90° rotation), the Bayer pattern stays the same
    because we're swapping rows and columns, not rotating the pattern.
    
    Args:
        bayer_pattern: Original Bayer pattern (RGGB, GRBG, GBRG, BGGR)
    Returns:
        str: Adjusted Bayer pattern (same as input for transpose)
    """
    # For transpose (90° rotation), the Bayer pattern stays the same
    self.logger.debug(f"Bayer pattern unchanged for transpose: {bayer_pattern}")
    return bayer_pattern
```

### **Integration in FITS Saving**
```python
# In _save_ascom_fits()
# 1. Transpose the image
original_shape = image_data.shape
image_data = np.transpose(image_data)
self.logger.info(f"Image orientation corrected: {original_shape} -> {image_data.shape}")

# 2. Adjust Bayer pattern if needed
if is_color_camera and bayer_pattern:
    original_bayer = bayer_pattern
    bayer_pattern = self._adjust_bayer_pattern_for_transpose(bayer_pattern)
    if original_bayer != bayer_pattern:
        self.logger.info(f"Bayer pattern adjusted: {original_bayer} -> {bayer_pattern}")
```

### **Integration in OpenCV Conversion**
```python
# In _convert_ascom_to_opencv()
# 1. Transpose the image
original_shape = image_array.shape
image_array = np.transpose(image_array)
self.logger.debug(f"Image orientation corrected: {original_shape} -> {image_array.shape}")

# 2. Adjust Bayer pattern if needed
if is_color_camera and bayer_pattern:
    original_bayer = bayer_pattern
    bayer_pattern = self._adjust_bayer_pattern_for_transpose(bayer_pattern)
    if original_bayer != bayer_pattern:
        self.logger.info(f"Bayer pattern adjusted: {original_bayer} -> {bayer_pattern}")

# 3. Apply debayering with correct pattern
if bayer_pattern == 'RGGB':
    bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
elif bayer_pattern == 'GRBG':
    bayer_pattern_cv2 = cv2.COLOR_BayerGR2BGR
# ... etc
```

## Testing and Verification

### **Test Scenarios**

#### **1. RGGB Pattern Test**
```python
# Original RGGB pattern
original = np.array([[R, G, R, G],
                     [G, B, G, B],
                     [R, G, R, G],
                     [G, B, G, B]])

# After transpose
transposed = np.transpose(original)
# Pattern remains RGGB
```

#### **2. Color Accuracy Test**
```bash
# Test with known color target
python test_fits_platesolve_overlay.py --color-test --config config_ost_qhy600m.yaml
```

### **Expected Logging**
```
DEBUG: Detected color camera with Bayer pattern: RGGB
INFO: Image orientation corrected: (4000, 6000) -> (6000, 4000)
DEBUG: Bayer pattern unchanged for transpose: RGGB
DEBUG: Successfully debayered image with RGGB pattern
```

## Potential Issues and Solutions

### **Issue 1: Wrong Colors After Transpose**
**Symptoms:**
- Colors appear incorrect
- Red/blue channels swapped
- Green channel distorted

**Causes:**
- Incorrect Bayer pattern after transpose
- Wrong OpenCV debayering constant
- Pattern detection failure

**Solutions:**
```python
# 1. Verify pattern detection
if hasattr(self.ascom_camera, 'sensor_type'):
    print(f"Detected pattern: {self.ascom_camera.sensor_type}")

# 2. Check pattern adjustment
self.logger.debug(f"Bayer pattern: {original_bayer} -> {bayer_pattern}")

# 3. Verify OpenCV constant
if bayer_pattern == 'RGGB':
    bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR  # Correct
```

### **Issue 2: Pattern Detection Failure**
**Symptoms:**
- No Bayer pattern detected
- Fallback to grayscale
- Poor color quality

**Solutions:**
```python
# 1. Check ASCOM driver properties
cam = win32com.client.Dispatch('ASCOM.QHYCCD.Camera')
print(f"SensorType: {cam.SensorType}")
print(f"IsColor: {cam.IsColor}")

# 2. Manual pattern override
bayer_pattern = 'RGGB'  # Force pattern
```

### **Issue 3: Inconsistent Results**
**Symptoms:**
- Different colors in FITS vs PNG
- Inconsistent orientation
- Plate-solving failures

**Solutions:**
```python
# 1. Ensure consistent transpose
# Both FITS and PNG methods use same transpose logic

# 2. Verify pattern consistency
# Both methods use same pattern adjustment

# 3. Check FITS headers
header['BAYERPAT'] = bayer_pattern  # Should match
```

## Best Practices

### **1. Always Test Color Accuracy**
```bash
# Test with known color targets
python test_fits_platesolve_overlay.py --color-test
```

### **2. Monitor Logging**
```python
# Enable debug logging for Bayer pattern info
logging.getLogger().setLevel(logging.DEBUG)
```

### **3. Verify Pattern Detection**
```python
# Check pattern detection in camera setup
if hasattr(ascom_camera, 'sensor_type'):
    logger.info(f"Bayer pattern: {ascom_camera.sensor_type}")
```

### **4. Test Different Patterns**
```python
# Test all supported patterns
patterns = ['RGGB', 'GRBG', 'GBRG', 'BGGR']
for pattern in patterns:
    # Test each pattern
    result = test_bayer_pattern(pattern)
```

## Advanced Topics

### **Other Rotation Angles**
For different rotation angles, Bayer patterns would change:

```python
# 90° rotation (transpose): No change
RGGB -> RGGB

# 180° rotation: Pattern changes
RGGB -> BGGR
GRBG -> GBRG

# 270° rotation: Pattern changes
RGGB -> BGGR
GRBG -> GBRG
```

**Current Implementation:**
- Only handles 90° rotation (transpose)
- Pattern remains unchanged
- Suitable for ASCOM orientation correction

### **Future Enhancements**
```python
def adjust_bayer_pattern_for_rotation(self, bayer_pattern: str, angle: int) -> str:
    """Adjust Bayer pattern for arbitrary rotation angles."""
    if angle == 90:
        return self._adjust_bayer_pattern_for_transpose(bayer_pattern)
    elif angle == 180:
        return self._adjust_bayer_pattern_for_180_rotation(bayer_pattern)
    elif angle == 270:
        return self._adjust_bayer_pattern_for_270_rotation(bayer_pattern)
    else:
        return bayer_pattern
```

## Summary

### **Key Points:**
✅ **Transpose preserves Bayer pattern**: 90° rotation doesn't change pattern
✅ **Consistent implementation**: Both FITS and PNG use same logic
✅ **Proper logging**: Pattern adjustments are logged for debugging
✅ **Fallback handling**: Grayscale fallback if debayering fails

### **Benefits:**
🎯 **Correct colors**: Proper Bayer pattern interpretation
🎯 **Consistent results**: Same colors in all file formats
🎯 **Robust handling**: Fallback mechanisms for edge cases
🎯 **Debugging support**: Comprehensive logging for troubleshooting

### **Verification:**
```bash
# Test color accuracy
python test_fits_platesolve_overlay.py --color-test

# Check logging
grep "Bayer pattern" overlay_runner.log

# Verify file consistency
# FITS and PNG should have same colors and orientation
```

This ensures that color cameras work correctly with the orientation correction system while maintaining proper color reproduction. 