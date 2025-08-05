#!/usr/bin/env python3
"""
Test script to verify FITS saving functionality.
This script tests if Astropy is available and can create FITS files.
"""

import sys
import os
import numpy as np
from pathlib import Path

def test_astropy_import():
    """Test if Astropy can be imported."""
    try:
        import astropy.io.fits as fits
        from astropy.time import Time
        print("✅ Astropy imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Astropy import failed: {e}")
        return False

def test_fits_creation():
    """Test if FITS files can be created."""
    try:
        import astropy.io.fits as fits
        from astropy.time import Time
        
        # Create test data
        test_data = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)
        
        # Create FITS header
        header = fits.Header()
        header['NAXIS'] = 2
        header['NAXIS1'] = 100
        header['NAXIS2'] = 100
        header['BITPIX'] = 16
        header['BZERO'] = 0
        header['BSCALE'] = 1
        header['CAMERA'] = 'Test'
        header['DATE-OBS'] = Time.now().isot
        
        # Create FITS file
        test_filename = "test_fits.fits"
        hdu = fits.PrimaryHDU(test_data, header=header)
        hdu.writeto(test_filename, overwrite=True)
        
        # Verify file was created
        if os.path.exists(test_filename):
            file_size = os.path.getsize(test_filename)
            print(f"✅ FITS file created successfully: {test_filename} (size: {file_size} bytes)")
            
            # Clean up
            os.remove(test_filename)
            return True
        else:
            print(f"❌ FITS file was not created: {test_filename}")
            return False
            
    except Exception as e:
        print(f"❌ FITS creation failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def test_video_capture_fits():
    """Test the VideoCapture FITS saving functionality."""
    try:
        # Add the code directory to the path
        sys.path.insert(0, str(Path(__file__).parent / "code"))
        
        from video_capture import VideoCapture
        from config_manager import ConfigManager
        
        # Create a minimal config for testing
        test_config = {
            'camera': {
                'camera_type': 'alpaca',
                'alpaca': {
                    'host': 'localhost',
                    'port': 11111,
                    'device_id': 0
                }
            },
            'video': {
                'output_dir': 'test_output'
            }
        }
        
        # Create test config file
        import yaml
        test_config_file = "test_config.yaml"
        with open(test_config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        # Initialize VideoCapture
        config = ConfigManager(test_config_file)
        video_capture = VideoCapture(config)
        
        # Create test data
        test_data = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)
        
        # Test FITS saving
        test_filename = "test_video_capture.fits"
        status = video_capture._save_fits_unified(test_data, test_filename)
        
        if status.is_success:
            print(f"✅ VideoCapture FITS saving successful: {test_filename}")
            if os.path.exists(test_filename):
                file_size = os.path.getsize(test_filename)
                print(f"   File size: {file_size} bytes")
                os.remove(test_filename)
            return True
        else:
            print(f"❌ VideoCapture FITS saving failed: {status.message}")
            return False
            
    except Exception as e:
        print(f"❌ VideoCapture test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
    finally:
        # Clean up
        if os.path.exists("test_config.yaml"):
            os.remove("test_config.yaml")

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