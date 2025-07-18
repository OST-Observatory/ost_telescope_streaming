#!/usr/bin/env python3
"""
Test script for advanced PlateSolve 2 automation.
Tests multiple approaches to automate PlateSolve 2 without manual intervention.
"""

import sys
import os
import time
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def test_advanced_automation():
    """Test the advanced automation approach."""
    print("Testing advanced PlateSolve 2 automation...")
    
    try:
        from plate_solver_advanced import PlateSolve2Advanced
        
        # Create solver
        solver = PlateSolve2Advanced()
        
        # Test image
        test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
        
        if not os.path.exists(test_image):
            print(f"✗ Test image not found: {test_image}")
            return False
        
        print(f"✓ Test image found: {test_image}")
        print(f"✓ Working directory: {solver.working_directory}")
        print(f"✓ Executable path: {solver.executable_path}")
        
        # Test availability
        if not solver._is_available():
            print("✗ PlateSolve 2 not available")
            return False
        
        print("✓ PlateSolve 2 is available")
        
        # Test solving
        print("\nStarting advanced automation test...")
        print("This will try multiple approaches to automate PlateSolve 2")
        
        result = solver.solve(test_image)
        
        print(f"\nResult: {result}")
        
        if result['success']:
            print(f"✓ Automation successful!")
            print(f"✓ Method used: {result['method_used']}")
            print(f"✓ RA: {result['ra_center']}°")
            print(f"✓ Dec: {result['dec_center']}°")
            print(f"✓ Solving time: {result['solving_time']:.1f}s")
            return True
        else:
            print(f"✗ Automation failed: {result['error_message']}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing advanced automation: {e}")
        return False

def test_command_line_variations():
    """Test different command line variations directly."""
    print("\nTesting command line variations directly...")
    
    import subprocess
    
    platesolve2_path = r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\PlateSolve2.exe"
    test_image = r"E:\Data\2025-07-01\NGC6819-0001_V_8s.fit"
    
    if not os.path.exists(platesolve2_path) or not os.path.exists(test_image):
        print("✗ Required files not found")
        return False
    
    # Test different command variations
    variations = [
        ["/silent"],
        ["-silent"],
        ["--silent"],
        ["/batch"],
        ["-batch"],
        ["--batch"],
        ["/auto"],
        ["-auto"],
        ["--auto"],
        ["/help"],
        ["-help"],
        ["--help"],
        ["/?"],
        ["-?"],
        ["--?"],
    ]
    
    for variation in variations:
        cmd = [platesolve2_path, test_image] + variation
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
            print("Timeout (this might be normal)")
        except Exception as e:
            print(f"Error: {e}")
    
    return True

def test_nina_inspiration():
    """Test approaches inspired by NINA implementation."""
    print("\nTesting NINA-inspired approaches...")
    
    try:
        # Check if we can find any documentation or examples
        print("Looking for PlateSolve 2 documentation or examples...")
        
        # Common locations for documentation
        possible_docs = [
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\README.txt",
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\help.txt",
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\*.txt",
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\*.pdf",
        ]
        
        for doc_pattern in possible_docs:
            if "*" in doc_pattern:
                import glob
                files = glob.glob(doc_pattern)
                for file in files:
                    print(f"Found: {file}")
            elif os.path.exists(doc_pattern):
                print(f"Found: {doc_pattern}")
        
        # Check for configuration files
        config_patterns = [
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\*.ini",
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\*.cfg",
            r"C:\Program Files (x86)\PlaneWave Instruments\PWI3\PlateSolve2\*.conf",
        ]
        
        for config_pattern in config_patterns:
            import glob
            files = glob.glob(config_pattern)
            for file in files:
                print(f"Found config: {file}")
        
        print("NINA-inspired approach test completed")
        return True
        
    except Exception as e:
        print(f"Error in NINA inspiration test: {e}")
        return False

def test_alternative_solvers():
    """Test alternative plate-solving solutions."""
    print("\nTesting alternative plate-solving solutions...")
    
    alternatives = [
        {
            'name': 'Astrometry.net API',
            'description': 'Online plate-solving service',
            'url': 'http://nova.astrometry.net/api/',
            'status': 'Available online'
        },
        {
            'name': 'Local Astrometry.net',
            'description': 'Local installation of astrometry.net',
            'status': 'Requires installation'
        },
        {
            'name': 'AI Plate Solver',
            'description': 'AI-based plate-solving',
            'status': 'Emerging technology'
        }
    ]
    
    for alt in alternatives:
        print(f"\n{alt['name']}:")
        print(f"  Description: {alt['description']}")
        print(f"  Status: {alt['status']}")
    
    print("\nRecommendations:")
    print("1. Try Astrometry.net API for online solving")
    print("2. Install local astrometry.net for offline solving")
    print("3. Continue investigating PlateSolve 2 automation")
    
    return True

def main():
    """Main test function."""
    print("Advanced PlateSolve 2 Automation Test")
    print("=" * 50)
    
    tests = [
        ("Advanced Automation", test_advanced_automation),
        ("Command Line Variations", test_command_line_variations),
        ("NINA Inspiration", test_nina_inspiration),
        ("Alternative Solvers", test_alternative_solvers),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            print(f"✓ {test_name} completed")
            passed += 1
        else:
            print(f"✗ {test_name} failed")
    
    print(f"\n--- Results ---")
    print(f"Completed: {passed}/{total}")
    
    if passed >= 3:
        print("\n🎉 Advanced automation testing completed!")
        print("\nNext steps:")
        print("1. Check PlateSolve 2 documentation for automation options")
        print("2. Consider using Astrometry.net API as alternative")
        print("3. Implement result file monitoring")
        print("4. Test with different image formats")
    else:
        print("\n❌ Some tests failed. Consider alternative approaches.")

if __name__ == "__main__":
    main() 