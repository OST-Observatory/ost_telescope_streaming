# ASCOM Color Camera Improvements Summary

## Overview

This document summarizes the comprehensive improvements made to support ASCOM color cameras throughout the OST Telescope Streaming system. These improvements ensure that color cameras work seamlessly with plate-solving, FITS file handling, and display functionality.

## Key Improvements Made

### **1. Enhanced FITS File Handling** (`code/video_capture.py`)

#### **Color Camera Detection**
- **Automatic Bayer pattern detection** from ASCOM `SensorType` property
- **FITS header integration** with color camera information
- **Support for all major Bayer patterns**: RGGB, GRBG, GBRG, BGGR

#### **Plate-Solving Optimization**
- **Green channel extraction** for plate-solving (most sensitive for astronomy)
- **2D data conversion** for PlateSolve 2 compatibility
- **Proper FITS headers** with color camera information

#### **FITS Header Enhancements**
```python
# New color camera headers
header['COLORCAM'] = True
header['BAYERPAT'] = 'RGGB'
header['NAXIS3'] = 3  # For RGB images
```

### **2. Improved Image Conversion** (`code/video_capture.py`)

#### **Enhanced Debayering**
- **Automatic Bayer pattern detection** and application
- **Robust error handling** with fallback to grayscale
- **Support for multiple image formats** (2D, 3D, RGBA)

#### **Better Color Processing**
- **Channel-specific normalization** for better color balance
- **Proper color space conversion** (BGR ↔ RGB)
- **Fallback mechanisms** for various data types

### **3. Advanced FITS Processing** (`tests/test_fits_platesolve_overlay.py`)

#### **Color-Aware Parameter Extraction**
- **Automatic color camera detection** from FITS headers
- **Bayer pattern extraction** and validation
- **Channel count detection** and handling

#### **Enhanced PNG Conversion**
- **Color-aware FITS to PNG conversion**
- **Automatic debayering** for raw Bayer data
- **Channel-specific normalization** for better display

#### **New Color Camera Test**
- **Dedicated color camera test function** (`test_color_camera_functionality`)
- **Comprehensive color processing validation**
- **Detailed logging and debugging** for color operations

### **4. ASCOM Camera Integration** (`code/ascom_camera.py`)

#### **Sensor Type Detection**
- **Comprehensive Bayer pattern mapping** from ASCOM SensorType
- **Fallback detection methods** for various camera types
- **Robust error handling** for detection failures

#### **Debayering Support**
- **Built-in debayering functionality** with multiple patterns
- **Automatic pattern detection** and application
- **Error handling** with graceful fallbacks

## Technical Details

### **Bayer Pattern Support**

| Pattern | ASCOM SensorType | OpenCV Pattern | Common Usage |
|---------|------------------|----------------|--------------|
| RGGB | 3 | `cv2.COLOR_BayerRG2BGR` | DSLR cameras, many CCDs |
| GRBG | 4 | `cv2.COLOR_BayerGR2BGR` | Some CCD cameras |
| GBRG | 5 | `cv2.COLOR_BayerGB2BGR` | Specialized cameras |
| BGGR | 6 | `cv2.COLOR_BayerBG2BGR` | Some CCD cameras |

### **Image Processing Pipeline**

#### **1. Raw Capture**
```python
# ASCOM provides raw Bayer data
raw_data = ascom_camera.get_image()
```

#### **2. FITS Storage (Plate-Solving)**
```python
# Extract green channel for plate-solving
if is_color_camera:
    green_channel = image_data[:, :, 1]
    fits_data = green_channel  # 2D data
```

#### **3. Display Conversion**
```python
# Full debayering for display
if is_color_camera and bayer_pattern:
    display_data = cv2.cvtColor(raw_data, bayer_pattern_cv2)
```

#### **4. Plate-Solving**
```python
# Use 2D green channel data
plate_solve_result = solve_plate(fits_data)
```

### **FITS File Structure**

#### **Color Camera FITS Headers**
```python
# Required headers for color cameras
header['COLORCAM'] = True
header['BAYERPAT'] = 'RGGB'
header['NAXIS3'] = 3
header['IMAGETYP'] = 'LIGHT'
```

