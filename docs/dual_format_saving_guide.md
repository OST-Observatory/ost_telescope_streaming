# Dual-Format Saving System for ASCOM Cameras

## Overview

The OST Telescope Streaming system now supports **dual-format saving** for ASCOM cameras, providing both:

1. **FITS files** - For plate-solving and astronomical processing
2. **Display format files** (PNG/JPG) - For viewing and display purposes

## How It Works

### ASCOM Cameras

When using ASCOM cameras, the system automatically saves **two files** for each capture:

1. **FITS file** (`capture_XXXX.fits`) - Always saved for plate-solving
2. **Display file** (`capture_XXXX.png`) - Saved if `file_format` is not FITS

### Non-ASCOM Cameras

For OpenCV cameras, only the configured `file_format` is saved.

## Configuration

### Video Configuration

```yaml
video:
  # Frame saving settings
  file_format: "png"  # Display format (png, jpg, tiff, etc.)

  # ASCOM camera settings
  ascom:
    ascom_driver: "ASCOM.QHYCCD.Camera"
    exposure_time: 0.1
    gain: 1.0
    binning: 2
```

### File Naming

Files are named using the pattern:
- Base: `capture`
- Optional timestamp: `_YYYYMMDD_HHMMSS`
- Optional counter: `_0001`
- Extension: `.fits` and `.png`

Examples:
- `capture.fits` + `capture.png`
- `capture_20250727_143022.fits` + `capture_20250727_143022.png`
- `capture_0001.fits` + `capture_0001.png`

## Use Cases

### Plate-Solving
- **FITS files** are used for plate-solving (optimal format)
- Contains full astronomical data and headers
- Preserves original ASCOM image data

### Display and Viewing
- **PNG/JPG files** are used for display
- Converted to standard image format
- Suitable for web browsers, image viewers, etc.

### Processing Pipeline
- **FITS files** can be used for:
  - Astrometric calibration
  - Photometric analysis
  - Image stacking
  - Scientific processing

## Configuration Examples

### Example 1: FITS + PNG
```yaml
video:
  file_format: "png"  # Display format
  # FITS is always saved for ASCOM cameras
```

**Result:**
- `capture.fits` (for plate-solving)
- `capture.png` (for display)

### Example 2: FITS Only
```yaml
video:
  file_format: "fits"  # Both formats are FITS
```

**Result:**
- `capture.fits` (used for both plate-solving and display)

### Example 3: FITS + JPG
```yaml
video:
  file_format: "jpg"  # Display format
```

**Result:**
- `capture.fits` (for plate-solving)
- `capture.jpg` (for display)

## Benefits

1. **Optimal Plate-Solving**: FITS format provides best results
2. **Easy Viewing**: PNG/JPG files work in any image viewer
3. **Data Preservation**: Original ASCOM data preserved in FITS
4. **Flexibility**: Choose display format based on needs
5. **Compatibility**: Works with existing astronomical software

## File Locations

Files are saved in the configured `plate_solve_dir`:
- Default: `plate_solve_frames/`
- Configurable in `plate_solve.plate_solve_dir`

## Logging

The system logs both file saves:
```
2025-07-27 14:30:22 - INFO - FITS frame saved: plate_solve_frames/capture.fits
2025-07-27 14:30:22 - INFO - Display frame saved: plate_solve_frames/capture.png
```

## Troubleshooting

### FITS File Not Saved
- Check ASCOM camera connection
- Verify exposure settings
- Check disk space

### Display File Not Saved
- Verify `file_format` is not "fits"
- Check OpenCV conversion
- Verify file permissions

### Plate-Solving Issues
- Ensure FITS file exists
- Check FITS file format
- Verify plate-solving configuration
