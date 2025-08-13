# Image Orientation Debugging Guide

## Problem Description

You're seeing that PNG images saved from ASCOM cameras don't appear rotated in the Windows Photos app, even though the system should be applying orientation correction.

## Possible Causes

### **1. Image Already in Correct Orientation**
The most likely cause is that **your ASCOM camera is already providing images in the correct orientation**.

**Check this by running:**
```bash
cd tests
python test_image_orientation.py --config ../config_ost_qhy600m.yaml
```

**Look for this log message:**
```
DEBUG: Image already in correct orientation: (6000, 4000), no rotation needed
```

### **2. Rotation Not Being Applied**
The rotation logic might not be working correctly.

**Check for these log messages:**
```
INFO: Image orientation corrected: (4000, 6000) -> (6000, 4000)
INFO: ✅ Rotation applied successfully: (4000, 6000) -> (6000, 4000)
```

### **3. Wrong Rotation Direction**
The rotation might be applied in the wrong direction.

**Check the dimensions:**
- **Before rotation**: `(height, width)` where height > width
- **After rotation**: `(width, height)` where width > height

## Debugging Steps

### **Step 1: Run the Orientation Test**
```bash
cd tests
python test_image_orientation.py --config ../config_ost_qhy600m.yaml
```

This will create several test files in `test_orientation_output/`:
- `original_before_rotation.png` - Before any rotation
- `rotated_after_rotation.png` - After rotation
- `full_conversion.png` - Full conversion result
- `save_frame_test.png` - Save frame result

### **Step 2: Check the Logs**
Look for these key log messages:

#### **If rotation is needed and applied:**
```
INFO: Image orientation corrected: (4000, 6000) -> (6000, 4000)
INFO: ✅ Rotation applied successfully: (4000, 6000) -> (6000, 4000)
```

#### **If rotation is not needed:**
```
DEBUG: Image already in correct orientation: (6000, 4000), no rotation needed
```

#### **If there's a problem:**
```
WARNING: ⚠️ Rotation may not have worked as expected: (4000, 6000) -> (4000, 6000)
```

### **Step 3: Compare the Test Files**
Open the files in `test_orientation_output/` and compare:

1. **`original_before_rotation.png`** vs **`rotated_after_rotation.png`**
   - These should be different if rotation was applied
   - The rotated version should have the long side horizontal

2. **`full_conversion.png`** vs **`save_frame_test.png`**
   - These should be identical
   - Both should have the correct orientation

### **Step 4: Check Image Dimensions**
Use a tool like ImageMagick or Python to check dimensions:

```python
import cv2
import numpy as np

# Check dimensions
img = cv2.imread("test_orientation_output/save_frame_test.png")
print(f"Image dimensions: {img.shape}")  # Should be (height, width, channels)
print(f"Width: {img.shape[1]}, Height: {img.shape[0]}")
print(f"Long side horizontal: {img.shape[1] > img.shape[0]}")
```

## Common Scenarios

### **Scenario 1: No Rotation Needed**
**Logs:**
```
DEBUG: Image already in correct orientation: (6000, 4000), no rotation needed
```

**Explanation:** Your ASCOM camera is already providing images in the correct orientation. This is actually **good news** - it means your camera driver is working correctly.

**Action:** No action needed. The system correctly detected that no rotation was necessary.

### **Scenario 2: Rotation Applied Successfully**
**Logs:**
```
INFO: Image orientation corrected: (4000, 6000) -> (6000, 4000)
INFO: ✅ Rotation applied successfully: (4000, 6000) -> (6000, 4000)
```

**Explanation:** The system detected that rotation was needed and applied it correctly.

**Action:** Check if the saved PNG files actually show the rotation. If not, there might be an issue with the file saving process.

### **Scenario 3: Rotation Failed**
**Logs:**
```
WARNING: ⚠️ Rotation may not have worked as expected: (4000, 6000) -> (4000, 6000)
```

**Explanation:** The rotation was attempted but didn't change the dimensions as expected.

**Action:** This indicates a bug in the rotation logic that needs to be fixed.

## Troubleshooting

### **If Images Still Appear Rotated**

1. **Check if rotation is being applied:**
   ```bash
   grep "orientation" overlay_runner.log
   ```

2. **Verify the rotation logic:**
   ```python
   # In your code, add debug prints:
   print(f"Original shape: {image.shape}")
   print(f"Needs rotation: {height > width}")
   print(f"After rotation: {rotated_image.shape}")
   ```

3. **Test with a known image:**
   ```python
   # Create a test image with known orientation
   test_image = np.zeros((4000, 6000, 3), dtype=np.uint8)
   # Add some text or pattern to see orientation
   cv2.putText(test_image, "TOP", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2)
   ```

### **If Rotation is Applied but Images Still Wrong**

1. **Check the transpose operation:**
   ```python
   # The correct transpose for RGB images:
   result_image = np.transpose(result_image, (1, 0, 2))
   ```

2. **Verify the dimensions:**
   ```python
   # Before: (height, width, channels)
   # After:  (width, height, channels)
   ```

3. **Check if the image is being saved correctly:**
   ```python
   # Make sure the rotated image is what's being saved
   cv2.imwrite(filename, rotated_image)
   ```

## Expected Behavior

### **For ASCOM Cameras with Vertical Orientation:**
- **Raw data**: `(4000, 6000)` - height > width
- **After rotation**: `(6000, 4000)` - width > height
- **Display**: Long side horizontal

### **For ASCOM Cameras with Horizontal Orientation:**
- **Raw data**: `(6000, 4000)` - width > height
- **No rotation needed**: `(6000, 4000)` - width > height
- **Display**: Long side horizontal (already correct)

## Fixes

### **If Rotation is Not Being Applied When Needed:**

1. **Check the `_needs_rotation` method:**
   ```python
   def _needs_rotation(self, image_shape: tuple) -> bool:
       if len(image_shape) >= 2:
           height, width = image_shape[0], image_shape[1]
           return height > width  # Long side vertical needs rotation
       return False
   ```

2. **Verify the rotation logic:**
   ```python
   if self._needs_rotation(result_image.shape):
       result_image = np.transpose(result_image, (1, 0, 2))
   ```

### **If Rotation is Applied in Wrong Direction:**

Change the transpose operation:
```python
# For 90° clockwise rotation:
result_image = np.transpose(result_image, (1, 0, 2))

# For 90° counter-clockwise rotation:
result_image = np.transpose(result_image, (1, 0, 2))[::-1, :, :]
```

## Summary

The most likely cause is that **your ASCOM camera is already providing images in the correct orientation**, so no rotation is needed. The system correctly detects this and skips the rotation step.

To verify this:
1. Run the orientation test script
2. Check the log messages
3. Compare the test output files
4. Verify the final image dimensions

If the images are indeed in the wrong orientation and no rotation is being applied, then there's a bug in the rotation detection logic that needs to be fixed.
