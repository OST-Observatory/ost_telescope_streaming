#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for coordinate conversion
"""

import sys
import os
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

# Add the code directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

def skycoord_to_pixel(obj_coord, center_coord, size_px, fov_deg):
    """Converts sky coordinates to pixel coordinates."""
    try:
        delta_ra = (obj_coord.ra.degree - center_coord.ra.degree) * \
            u.deg.to(u.arcmin) * np.cos(center_coord.dec.radian)
        delta_dec = (obj_coord.dec.degree - center_coord.dec.degree) * u.deg.to(u.arcmin)

        scale = size_px[0] / (fov_deg * 60)  # arcmin -> pixels

        x = size_px[0] / 2 + delta_ra * scale
        y = size_px[1] / 2 - delta_dec * scale  # Invert Y-axis (Dec up)

        return int(x), int(y)
    except Exception as e:
        raise ValueError(f"Error in coordinate conversion: {e}")

try:
    print("Testing coordinate conversion...")
    print("=" * 40)
    
    # Test coordinates
    center_ra = 47.4166
    center_dec = -15.5384
    image_size = (800, 800)
    fov_deg = 1.5
    
    center_coord = SkyCoord(ra=center_ra * u.deg, dec=center_dec * u.deg, frame='icrs')
    
    print(f"Center: RA={center_ra}°, Dec={center_dec}°")
    print(f"Image size: {image_size}")
    print(f"Field of view: {fov_deg}°")
    
    # Test some object coordinates
    test_objects = [
        (center_ra + 0.1, center_dec + 0.1, "Object 1"),
        (center_ra - 0.1, center_dec - 0.1, "Object 2"),
        (center_ra, center_dec, "Center object"),
        (center_ra + 1.0, center_dec + 1.0, "Far object")
    ]
    
    for obj_ra, obj_dec, name in test_objects:
        obj_coord = SkyCoord(ra=obj_ra * u.deg, dec=obj_dec * u.deg, frame='icrs')
        
        try:
            x, y = skycoord_to_pixel(obj_coord, center_coord, image_size, fov_deg)
            print(f"{name}: RA={obj_ra:.4f}°, Dec={obj_dec:.4f}° -> Pixel({x}, {y})")
        except Exception as e:
            print(f"{name}: Error - {e}")
    
    print("\nCoordinate conversion test completed!")
    
except Exception as e:
    print(f"Error during coordinate test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 