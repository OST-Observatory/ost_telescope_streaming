#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for SIMBAD queries
"""

import sys
import os

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

try:
    from astroquery.simbad import Simbad
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    from config_manager import config
    
    print("Testing SIMBAD query...")
    print("=" * 40)
    
    # Test coordinates (same as in your error)
    ra = 47.4166
    dec = -15.5384
    
    print(f"Testing coordinates: RA={ra}°, Dec={dec}°")
    
    # Configure SIMBAD
    custom_simbad = Simbad()
    custom_simbad.reset_votable_fields()
    custom_simbad.add_votable_fields('ra', 'dec', 'V', 'otype', 'main_id')
    
    # Create center coordinate
    center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs')
    
    # Query SIMBAD
    print("Querying SIMBAD...")
    result = custom_simbad.query_region(center, radius=1.0 * u.deg, timeout=30)
    
    if result is None or len(result) == 0:
        print("No objects found in SIMBAD query.")
    else:
        print(f"Found {len(result)} objects")
        print(f"Available columns: {result.colnames}")
        
        # Show first few objects
        print("\nFirst 3 objects:")
        for i, row in enumerate(result[:3]):
            print(f"Object {i+1}:")
            for col in result.colnames:
                print(f"  {col}: {row[col]}")
            print()
    
    print("SIMBAD test completed!")
    
except Exception as e:
    print(f"Error during SIMBAD test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 