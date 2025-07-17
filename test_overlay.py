#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test overlay generation with current configuration
"""

import sys
import os

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

try:
    from generate_overlay import main as generate_overlay_main
    import argparse
    
    print("Testing overlay generation...")
    print("=" * 40)
    
    # Test coordinates (same as before)
    ra = 47.4166
    dec = -15.5384
    
    print(f"Coordinates: RA={ra}°, Dec={dec}°")
    print("Generating overlay...")
    
    # Simulate command line arguments
    sys.argv = [
        'generate_overlay.py',
        '--ra', str(ra),
        '--dec', str(dec),
        '--output', 'test_overlay.png'
    ]
    
    # Run the overlay generation
    generate_overlay_main()
    
    print("Overlay generation test completed!")
    print("Check 'test_overlay.png' for the result.")
    
except Exception as e:
    print(f"Error during overlay test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 