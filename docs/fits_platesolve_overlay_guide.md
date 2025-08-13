# FITS Plate-Solving and Overlay Generation Guide

## Overview

The `test_fits_platesolve_overlay.py` script provides a comprehensive solution for processing FITS files with automated plate-solving and overlay generation. This tool is perfect for processing astronomical images and creating annotated overlays.

## Features

### 🔍 **FITS Parameter Extraction**
- **Automatic extraction** of all plate-solving parameters from FITS headers
- **Telescope parameters**: Focal length, aperture, sensor dimensions
- **Camera parameters**: Pixel size, binning, exposure time, gain
- **Coordinate extraction**: RA/Dec from various header formats
- **FOV calculation**: Automatic field of view calculation

### 🎯 **Plate-Solving**
- **Automated plate-solving** using PlateSolve 2
- **Parameter optimization** based on FITS header data
- **Coordinate validation** and error handling
- **Multiple coordinate formats** support

### 🖼️ **Image Processing**
- **FITS to PNG conversion** for display
- **Overlay generation** based on plate-solving results
- **Image combination** with overlay overlay
- **3 output formats**: Original image, overlay, combined image

## Usage

### Basic Usage

```bash
cd tests

# Process FITS file with automatic parameter extraction
python test_fits_platesolve_overlay.py capture.fits

# Specify output directory
python test_fits_platesolve_overlay.py capture.fits --output-dir my_output
```

### Advanced Usage with Parameter Overrides

```bash
# Override coordinates from FITS header
python test_fits_platesolve_overlay.py capture.fits --ra 295.1234 --dec 40.5678

# Override FOV parameters
python test_fits_platesolve_overlay.py capture.fits --fov-width 0.6 --fov-height 0.4

# Use specific configuration
python test_fits_platesolve_overlay.py capture.fits --config ../config_ost_qhy600m.yaml

# Enable debug output
python test_fits_platesolve_overlay.py capture.fits --debug
```

### Complete Example

```bash
cd tests

python test_fits_platesolve_overlay.py \
    ../plate_solve_frames/capture.fits \
    --output-dir ../fits_output \
    --config ../config_ost_qhy600m.yaml \
    --debug
```

## Command Line Options

### Required Arguments
- **`fits_file`**: Path to input FITS file

### Optional Arguments
- **`--output-dir, -o`**: Output directory for PNG files (default: `fits_output`)
- **`--ra`**: RA in degrees (overrides FITS header)
- **`--dec`**: Dec in degrees (overrides FITS header)
- **`--fov-width`**: FOV width in degrees (overrides FITS header)
- **`--fov-height`**: FOV height in degrees (overrides FITS header)

### Standard Options
- **`--config, -c`**: Configuration file path
- **`--verbose, -v`**: Enable verbose output
- **`--debug, -d`**: Enable debug output
- **`--quiet, -q`**: Enable quiet output

## Output Files

The script generates **3 PNG files** in the specified output directory:

### 1. **Original Image** (`{basename}_image.png`)
- **Source**: Converted from input FITS file
- **Purpose**: Display the original astronomical image
- **Format**: PNG with normalized brightness

### 2. **Overlay** (`{basename}_overlay.png`)
- **Source**: Generated overlay with astronomical objects
- **Purpose**: Show identified objects and annotations
- **Format**: PNG with transparent background

### 3. **Combined Image** (`{basename}_combined.png`)
- **Source**: Original image + overlay
- **Purpose**: Final annotated image for display
- **Format**: PNG with overlay applied

## FITS Header Extraction

### Supported Header Keywords

#### **Image Information**
- `NAXIS1`, `NAXIS2`: Image dimensions
- `BITPIX`: Data type information

#### **Telescope Parameters**
- `FOCALLEN`: Focal length in mm
- `APERTURE`: Aperture diameter in mm

#### **Camera Parameters**
- `PIXSIZE1`, `PIXSIZE2`: Pixel size in mm
- `XBINNING`, `YBINNING`: Binning factors
- `EXPTIME`: Exposure time in seconds
- `GAIN`: Camera gain setting

#### **Coordinates** (Multiple formats supported)
- `RA`, `DEC`: Basic coordinates
- `CRVAL1`, `CRVAL2`: World coordinate system
- `OBJCTRA`, `OBJCTDEC`: Object coordinates

#### **Additional Information**
- `DATE-OBS`: Observation date/time
- `OBJECT`: Object name
- `INSTRUME`: Instrument name

### Coordinate Format Support

The script supports multiple coordinate formats:

#### **RA Formats**
- **Decimal degrees**: `295.1234`
- **HH:MM:SS**: `19:40:29.6`
- **HH MM SS**: `19 40 29.6`

#### **Dec Formats**
- **Decimal degrees**: `40.5678`
- **DD:MM:SS**: `+40:34:04.1`
- **DD MM SS**: `+40 34 04.1`

## Processing Steps

### Step 1: Parameter Extraction
```python
# Extract all parameters from FITS header
parameters = extract_fits_parameters(fits_path, logger)
```

**Extracts:**
- Image dimensions
- Telescope parameters
- Camera parameters
- Coordinates (if available)
- Calculates FOV

### Step 2: FITS to PNG Conversion
```python
# Convert FITS to displayable PNG
convert_fits_to_png(fits_path, png_image_path, logger)
```

