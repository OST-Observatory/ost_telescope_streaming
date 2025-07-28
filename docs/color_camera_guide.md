# ASCOM Color Camera Support Guide

## Overview

The OST Telescope Streaming system now provides comprehensive support for ASCOM color cameras with automatic Bayer pattern detection, debayering, and proper FITS file handling. This guide explains how color cameras are supported throughout the system.

## Color Camera Detection

### Automatic Detection

The system automatically detects color cameras using multiple methods:

#### **1. ASCOM SensorType Property**
```python
# In ascom_camera.py
def sensor_type(self) -> Optional[str]:
    if hasattr(self.camera, 'SensorType'):
        sensor_type = self.camera.SensorType
        # ASCOM SensorType enum values:
        # 0=Monochrome, 1=Color, 2=RgGg, 3=RGGB, 4=GRBG, 5=GBRG, 6=BGGR
```

#### **2. Bayer Pattern Detection**
```python
# Supported Bayer patterns
BAYER_PATTERNS = ['RGGB', 'GRBG', 'GBRG', 'BGGR']
```

#### **3. FITS Header Information**
```python
# Color camera indicators in FITS headers
header['COLORCAM'] = True
header['BAYERPAT'] = 'RGGB'  # Bayer pattern
```

## Supported Bayer Patterns

### **RGGB Pattern**
- **ASCOM SensorType**: 3
- **OpenCV Pattern**: `cv2.COLOR_BayerRG2BGR`
- **Common Cameras**: Many DSLR cameras, some CCD cameras

### **GRBG Pattern**
- **ASCOM SensorType**: 4
- **OpenCV Pattern**: `cv2.COLOR_BayerGR2BGR`
- **Common Cameras**: Some CCD cameras

### **GBRG Pattern**
- **ASCOM SensorType**: 5
- **OpenCV Pattern**: `cv2.COLOR_BayerGB2BGR`
- **Common Cameras**: Some specialized cameras

### **BGGR Pattern**
- **ASCOM SensorType**: 6
- **OpenCV Pattern**: `cv2.COLOR_BayerBG2BGR`
- **Common Cameras**: Some CCD cameras

## FITS File Handling

### **Color Camera FITS Support**

The system handles color cameras in FITS files with special considerations:

#### **1. FITS Header Information**
```python
# Color camera headers added to FITS files
header['COLORCAM'] = True
header['BAYERPAT'] = 'RGGB'
header['NAXIS3'] = 3  # For RGB images
```

#### **2. Plate-Solving Strategy**
For plate-solving, color cameras are processed using the **green channel**:

```python
# Use green channel for plate-solving (most sensitive for astronomy)
if is_color_camera and len(image_data.shape) == 3:
    if image_data.shape[2] >= 3:
        green_channel = image_data[:, :, 1]  # Green channel
        image_data = green_channel
```

**Why Green Channel?**
- **Sensitivity**: Green channel is most sensitive for astronomical imaging
- **Plate-Solving**: Most star catalogs are optimized for monochrome data
- **Performance**: Faster processing with 2D data

#### **3. Display Conversion**
For display purposes, full color conversion is performed:

```python
# Full debayering for display
if is_color_camera and bayer_pattern:
    color_image = cv2.cvtColor(image_array, bayer_pattern_cv2)
```

## Image Processing Pipeline

### **1. Raw Capture**
```python
# ASCOM camera provides raw Bayer data
raw_data = ascom_camera.get_image()
```

### **2. FITS Storage**
```python
# Store with color information in header
# Convert to 2D (green channel) for plate-solving
fits_data = extract_green_channel(raw_data)
```

### **3. Display Conversion**
```python
# Full debayering for display
display_image = debayer_image(raw_data, bayer_pattern)
```

### **4. Plate-Solving**
```python
# Use 2D green channel data
plate_solve_result = solve_plate(fits_data)
```

## Configuration

### **Camera Configuration**
```yaml
# config.yaml
video:
  camera_type: ascom
  ascom:
    ascom_driver: ASCOM.QHYCCD.Camera
    # Bayer pattern will be auto-detected
```

### **Manual Bayer Pattern Override**
```yaml
# If auto-detection fails
video:
  ascom:
    bayer_pattern: RGGB  # Manual override
```

## Testing Color Cameras

### **1. Basic Color Camera Test**
```bash
cd tests

# Test color camera functionality
python test_fits_platesolve_overlay.py capture.fits --color-test

# Standard test (works with both mono and color)
python test_fits_platesolve_overlay.py capture.fits
```

