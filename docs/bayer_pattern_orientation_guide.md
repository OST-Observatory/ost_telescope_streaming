# Bayer Pattern and Image Orientation Guide

## Overview

When working with ASCOM color cameras, the combination of Bayer patterns and image orientation correction requires special attention to ensure proper color reproduction. This guide explains the **simplified approach** used by the system.

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
When we need to correct image orientation, we must ensure **proper color reproduction** for Bayer pattern images.

## Solution: Debayer First, Then Rotate

### **The Elegant Solution**
Instead of rotating Bayer patterns (which is complex), we use a **much simpler approach**:

1. **Debayer the raw data** first (using original Bayer pattern)
2. **Rotate the resulting RGB image** (simple transpose)

### **Why This is Better**
- ✅ **Simpler logic**: No Bayer pattern adjustments needed
- ✅ **More robust**: Works with any Bayer pattern
- ✅ **Easier to debug**: Clear separation of concerns
- ✅ **Better performance**: Single rotation operation

## Implementation

### **For Display Formats (PNG/JPG)**
```python
def _convert_to_opencv(self, image_data):
    # 1. Convert raw data to numpy array
    image_array = np.array(ascom_image_data)
    
    # 2. Detect Bayer pattern
    if hasattr(self.ascom_camera, 'sensor_type'):
        bayer_pattern = self.ascom_camera.sensor_type
    
    # 3. DEBAYER FIRST (before any rotation)
    if is_color_camera and bayer_pattern:
        if bayer_pattern == 'RGGB':
            bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
        elif bayer_pattern == 'GRBG':
            bayer_pattern_cv2 = cv2.COLOR_BayerGR2BGR
        # ... etc
        
        result_image = cv2.cvtColor(image_array, bayer_pattern_cv2)
        self.logger.debug(f"Successfully debayered image with {bayer_pattern} pattern")
    
    # 4. THEN apply orientation correction to RGB image
    original_shape = result_image.shape
    result_image = np.transpose(result_image, (1, 0, 2))  # Transpose only spatial dimensions
    self.logger.debug(f"Image orientation corrected: {original_shape} -> {result_image.shape}")
    
    return result_image
```

### **For FITS Files (Plate-Solving)**
```python
def _save_fits_unified(self, frame, filename):
    # 1. Get raw Bayer data
    image_data = frame.data
    
    # 2. Apply orientation correction to raw data
    original_shape = image_data.shape
    image_data = np.transpose(image_data)
    self.logger.info(f"Image orientation corrected: {original_shape} -> {image_data.shape}")
    
    # 3. Note: For 90° rotation (transpose), Bayer patterns remain unchanged
    # RGGB -> RGGB, GRBG -> GRBG, GBRG -> GBRG, BGGR -> BGGR
    # No pattern adjustment needed for this rotation
    
    # 4. Save with original Bayer pattern in header
    header['BAYERPAT'] = bayer_pattern
    header['COLORCAM'] = True
```

## Why This Works

### **Bayer Pattern Behavior Under Transpose**
For a **90° rotation (transpose)**:
- **RGGB → RGGB** (no change)
- **GRBG → GRBG** (no change)
- **GBRG → GBRG** (no change)
- **BGGR → BGGR** (no change)

**Why no change?**
- Transpose swaps rows and columns
- Bayer pattern structure remains intact
- Color relationships preserved

### **The Key Insight**
Since **90° rotation doesn't change Bayer patterns**, we can:
1. **Debayer first** using the original pattern
2. **Rotate the RGB result** without worrying about pattern changes

## Comparison: Old vs New Approach

### **Old Approach (Complex)**
```python
# 1. Rotate raw Bayer data
image_array = np.transpose(image_array)

# 2. Adjust Bayer pattern (complex logic)
bayer_pattern = self._adjust_bayer_pattern_for_transpose(bayer_pattern)

# 3. Debayer with adjusted pattern
result_image = cv2.cvtColor(image_array, bayer_pattern_cv2)
```

### **New Approach (Simple)**
```python
# 1. Debayer raw data with original pattern
result_image = cv2.cvtColor(image_array, bayer_pattern_cv2)

# 2. Rotate the RGB result
result_image = np.transpose(result_image, (1, 0, 2))
```

## Testing and Verification

### **Test Scenarios**

#### **1. Color Accuracy Test**
```bash
# Test with known color target
python test_fits_platesolve_overlay.py --color-test --config config_ost_qhy600m.yaml
```

#### **2. Expected Logging**
```
DEBUG: Detected color camera with Bayer pattern: RGGB
DEBUG: Successfully debayered image with RGGB pattern
DEBUG: Image orientation corrected: (4000, 6000) -> (6000, 4000)
```

### **Verification Steps**
1. **Check color accuracy**: Colors should be correct
2. **Verify orientation**: Images should have correct orientation
3. **Confirm consistency**: FITS and PNG should match

## Benefits of the New Approach

### **Simplicity**
- ✅ **No complex pattern adjustments**
- ✅ **Clear separation of concerns**
- ✅ **Easier to understand and maintain**

### **Robustness**
- ✅ **Works with any Bayer pattern**
- ✅ **No edge cases for pattern changes**
- ✅ **Consistent results**

### **Performance**
- ✅ **Single rotation operation**
- ✅ **No pattern calculation overhead**
- ✅ **Faster processing**

### **Debugging**
- ✅ **Clear logging of each step**
- ✅ **Easy to identify issues**
- ✅ **Simple to test**

## Potential Issues and Solutions

### **Issue 1: Wrong Colors**
**Symptoms:**
- Colors appear incorrect
- Red/blue channels swapped

**Causes:**
- Wrong Bayer pattern detection
- Incorrect OpenCV debayering constant

**Solutions:**
```python
# 1. Verify pattern detection
if hasattr(self.ascom_camera, 'sensor_type'):
    print(f"Detected pattern: {self.ascom_camera.sensor_type}")

# 2. Check OpenCV constant mapping
if bayer_pattern == 'RGGB':
    bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR  # Correct
```

### **Issue 2: Incorrect Orientation**
**Symptoms:**
- Images still rotated
- Wrong aspect ratio

**Causes:**
- Transpose not applied
- Wrong transpose dimensions

**Solutions:**
```python
# 1. Check transpose operation
result_image = np.transpose(result_image, (1, 0, 2))  # Correct for RGB

# 2. Verify shape change
self.logger.debug(f"Shape: {original_shape} -> {result_image.shape}")
```

## Best Practices

### **1. Always Test Color Accuracy**
```bash
# Test with known color targets
python test_fits_platesolve_overlay.py --color-test
```

### **2. Monitor Logging**
```python
# Enable debug logging
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
```

## Summary

### **Key Points:**
✅ **Debayer first, then rotate**: Much simpler approach
✅ **No pattern adjustments needed**: 90° rotation preserves patterns
✅ **Clear separation of concerns**: Debayering and rotation are separate
✅ **Robust implementation**: Works with all Bayer patterns

### **Benefits:**
🎯 **Simpler code**: Easier to understand and maintain
🎯 **Better performance**: Single rotation operation
🎯 **More robust**: No complex pattern calculations
🎯 **Easier debugging**: Clear step-by-step process

### **Verification:**
```bash
# Test color accuracy
python test_fits_platesolve_overlay.py --color-test

# Check logging
grep "debayered\|orientation" overlay_runner.log

# Verify file consistency
# FITS and PNG should have same colors and orientation
```

This simplified approach ensures that color cameras work correctly with the orientation correction system while maintaining proper color reproduction and much simpler code. 