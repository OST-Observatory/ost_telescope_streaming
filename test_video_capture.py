#!/usr/bin/env python3
"""
Test script for video capture from telescope stream.
Tests camera availability and captures a single frame.
"""

import cv2
import argparse
import sys
import time
from pathlib import Path

def list_cameras():
    """List all available camera devices."""
    print("Scanning for available cameras...")
    
    available_cameras = []
    # Test first 10 camera indices
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Get camera info
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            print(f"Camera {i}: {width}x{height} @ {fps:.1f}fps")
            available_cameras.append(i)
            cap.release()
        else:
            print(f"Camera {i}: Not available")
    
    if not available_cameras:
        print("No cameras found!")
        return []
    
    print(f"\nFound {len(available_cameras)} camera(s): {available_cameras}")
    return available_cameras

def test_camera_access(camera_index):
    """Test if camera is accessible (not blocked by other applications)."""
    print(f"Testing access to camera {camera_index}...")
    
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Camera {camera_index} is not accessible")
        return False
    
    # Try to read a frame
    ret, frame = cap.read()
    if not ret:
        print(f"Camera {camera_index} is accessible but cannot read frames (possibly in use by another application)")
        cap.release()
        return False
    
    print(f"Camera {camera_index} is accessible and can read frames")
    cap.release()
    return True

def capture_frame(camera_index, output_path="test_frame.jpg"):
    """Capture a single frame from the specified camera."""
    print(f"Capturing frame from camera {camera_index}...")
    
    # Test access first
    if not test_camera_access(camera_index):
        return False
    
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Failed to open camera {camera_index}")
        return False
    
    # Wait a moment for camera to stabilize
    print("Waiting for camera to stabilize...")
    time.sleep(1)
    
    # Capture frame
    ret, frame = cap.read()
    if not ret:
        print(f"Failed to capture frame from camera {camera_index}")
        cap.release()
        return False
    
    # Save frame
    output_file = Path(output_path)
    success = cv2.imwrite(str(output_file), frame)
    
    if success:
        print(f"Frame saved to: {output_file.absolute()}")
        print(f"   Frame size: {frame.shape[1]}x{frame.shape[0]} pixels")
    else:
        print(f"Failed to save frame to {output_file}")
    
    cap.release()
    return success

def main():
    parser = argparse.ArgumentParser(description="Test video capture from telescope stream")
    parser.add_argument("--list", action="store_true", help="List all available cameras")
    parser.add_argument("--camera", type=int, default=0, help="Camera index to use (default: 0)")
    parser.add_argument("--output", default="test_frame.jpg", help="Output filename (default: test_frame.jpg)")
    parser.add_argument("--test-access", action="store_true", help="Test camera access without capturing")
    
    args = parser.parse_args()
    
    if args.list:
        list_cameras()
        return
    
    if args.test_access:
        test_camera_access(args.camera)
        return
    
    # Capture frame
    success = capture_frame(args.camera, args.output)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 