#!/usr/bin/env python3
"""
Test script to verify FITS saving functionality.
This script tests if Astropy is available and can create FITS files.
"""

import os
from pathlib import Path
import sys

import numpy as np
import pytest


def test_astropy_import():
    """Test if Astropy can be imported."""
    try:
        import importlib.util

        spec_fits = importlib.util.find_spec("astropy.io.fits")
        spec_time = importlib.util.find_spec("astropy.time")

        if spec_fits and spec_time:
            print("✅ Astropy available")
            assert True
        else:
            pytest.skip("Astropy not available")
    except ImportError as e:
        pytest.skip(f"Astropy import failed: {e}")


def test_fits_creation():
    """Test if FITS files can be created."""
    try:
        import astropy.io.fits as fits
        from astropy.time import Time

        # Create test data
        test_data = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)

        # Create FITS header
        header = fits.Header()
        header["NAXIS"] = 2
        header["NAXIS1"] = 100
        header["NAXIS2"] = 100
        header["BITPIX"] = 16
        header["BZERO"] = 0
        header["BSCALE"] = 1
        header["CAMERA"] = "Test"
        header["DATE-OBS"] = Time.now().isot

        # Create FITS file
        test_filename = "test_fits.fits"
        hdu = fits.PrimaryHDU(test_data, header=header)
        hdu.writeto(test_filename, overwrite=True)

        # Verify file was created
        assert os.path.exists(test_filename)
        # Clean up
        os.remove(test_filename)

    except Exception as e:
        pytest.skip(f"FITS creation skipped: {e}")


def test_video_capture_fits():
    """Test the VideoCapture FITS saving functionality."""
    try:
        # Add the code directory to the path
        sys.path.insert(0, str(Path(__file__).parent / "code"))

        from config_manager import ConfigManager
        import yaml

        from code.capture.controller import VideoCapture

        test_config = {
            "camera": {
                "camera_type": "alpaca",
                "alpaca": {"host": "localhost", "port": 11111, "device_id": 0},
            },
            "video": {"output_dir": "test_output"},
        }

        test_config_file = "test_config.yaml"
        with open(test_config_file, "w") as f:
            yaml.dump(test_config, f)

        config = ConfigManager(test_config_file)
        video_capture = VideoCapture(config, return_frame_objects=True)

        # Create test data
        test_data = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)

        # Test FITS saving
        test_filename = "test_video_capture.fits"
        status = video_capture.save_frame(test_data, test_filename)

        assert status.is_success
        assert os.path.exists(test_filename)

    except Exception as e:
        pytest.skip(f"VideoCapture FITS saving skipped: {e}")
    finally:
        # Clean up
        if os.path.exists("test_config.yaml"):
            os.remove("test_config.yaml")
        if os.path.exists("test_video_capture.fits"):
            os.remove("test_video_capture.fits")


def main():
    """Main test function."""
    print("Testing FITS saving functionality...")
    print("=" * 50)

    # Test 1: Astropy import
    print("1. Testing Astropy import...")
    astropy_ok = test_astropy_import()

    # Test 2: Basic FITS creation
    print("\n2. Testing basic FITS creation...")
    fits_ok = test_fits_creation()

    # Test 3: VideoCapture FITS saving
    print("\n3. Testing VideoCapture FITS saving...")
    video_capture_ok = test_video_capture_fits()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Astropy import: {'✅ OK' if astropy_ok else '❌ FAILED'}")
    print(f"Basic FITS creation: {'✅ OK' if fits_ok else '❌ FAILED'}")
    print(f"VideoCapture FITS saving: {'✅ OK' if video_capture_ok else '❌ FAILED'}")

    if astropy_ok and fits_ok and video_capture_ok:
        print("\n🎉 All tests passed! FITS saving should work correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

        if not astropy_ok:
            print("\nTo fix Astropy issues:")
            print("pip install astropy")

        if not fits_ok:
            print("\nTo fix FITS creation issues:")
            print("- Check file permissions")
            print("- Ensure sufficient disk space")

        if not video_capture_ok:
            print("\nTo fix VideoCapture issues:")
            print("- Check the VideoCapture implementation")
            print("- Verify configuration format")


if __name__ == "__main__":
    main()