#### **Data Organization**
- **Plate-Solving**: 2D green channel data
- **Display**: Full 3D RGB data (if available)
- **Storage**: Optimized for each use case

## Testing and Validation

### **New Test Functionality**

#### **Color Camera Test**
```bash
# Dedicated color camera test
python test_fits_platesolve_overlay.py capture.fits --color-test

# Standard test (works with both mono and color)
python test_fits_platesolve_overlay.py capture.fits
```

#### **Test Output**
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

### **Debug Information**
```bash
# Enable detailed debugging
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

## Performance Optimizations

### **Processing Speed**
- **Plate-Solving**: Uses 2D green channel (faster processing)
- **Display**: Full color debayering (optimal quality)
- **Memory**: Efficient data handling for each use case

### **Storage Efficiency**
- **FITS Files**: Same size as monochrome (green channel only)
- **PNG Files**: 3x larger than monochrome (full color)
- **Dual Format**: Optimized for each purpose

### **Memory Usage**
- **Raw Data**: 16-bit per pixel
- **Debayered**: 48-bit per pixel (3x memory)
- **FITS Storage**: 16-bit per pixel (green channel only)

## Integration Points

### **Main Application** (`overlay_runner.py`)
- **Automatic color detection** and handling
- **Seamless integration** with existing workflow
- **No configuration changes** required

### **Video Processing** (`video_processor.py`)
- **Dual format saving** for color cameras
- **Automatic format selection** based on use case
- **Consistent interface** for both mono and color

### **Plate-Solving** (`plate_solver.py`)
- **Optimized for 2D data** (green channel)
- **Maintains compatibility** with existing catalogs
- **Improved performance** for color cameras

## Configuration

### **Automatic Configuration**
```yaml
# No changes required - auto-detection works
video:
  camera_type: ascom
  ascom:
    ascom_driver: ASCOM.QHYCCD.Camera
```

### **Manual Override** (if needed)
```yaml
# Manual Bayer pattern override
video:
  ascom:
    bayer_pattern: RGGB  # Manual override
```

## Benefits

### **For Users**
- ✅ **Seamless Integration**: Color cameras work out-of-the-box
- ✅ **Optimal Performance**: Green channel for plate-solving
- ✅ **High Quality Display**: Full color debayering
- ✅ **No Configuration**: Automatic detection and handling

### **For Developers**
- ✅ **Extensible Design**: Easy to add new Bayer patterns
- ✅ **Robust Error Handling**: Graceful fallbacks
- ✅ **Comprehensive Testing**: Dedicated test functionality
- ✅ **Clear Documentation**: Detailed guides and examples

### **For System**
- ✅ **Backward Compatibility**: Works with existing monochrome cameras
- ✅ **Performance Optimized**: Efficient processing for each use case
- ✅ **Storage Efficient**: Optimized file formats
- ✅ **Maintainable Code**: Clear separation of concerns

## Future Enhancements

### **Planned Improvements**
1. **Additional Bayer Patterns**: Support for more specialized patterns
2. **Advanced Color Processing**: Histogram equalization, color balance
3. **Multi-Channel Support**: Support for more than 3 channels
4. **Performance Optimization**: GPU acceleration for debayering

### **Extensibility**
- **Modular Design**: Easy to add new color processing algorithms
- **Plugin Architecture**: Support for custom debayering methods
- **Configuration Driven**: Flexible pattern detection and handling

## Summary

The ASCOM color camera improvements provide:

🎯 **Comprehensive Support**: All major Bayer patterns supported
🎯 **Automatic Detection**: No manual configuration required
🎯 **Optimal Performance**: Green channel for plate-solving, full color for display
🎯 **Robust Error Handling**: Graceful fallbacks and debugging
🎯 **Extensive Testing**: Dedicated test functionality with detailed output
🎯 **Clear Documentation**: Complete guides and examples

These improvements ensure that color cameras work seamlessly with the existing plate-solving and overlay generation system while maintaining optimal performance and quality for both processing and display purposes.
