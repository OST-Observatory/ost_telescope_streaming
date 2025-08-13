#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze object types from SIMBAD query
"""

from collections import Counter
import os
import sys

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "code"))

try:
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    from astroquery.simbad import Simbad

    print("Analyzing SIMBAD objects...")
    print("=" * 40)

    # Test coordinates
    ra = 47.4166
    dec = -15.5384

    print(f"Coordinates: RA={ra}°, Dec={dec}°")

    # Configure SIMBAD
    custom_simbad = Simbad()
    custom_simbad.reset_votable_fields()
    custom_simbad.add_votable_fields("ra", "dec", "V", "otype", "main_id")

    # Create center coordinate
    center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")

    # Query SIMBAD
    print("Querying SIMBAD...")
    result = custom_simbad.query_region(center, radius=1.0 * u.deg)

    if result is None or len(result) == 0:
        print("No objects found.")
        sys.exit(0)

    print(f"Found {len(result)} objects")

    # Analyze object types
    object_types = []
    magnitudes = []
    has_magnitude_count = 0

    for row in result:
        # Object type
        if "otype" in row.colnames:
            obj_type = row["otype"]
            object_types.append(obj_type)

        # Magnitude
        if "V" in row.colnames:
            mag = row["V"]
            if mag is not None and mag != "--":
                magnitudes.append(float(mag))
                has_magnitude_count += 1

    # Count object types
    type_counter = Counter(object_types)

    print("\nObject Type Analysis:")
    print(f"Objects with magnitude: {has_magnitude_count}")
    print(f"Objects without magnitude: {len(result) - has_magnitude_count}")

    print("\nObject Types (top 10):")
    for obj_type, count in type_counter.most_common(10):
        print(f"  {obj_type}: {count}")

    if magnitudes:
        print("\nMagnitude Analysis:")
        print(f"  Min magnitude: {min(magnitudes):.2f}")
        print(f"  Max magnitude: {max(magnitudes):.2f}")
        print(f"  Average magnitude: {sum(magnitudes)/len(magnitudes):.2f}")

        # Count by magnitude ranges
        bright = sum(1 for m in magnitudes if m <= 6)
        medium = sum(1 for m in magnitudes if 6 < m <= 10)
        faint = sum(1 for m in magnitudes if m > 10)

        print(f"  Bright (≤6): {bright}")
        print(f"  Medium (6-10): {medium}")
        print(f"  Faint (>10): {faint}")

    print("\nAnalysis completed!")

except Exception as e:
    print(f"Error during analysis: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