**Process:**
- Read FITS data
- Normalize to 0-255 range
- Save as PNG

### Step 3: Plate-Solving
```python
# Perform automated plate-solving
plate_solve_result = perform_plate_solving(fits_path, parameters, config, logger)
```

**Uses:**
- PlateSolve 2 automation
- Extracted parameters
- FITS file as input

### Step 4: Overlay Generation
```python
# Generate astronomical overlay
generate_overlay(plate_solve_result, parameters, png_overlay_path, config, logger)
```

**Creates:**
- Object markers
- Labels and annotations
- Coordinate grid

### Step 5: Image Combination
```python
# Combine overlay with original image
combine_overlay_with_image(png_image_path, png_overlay_path, png_combined_path, logger)
```

**Process:**
- Overlay overlay on original image
- Preserve image quality
- Create final annotated image

## Configuration

### Required Configuration

The script uses the standard configuration system:

```yaml
# Plate-solving configuration
plate_solve:
  platesolve2:
    executable_path: "C:/Program Files (x86)/PlaneWave Instruments/PWI3/PlateSolve2/PlateSolve2.exe"
    working_directory: "C:/Users/BP34_Admin/AppData/Local/Temp"
    timeout: 60
    verbose: true

# Overlay configuration
overlay:
  field_of_view: 1.5
  magnitude_limit: 9.0
  image_size: [1920, 1080]
```

### Configuration File Examples

#### **Default Configuration**
```bash
python test_fits_platesolve_overlay.py capture.fits
# Uses config.yaml
```

#### **QHY Camera Configuration**
```bash
python test_fits_platesolve_overlay.py capture.fits --config ../config_ost_qhy600m.yaml
```

#### **Custom Configuration**
```bash
python test_fits_platesolve_overlay.py capture.fits --config my_config.yaml
```

## Examples

### Example 1: Basic Processing
```bash
cd tests
python test_fits_platesolve_overlay.py ../plate_solve_frames/capture.fits
```

**Output:**
```
fits_output/
├── capture_image.png
├── capture_overlay.png
└── capture_combined.png
```

### Example 2: With Coordinate Override
```bash
cd tests
python test_fits_platesolve_overlay.py capture.fits \
    --ra 295.1234 \
    --dec 40.5678 \
    --fov-width 0.6 \
    --fov-height 0.4
```

### Example 3: Debug Mode
```bash
cd tests
python test_fits_platesolve_overlay.py capture.fits \
    --config ../config_ost_qhy600m.yaml \
    --debug \
    --output-dir debug_output
```

## Troubleshooting

### Common Issues

#### **FITS File Not Found**
```bash
# Check file path
ls -la capture.fits

# Use absolute path if needed
python test_fits_platesolve_overlay.py /full/path/to/capture.fits
```

#### **Plate-Solving Fails**
```bash
# Check PlateSolve 2 installation
python test_fits_platesolve_overlay.py capture.fits --debug

# Verify FITS format
python test_fits_platesolve_overlay.py capture.fits --ra 180 --dec 0
```

#### **Parameter Extraction Issues**
```bash
# Use manual parameter override
python test_fits_platesolve_overlay.py capture.fits \
    --ra 295.1234 \
    --dec 40.5678 \
    --fov-width 0.6 \
    --fov-height 0.4
```

#### **Output Directory Issues**
```bash
# Create output directory manually
mkdir -p my_output
python test_fits_platesolve_overlay.py capture.fits --output-dir my_output
```

### Debug Output

Enable debug mode for detailed information:

```bash
python test_fits_platesolve_overlay.py capture.fits --debug
```

**Shows:**
- FITS header extraction details
- Plate-solving parameters
- Processing steps
- Error details

## Integration with Main Application

### Workflow Integration

This test can be integrated into the main application workflow:

1. **Capture FITS** with `overlay_runner.py`
2. **Process FITS** with `test_fits_platesolve_overlay.py`
3. **Use results** for further analysis

### Batch Processing

For multiple FITS files:

```bash
#!/bin/bash
cd tests

for fits_file in ../plate_solve_frames/*.fits; do
    echo "Processing $fits_file..."
    python test_fits_platesolve_overlay.py "$fits_file" \
        --output-dir "../fits_output/$(basename "$fits_file" .fits)" \
        --config ../config_ost_qhy600m.yaml
done
```

## Requirements

### Python Dependencies
- `astropy`: FITS file reading
- `opencv-python`: Image processing
- `numpy`: Numerical operations
- `matplotlib`: Image display (optional)

### External Software
- **PlateSolve 2**: For plate-solving functionality
- **ASCOM Platform**: For telescope integration (optional)

### System Requirements
- **Windows**: Full functionality
- **Linux/macOS**: Limited to OpenCV cameras

## Summary

The `test_fits_platesolve_overlay.py` script provides a complete solution for:

✅ **FITS file processing** with automatic parameter extraction
✅ **Plate-solving** using PlateSolve 2
✅ **Overlay generation** with astronomical annotations
✅ **3 output formats** for different use cases
✅ **Flexible configuration** and parameter overrides
✅ **Comprehensive error handling** and debugging

This tool is essential for processing astronomical images and creating professional overlays for telescope streaming and analysis.
