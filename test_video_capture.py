#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple video capture test script
"""

import cv2
import sys
import os

def list_cameras():
    """List available camera devices"""
    print("Available camera devices:")
    available_cameras = []
    
    for i in range(10):  # Check first 10 indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                print(f"  Camera {i}: {width}x{height} @ {fps:.1f} fps")
                available_cameras.append(i)
            cap.release()
        else:
            print(f"  Camera {i}: Not available")
    
    return available_cameras

def capture_frame(camera_index=0, output_file="captured_frame.jpg"):
    """Capture a single frame from the specified camera"""
    print(f"Attempting to capture frame from camera {camera_index}...")
    
    # Open camera
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_index}")
        return False
    
    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Camera opened: {width}x{height} @ {fps:.1f} fps")
    
    # Capture frame
    ret, frame = cap.read()
    
    if not ret:
        print("Error: Could not capture frame")
        cap.release()
        return False
    
    # Save frame
    success = cv2.imwrite(output_file, frame)
    
    if success:
        print(f"Frame saved as {output_file}")
        print(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
    else:
        print(f"Error: Could not save frame to {output_file}")
    
    # Release camera
    cap.release()
    
    return success

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple video capture test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--output", type=str, default="captured_frame.jpg", help="Output file (default: captured_frame.jpg)")
    parser.add_argument("--list", action="store_true", help="List available cameras")
    
    args = parser.parse_args()
    
    if args.list:
        list_cameras()
        return
    
    print("Video Capture Test")
    print("=" * 30)
    
    # List cameras first
    available_cameras = list_cameras()
    
    if not available_cameras:
        print("No cameras found!")
        return
    
    if args.camera not in available_cameras:
        print(f"Warning: Camera {args.camera} not in available cameras: {available_cameras}")
        print("Trying anyway...")
    
    # Capture frame
    success = capture_frame(args.camera, args.output)
    
    if success:
        print("Video capture test completed successfully!")
    else:
        print("Video capture test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 