### **2. Test Output**
The color camera test provides detailed information:

```
============================================================
TEST: Color Camera Functionality
============================================================
1. Extracting FITS parameters...
✅ Color camera detected: RGGB pattern, 3 channels
2. Converting FITS to PNG...
✅ Input PNG created: capture_input.png
3. Performing plate-solving...
✅ Plate-solving successful
4. Generating overlay...
✅ Overlay created: capture_overlay.png
5. Combining overlay with input image...
✅ Combined image created: capture_combined.png
============================================================
Color Camera Test Results:
============================================================
✅ Input PNG: capture_input.png
✅ Overlay PNG: capture_overlay.png
✅ Combined PNG: capture_combined.png
✅ Color camera processing: RGGB Bayer pattern
✅ Color camera functionality test completed successfully
```

## Troubleshooting

### **Common Issues**

#### **1. Bayer Pattern Not Detected**
```bash
# Check ASCOM driver properties
python -c "
import win32com.client
cam = win32com.client.Dispatch('ASCOM.QHYCCD.Camera')
print(f'SensorType: {cam.SensorType}')
print(f'IsColor: {cam.IsColor}')
"
```

#### **2. Poor Color Quality**
```python
# Try different Bayer patterns
BAYER_PATTERNS = ['RGGB', 'GRBG', 'GBRG', 'BGGR']
for pattern in BAYER_PATTERNS:
    # Test each pattern
    result = debayer_image(raw_data, pattern)
```

#### **3. Plate-Solving Fails with Color Data**
```python
# Ensure green channel extraction
if is_color_camera:
    # Use green channel for plate-solving
    plate_solve_data = extract_green_channel(color_data)
else:
    # Use full data for monochrome
    plate_solve_data = mono_data
```

### **Debug Information**

Enable debug logging for detailed color processing information:

```bash
python test_fits_platesolve_overlay.py capture.fits --color-test --debug
```

**Debug Output:**
```
DEBUG: ASCOM image data type: uint16, shape: (3194, 4788)
DEBUG: Detected color camera with Bayer pattern: RGGB
DEBUG: Successfully debayered image with RGGB pattern
DEBUG: FITS data: dtype=int16, shape=(3194, 4788), min=0, max=32767
INFO: Using green channel for plate-solving (color camera)
```

## Integration with Main Application

### **Overlay Runner**
The main `overlay_runner.py` automatically handles color cameras:

```python
# Automatic color detection and processing
video_capture = VideoCapture(config=config, logger=logger)
# Color handling is automatic
```

### **Dual Format Saving**
Color cameras save both formats:

1. **FITS**: 2D green channel for plate-solving
2. **PNG**: Full color for display

```python
# Automatic dual format saving
if is_color_camera:
    save_fits(green_channel_data)  # For plate-solving
    save_png(full_color_data)      # For display
```

## Performance Considerations

### **Processing Speed**
- **Plate-Solving**: Uses 2D green channel (faster)
- **Display**: Full color debayering (slower but better quality)

### **Memory Usage**
- **Raw Data**: 16-bit per pixel
- **Debayered**: 48-bit per pixel (3x memory)
- **FITS Storage**: 16-bit per pixel (green channel only)

### **Storage Requirements**
- **FITS Files**: Same size as monochrome
- **PNG Files**: 3x larger than monochrome

## Best Practices

### **1. Camera Setup**
```python
# Always check sensor type after connection
if ascom_camera.sensor_type:
    print(f"Bayer pattern: {ascom_camera.sensor_type}")
else:
    print("Monochrome camera detected")
```

### **2. FITS Processing**
```python
# Use appropriate processing for each use case
if is_color_camera:
    # Plate-solving: green channel
    plate_solve_data = extract_green_channel(color_data)
    # Display: full color
    display_data = debayer_full_color(color_data)
```

### **3. Testing**
```bash
# Always test with --color-test for color cameras
python test_fits_platesolve_overlay.py capture.fits --color-test --debug
```

## Summary

The OST Telescope Streaming system provides comprehensive color camera support:

✅ **Automatic Detection**: Bayer pattern detection from ASCOM drivers
✅ **FITS Integration**: Proper color information in FITS headers
✅ **Plate-Solving**: Optimized green channel processing
✅ **Display Quality**: Full color debayering for display
✅ **Dual Format**: FITS for processing, PNG for display
✅ **Testing Tools**: Dedicated color camera test functionality

This ensures that color cameras work seamlessly with the existing plate-solving and overlay generation system while maintaining optimal performance and quality. 