#!/usr/bin/env python3
"""
Test script to debug image orientation issues with ASCOM cameras.
This script helps identify if the rotation is being applied correctly.
"""

import sys
import os
import logging
import numpy as np
import cv2
from pathlib import Path

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from test_utils import get_test_config, setup_logging
from video_capture import VideoCapture

def test_image_orientation():
    """Test image orientation with ASCOM camera."""
    
    # Setup logging
    logger = setup_logging()
    logger.info("Testing image orientation with ASCOM camera")
    
    # Get configuration
    config = get_test_config()
    
    # Create video capture
    video_capture = VideoCapture(config=config, logger=logger, return_frame_objects=True)
    
    # Connection is performed during VideoCapture initialization now
    logger.info("VideoCapture initialized (connection handled internally)")
    
    # Get camera info via adapter if available
    try:
        if hasattr(video_capture, 'camera') and video_capture.camera and hasattr(video_capture.camera, 'get_camera_info'):
            info_status = video_capture.camera.get_camera_info()
            if getattr(info_status, 'is_success', False):
                logger.info(f"Camera info: {info_status.data}")
            else:
                logger.info("Camera info not available")
        else:
            logger.info("Camera adapter does not provide get_camera_info()")
    except Exception as e:
        logger.info(f"Camera info retrieval skipped: {e}")
    
    # Capture a single frame
    logger.info("Capturing single frame...")
    capture_status = video_capture.capture_single_frame_ascom(
        exposure_time_s=2.0,
        gain=1.0,
        binning=1
    )
    
    if not capture_status.is_success:
        logger.error(f"Failed to capture frame: {capture_status.message}")
        return False
    
    logger.info("Frame captured successfully")
    
    # Get the raw image data
    raw_image_data = capture_status.data
    logger.info(f"Raw image data shape: {raw_image_data.shape}")
    logger.info(f"Raw image data type: {raw_image_data.dtype}")
    
    # Test the conversion process step by step
    logger.info("Testing conversion process...")
    
    # Step 1: Convert to numpy array
    image_array = np.array(raw_image_data)
    logger.info(f"Step 1 - Numpy array shape: {image_array.shape}")
    
    # Step 2: Check if it's a color camera
    is_color_camera = False
    bayer_pattern = None
    
    if hasattr(video_capture.ascom_camera, 'sensor_type'):
        sensor_type = video_capture.ascom_camera.sensor_type
        if sensor_type in ['RGGB', 'GRBG', 'GBRG', 'BGGR']:
            is_color_camera = True
            bayer_pattern = sensor_type
            logger.info(f"Step 2 - Detected color camera with Bayer pattern: {bayer_pattern}")
        else:
            logger.info(f"Step 2 - Monochrome camera detected")
    else:
        logger.info("Step 2 - Could not determine camera type")
    
    # Step 3: Apply debayering if needed
    if is_color_camera and bayer_pattern:
        if bayer_pattern == 'RGGB':
            bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
        elif bayer_pattern == 'GRBG':
            bayer_pattern_cv2 = cv2.COLOR_BayerGR2BGR
        elif bayer_pattern == 'GBRG':
            bayer_pattern_cv2 = cv2.COLOR_BayerGB2BGR
        elif bayer_pattern == 'BGGR':
            bayer_pattern_cv2 = cv2.COLOR_BayerBG2BGR
        else:
            bayer_pattern_cv2 = cv2.COLOR_BayerRG2BGR
        
        try:
            result_image = cv2.cvtColor(image_array, bayer_pattern_cv2)
            logger.info(f"Step 3 - Debayered image shape: {result_image.shape}")
        except Exception as e:
            logger.error(f"Step 3 - Debayering failed: {e}")
            return False
    else:
        # For monochrome cameras
        if len(image_array.shape) == 2:
            result_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            logger.info(f"Step 3 - Converted monochrome to BGR shape: {result_image.shape}")
        else:
            result_image = image_array
            logger.info(f"Step 3 - Using existing image shape: {result_image.shape}")
    
    # Step 4: Apply orientation correction
    original_shape = result_image.shape
    result_image = np.transpose(result_image, (1, 0, 2))  # Transpose only spatial dimensions
    logger.info(f"Step 4 - Orientation corrected: {original_shape} -> {result_image.shape}")
    
    # Save both versions for comparison
    output_dir = Path("test_orientation_output")
    output_dir.mkdir(exist_ok=True)
    
    # Save original (before rotation)
    original_filename = output_dir / "original_before_rotation.png"
    cv2.imwrite(str(original_filename), np.transpose(result_image, (1, 0, 2)))  # Transpose back
    logger.info(f"Saved original (before rotation): {original_filename}")
    
    # Save rotated (after rotation)
    rotated_filename = output_dir / "rotated_after_rotation.png"
    cv2.imwrite(str(rotated_filename), result_image)
    logger.info(f"Saved rotated (after rotation): {rotated_filename}")
    
    # Test the full conversion method
    logger.info("Testing full conversion method...")
    converted_image = video_capture._convert_to_opencv(raw_image_data)
    
    if converted_image is not None:
        full_conversion_filename = output_dir / "full_conversion.png"
        cv2.imwrite(str(full_conversion_filename), converted_image)
        logger.info(f"Saved full conversion result: {full_conversion_filename}")
        logger.info(f"Full conversion shape: {converted_image.shape}")
    else:
        logger.error("Full conversion failed")
        return False
    
    # Test saving through the save_frame method
    logger.info("Testing save_frame method...")
    save_status = video_capture.save_frame(raw_image_data, str(output_dir / "save_frame_test.png"))
    
    if save_status.is_success:
        logger.info(f"Save frame successful: {save_status.data}")
    else:
        logger.error(f"Save frame failed: {save_status.message}")
    
    # Disconnect
    video_capture.disconnect()
    
    logger.info("=" * 60)
    logger.info("ORIENTATION TEST COMPLETE")
    logger.info("=" * 60)
    logger.info("Check the following files in test_orientation_output/:")
    logger.info("1. original_before_rotation.png - Before rotation")
    logger.info("2. rotated_after_rotation.png - After rotation")
    logger.info("3. full_conversion.png - Full conversion result")
    logger.info("4. save_frame_test.png - Save frame result")
    logger.info("=" * 60)
    logger.info("Compare these files to see if rotation is working correctly.")
    logger.info("The rotated version should have the long side horizontal.")
    
    return True

def main():
    """Main function."""
    try:
        success = test_image_orientation()
        if success:
            print("✅ Orientation test completed successfully!")
            print("Check the output files in test_orientation_output/")
        else:
            print("❌ Orientation test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error during orientation test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 