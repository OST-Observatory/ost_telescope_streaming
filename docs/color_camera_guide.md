# ASCOM Color Camera Support Guide

## Overview

The OST Telescope Streaming system provides comprehensive support for ASCOM color cameras, including automatic Bayer pattern detection, debayering for display, and optimized plate-solving. This guide covers the complete color camera workflow from capture to processing.

## Automatic Detection

### **Bayer Pattern Detection**
The system automatically detects color cameras and their Bayer patterns:

```python
# Supported Bayer patterns
'RGGB'  # Red-Green-Green-Blue (most common)
'GRBG'  # Green-Red-Blue-Green
'GBRG'  # Green-Blue-Red-Green
'BGGR'  # Blue-Green-Green-Red
```

### **Detection Method**
```python
if hasattr(self.ascom_camera, 'sensor_type'):
    sensor_type = self.ascom_camera.sensor_type
    if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
        is_color_camera = True
        bayer_pattern = sensor_type
```

## Image Processing Pipeline

### **1. Raw Capture**
- ASCOM camera provides raw Bayer data
- System detects color camera and Bayer pattern
- Preserves original data for FITS files

### **2. Dual-Format Saving**
- **FITS files**: Raw Bayer data for plate-solving
- **PNG/JPG files**: Debayered color data for display

### **3. Image Orientation Correction**
- **ASCOM cameras** often have rotated images compared to other software
- **Automatic correction** applied to both FITS and PNG/JPG files
- **Transpose operation** corrects 90° rotation

```python
# Applied to both FITS and display formats
original_shape = image_array.shape
image_array = np.transpose(image_array)
self.logger.debug(f"Image orientation corrected: {original_shape} -> {image_array.shape}")
```

## FITS File Handling

### **Color Camera FITS Headers**
```python
header['COLORCAM'] = True
header['BAYERPAT'] = 'RGGB'  # or detected pattern
header['NAXIS3'] = 3  # for 3-channel images
```

### **Plate-Solving Optimization**
For plate-solving, the system extracts the **green channel** from color images:

```python
if len(image_data.shape) == 3:
    # Extract green channel for plate-solving
    image_data = image_data[:, :, 1]  # Green channel
    header['NAXIS3'] = 3  # Keep color info in header
```

**Why Green Channel?**
- Green channel has highest sensitivity
- Best signal-to-noise ratio
- Most stars visible in green wavelengths
- PlateSolve 2 prefers monochrome images

## Display Format Processing

### **Debayering Process**
```python
# Map Bayer patterns to OpenCV constants
if bayer_pattern == 'RGGB':
    bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
elif bayer_pattern == 'GRBG':
    bayer_pattern_cv2 = cv2.COLOR_BayerGR2BGR
# ... etc

# Apply debayering
color_image = cv2.cvtColor(image_array, bayer_pattern_cv2)
```

### **Color Balance**
- Automatic debayering based on detected Bayer pattern
- Conversion to BGR format for OpenCV compatibility
- Normalization for optimal display

## Configuration

### **Camera Settings**
```yaml
video:
  camera_type: ascom
  ascom:
    driver: ASCOM.QHYCCD.Camera
    exposure_time: 5.0
    gain: 1.0
    binning: 1
```

### **File Format Settings**
```yaml
video:
  file_format: png  # or jpg, fits
  save_plate_solve_frames: true
```

## Testing Color Cameras

### **Using the Test Script**
```bash
cd tests
python test_fits_platesolve_overlay.py --color-test --config ../config_ost_qhy600m.yaml
```

### **What the Test Does**
1. **Detects color camera** and Bayer pattern
2. **Saves FITS file** with proper headers
3. **Converts to PNG** with debayering
4. **Performs plate-solving** using green channel
5. **Generates overlay** with correct orientation
6. **Combines images** for final result

### **Expected Output**
```
INFO: Detected color camera with Bayer pattern: RGGB
INFO: Image orientation corrected: (4000, 6000) -> (6000, 4000)
INFO: Successfully debayered image with RGGB pattern
INFO: Plate-solving successful: RA=295.1234°, Dec=40.5678°
```

## Troubleshooting

### **Common Issues**

#### **1. Wrong Colors**
```bash
# Check Bayer pattern detection
INFO: Detected color camera with Bayer pattern: RGGB
```

**Solution**: Verify the correct Bayer pattern in camera documentation.

#### **2. Poor Plate-Solving**
```bash
# Check if green channel extraction is working
INFO: Extracting green channel for plate-solving
```

**Solution**: Ensure FITS files contain proper `COLORCAM` and `BAYERPAT` headers.

#### **3. Incorrect Orientation**
```bash
# Check orientation correction
INFO: Image orientation corrected: (4000, 6000) -> (6000, 4000)
```

**Solution**: Both FITS and PNG files should show the same orientation correction.

### **Debug Information**
```python
# Enable debug logging
logging.getLogger().setLevel(logging.DEBUG)

# Check data flow
DEBUG: ASCOM image data type: uint16, shape: (4000, 6000)
DEBUG: Image orientation corrected: (4000, 6000) -> (6000, 4000)
DEBUG: Successfully debayered image with RGGB pattern
```

## Performance Considerations

### **Memory Usage**
- **Raw Bayer data**: 2 bytes per pixel
- **Debayered color**: 6 bytes per pixel (3 channels × 2 bytes)
- **Green channel extraction**: Minimal overhead

### **Processing Time**
- **Debayering**: ~10-50ms for typical images
- **Orientation correction**: ~1-5ms
- **Green channel extraction**: ~1-2ms

### **File Sizes**
- **FITS files**: Raw Bayer data (smaller)
- **PNG files**: Debayered color data (larger)
- **Compression**: PNG provides good compression for color images

## Integration with Main Application

### **Overlay Runner**
The main application automatically handles color cameras:

```python
# Automatic detection and processing
if hasattr(self.ascom_camera, 'is_color_camera'):
    self.logger.info(f"Color camera detected: {self.ascom_camera.sensor_type}")
```

### **Plate-Solving Integration**
```python
# Automatic green channel extraction for plate-solving
# Proper FITS headers for color information
# Correct orientation for all formats
```

## Summary

The color camera support provides:

🎨 **Automatic Detection**: Recognizes color cameras and Bayer patterns
🔄 **Dual-Format Saving**: FITS for processing, PNG/JPG for display
📐 **Orientation Correction**: Consistent orientation across all formats
🔍 **Optimized Plate-Solving**: Green channel extraction for best results
⚡ **Efficient Processing**: Minimal overhead with maximum compatibility

This ensures that color cameras work seamlessly with the entire system while maintaining optimal performance for both plate-solving and display purposes.
