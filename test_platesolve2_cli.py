#!/usr/bin/env python3
"""
Test script to find the correct command line parameters for PlateSolve 2.
"""

import subprocess
import sys
import os
from pathlib import Path

def test_platesolve2_help():
    """Test different help commands for PlateSolve 2."""
    platesolve2_path = r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\PlateSolve2.exe"
    
    if not os.path.exists(platesolve2_path):
        print(f"PlateSolve 2 not found at: {platesolve2_path}")
        return
    
    print("Testing PlateSolve 2 command line options...")
    
    # Test different help commands
    help_commands = [
        ["--help"],
        ["-h"],
        ["/help"],
        ["/h"],
        ["help"],
        ["?"],
        ["/?"],
        ["--version"],
        ["-v"],
        ["/version"],
        ["/v"]
    ]
    
    for help_cmd in help_commands:
        cmd = [platesolve2_path] + help_cmd
        print(f"\nTesting: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            print(f"Return code: {result.returncode}")
            if result.stdout:
                print(f"STDOUT: {result.stdout[:200]}...")
            if result.stderr:
                print(f"STDERR: {result.stderr[:200]}...")
                
        except subprocess.TimeoutExpired:
            print("Timeout")
        except Exception as e:
            print(f"Error: {e}")

def test_platesolve2_with_image():
    """Test PlateSolve 2 with an actual image file."""
    platesolve2_path = r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\PlateSolve2.exe"
    
    # Test image path (you can change this)
    test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
    
    if not os.path.exists(test_image):
        print(f"Test image not found: {test_image}")
        return
    
    print(f"\nTesting PlateSolve 2 with image: {test_image}")
    
    # Test different command formats
    test_commands = [
        # Format 1: image_path results_path
        [platesolve2_path, test_image, "test_results.txt"],
        
        # Format 2: -i image_path -o results_path
        [platesolve2_path, "-i", test_image, "-o", "test_results.txt"],
        
        # Format 3: --input image_path --output results_path
        [platesolve2_path, "--input", test_image, "--output", "test_results.txt"],
        
        # Format 4: /i image_path /o results_path
        [platesolve2_path, "/i", test_image, "/o", "test_results.txt"],
        
        # Format 5: Just image path
        [platesolve2_path, test_image],
    ]
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n--- Test {i}: {' '.join(cmd)} ---")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            print(f"Return code: {result.returncode}")
            if result.stdout:
                print(f"STDOUT: {result.stdout}")
            if result.stderr:
                print(f"STDERR: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("Timeout - this might be normal if PlateSolve 2 opens GUI")
        except Exception as e:
            print(f"Error: {e}")

def test_platesolve2_silent():
    """Test if PlateSolve 2 can run silently."""
    platesolve2_path = r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\PlateSolve2.exe"
    test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
    
    if not os.path.exists(test_image):
        print(f"Test image not found: {test_image}")
        return
    
    print(f"\nTesting silent mode with image: {test_image}")
    
    # Test with different silent flags
    silent_commands = [
        [platesolve2_path, test_image, "test_results.txt", "--silent"],
        [platesolve2_path, test_image, "test_results.txt", "-s"],
        [platesolve2_path, test_image, "test_results.txt", "/silent"],
        [platesolve2_path, test_image, "test_results.txt", "/s"],
        [platesolve2_path, test_image, "test_results.txt", "--batch"],
        [platesolve2_path, test_image, "test_results.txt", "-b"],
        [platesolve2_path, test_image, "test_results.txt", "/batch"],
        [platesolve2_path, test_image, "test_results.txt", "/b"],
    ]
    
    for i, cmd in enumerate(silent_commands, 1):
        print(f"\n--- Silent Test {i}: {' '.join(cmd)} ---")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            print(f"Return code: {result.returncode}")
            if result.stdout:
                print(f"STDOUT: {result.stdout}")
            if result.stderr:
                print(f"STDERR: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("Timeout - this might be normal if PlateSolve 2 opens GUI")
        except Exception as e:
            print(f"Error: {e}")

def main():
    """Main test function."""
    print("PlateSolve 2 Command Line Test")
    print("=" * 50)
    
    # Test help commands
    test_platesolve2_help()
    
    # Test with actual image
    test_platesolve2_with_image()
    
    # Test silent mode
    test_platesolve2_silent()
    
    print("\n" + "=" * 50)
    print("Test completed.")
    print("\nNote: If PlateSolve 2 opens a GUI window, the command line interface")
    print("might not be fully supported. You may need to use a different approach.")

if __name__ == "__main__":
    main() 