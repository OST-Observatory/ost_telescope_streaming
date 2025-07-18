#!/usr/bin/env python3
"""
Test script for working PlateSolve 2 integration.
Based on successful command: PlateSolve2.exe image_path
"""

import sys
import os
import time
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def test_platesolve2_direct():
    """Test PlateSolve 2 directly with the working command."""
    print("Testing PlateSolve 2 direct command...")
    
    import subprocess
    
    platesolve2_path = r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\PlateSolve2.exe"
    test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
    
    if not os.path.exists(platesolve2_path):
        print(f"✗ PlateSolve 2 not found: {platesolve2_path}")
        return False
    
    if not os.path.exists(test_image):
        print(f"✗ Test image not found: {test_image}")
        return False
    
    print(f"✓ PlateSolve 2 found: {platesolve2_path}")
    print(f"✓ Test image found: {test_image}")
    
    # Test the working command
    cmd = [platesolve2_path, test_image]
    print(f"Running: {' '.join(cmd)}")
    
    try:
        # Use Popen for GUI application
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for GUI to open
        time.sleep(3)
        
        # Check if process is running
        if process.poll() is None:
            print("✓ PlateSolve 2 GUI opened successfully")
            print("✓ Process is running (GUI should be visible)")
            
            # Wait a bit more to let user see the GUI
            print("Waiting 5 seconds for GUI to be visible...")
            time.sleep(5)
            
            # Terminate the process for testing
            process.terminate()
            print("✓ Process terminated for testing")
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"✗ Process finished unexpectedly")
            if stderr:
                print(f"Error: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error running PlateSolve 2: {e}")
        return False

def test_platesolve2_integration():
    """Test PlateSolve 2 integration with our module."""
    print("\nTesting PlateSolve 2 integration...")
    
    try:
        from plate_solver import PlateSolverFactory
        
        # Create solver
        solver = PlateSolverFactory.create_solver('platesolve2')
        if not solver:
            print("✗ Failed to create solver")
            return False
        
        print(f"✓ Solver created: {solver.get_name()}")
        print(f"✓ Available: {solver.is_available()}")
        
        # Test with GUI mode
        solver.use_gui_mode = True
        
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            return False
        
        print(f"Testing with image: {test_image}")
        print("This will open PlateSolve 2 GUI...")
        
        # Solve (this will open GUI)
        result = solver.solve(test_image)
        
        print(f"Result: {result}")
        
        if "GUI opened" in result.error_message:
            print("✓ GUI mode working correctly")
            return True
        else:
            print(f"✗ Unexpected result: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing integration: {e}")
        return False

def test_platesolve2_cli_mode():
    """Test PlateSolve 2 CLI mode (which also opens GUI)."""
    print("\nTesting PlateSolve 2 CLI mode...")
    
    try:
        from plate_solver import PlateSolverFactory
        
        # Create solver
        solver = PlateSolverFactory.create_solver('platesolve2')
        if not solver:
            print("✗ Failed to create solver")
            return False
        
        # Set to CLI mode (but it will still open GUI)
        solver.use_gui_mode = False
        
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            return False
        
        print(f"Testing CLI mode with image: {test_image}")
        print("Note: This will still open GUI (PlateSolve 2 behavior)")
        
        # Solve
        result = solver.solve(test_image)
        
        print(f"Result: {result}")
        
        if "GUI opened" in result.error_message:
            print("✓ CLI mode working (opens GUI as expected)")
            return True
        else:
            print(f"✗ Unexpected result: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing CLI mode: {e}")
        return False

def test_configuration():
    """Test configuration settings."""
    print("\nTesting configuration...")
    
    try:
        from config_manager import config
        
        plate_solve_config = config.get_plate_solve_config()
        
        print(f"PlateSolve 2 path: {plate_solve_config.get('platesolve2_path')}")
        print(f"Use GUI mode: {plate_solve_config.get('use_gui_mode')}")
        print(f"Working directory: {plate_solve_config.get('working_directory')}")
        
        # Check if path exists
        platesolve2_path = plate_solve_config.get('platesolve2_path', '')
        if platesolve2_path and os.path.exists(platesolve2_path):
            print("✓ PlateSolve 2 executable found")
            return True
        else:
            print("✗ PlateSolve 2 executable not found")
            return False
            
    except Exception as e:
        print(f"✗ Error testing configuration: {e}")
        return False

def main():
    """Main test function."""
    print("PlateSolve 2 Working Integration Test")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Direct Command", test_platesolve2_direct),
        ("Integration", test_platesolve2_integration),
        ("CLI Mode", test_platesolve2_cli_mode),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            print(f"✓ {test_name} passed")
            passed += 1
        else:
            print(f"✗ {test_name} failed")
    
    print(f"\n--- Results ---")
    print(f"Passed: {passed}/{total}")
    
    if passed >= 3:
        print("\n🎉 PlateSolve 2 integration is working!")
        print("\nHow to use:")
        print("1. PlateSolve 2 will open GUI when called")
        print("2. Solve the image manually in the GUI")
        print("3. Copy coordinates or save results")
        print("4. Use the coordinates in your overlay system")
        print("\nFor automation, consider:")
        print("- Using Astrometry.net API")
        print("- Implementing clipboard monitoring")
        print("- Using Windows API to read GUI content")
    else:
        print("\n❌ Some tests failed. Check the output above.")

if __name__ == "__main__":
    main() 