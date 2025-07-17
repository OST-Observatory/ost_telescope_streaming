#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug SIMBAD column names and data
"""

import sys
import os

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

try:
    from astroquery.simbad import Simbad
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    
    print("Debugging SIMBAD data...")
    print("=" * 40)
    
    # Test coordinates
    ra = 47.4166
    dec = -15.5384
    
    print(f"Coordinates: RA={ra}°, Dec={dec}°")
    
    # Configure SIMBAD
    custom_simbad = Simbad()
    custom_simbad.reset_votable_fields()
    custom_simbad.add_votable_fields('ra', 'dec', 'V', 'otype', 'main_id')
    
    # Create center coordinate
    center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs')
    
    # Query SIMBAD
    print("Querying SIMBAD...")
    result = custom_simbad.query_region(center, radius=1.0 * u.deg)
    
    if result is None or len(result) == 0:
        print("No objects found.")
        sys.exit(0)
    
    print(f"Found {len(result)} objects")
    print(f"Available columns: {result.colnames}")
    
    # Debug first object in detail
    print(f"\nDetailed analysis of first object:")
    first_row = result[0]
    
    for col in result.colnames:
        value = first_row[col]
        value_type = type(value).__name__
        print(f"  {col}: {value} (type: {value_type})")
        
        # Check if it's bytes and try to decode
        if isinstance(value, bytes):
            try:
                decoded = value.decode('utf-8')
                print(f"    Decoded: {decoded}")
            except Exception as e:
                print(f"    Decode error: {e}")
    
    # Check for main_id column specifically
    print(f"\nChecking for main_id column:")
    if 'main_id' in result.colnames:
        print(f"  main_id column exists")
        print(f"  First value: {first_row['main_id']}")
        print(f"  Type: {type(first_row['main_id'])}")
    else:
        print(f"  main_id column NOT found")
        print(f"  Available columns: {result.colnames}")
    
    print(f"\nDebug completed!")
    
except Exception as e:
    print(f"Error during debug: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 