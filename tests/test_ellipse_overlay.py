#!/usr/bin/env python3
"""
Test script for ellipse overlay features:
- Ellipses for galaxies and nebulae based on actual dimensions
- Fallback to markers for objects without dimension data
- Position angle support for rotated ellipses
"""

import sys
import os
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
try:
    from overlay.generator import OverlayGenerator
except Exception:
    from generate_overlay import OverlayGenerator
import logging

def test_ellipse_overlay_features():
    """Test the ellipse overlay features."""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config_file = "config_80mm-apo_asi2600ms-pro.yaml"
    if not os.path.exists(config_file):
        config_file = "config.yaml"
        logger.info(f"Using default config: {config_file}")
    
    config = ConfigManager(config_file)
    logger.info(f"Configuration loaded from: {config_file}")
    
    # Test coordinates for different types of objects
    test_coordinates = [
        # M31 - Andromeda Galaxy (large galaxy with dimensions)
        {"name": "M31_Andromeda", "ra": 10.6847, "dec": 41.2692, "fov": 2.0},
        
        # M42 - Orion Nebula (large nebula with dimensions)
        {"name": "M42_Orion", "ra": 83.8221, "dec": -5.3911, "fov": 1.5},
        
        # M13 - Hercules Globular Cluster (globular cluster)
        {"name": "M13_Hercules", "ra": 250.4235, "dec": 36.4613, "fov": 1.0},
        
        # M57 - Ring Nebula (planetary nebula)
        {"name": "M57_Ring", "ra": 283.3964, "dec": 33.0292, "fov": 0.5},
        
        # M45 - Pleiades (open cluster)
        {"name": "M45_Pleiades", "ra": 56.8711, "dec": 24.1053, "fov": 2.0},
        
        # M1 - Crab Nebula (supernova remnant)
        {"name": "M1_Crab", "ra": 83.6331, "dec": 22.0145, "fov": 0.8},
    ]
    
    logger.info("Testing ellipse overlay features...")
    
    for test_case in test_coordinates:
        name = test_case["name"]
        ra_deg = test_case["ra"]
        dec_deg = test_case["dec"]
        fov_deg = test_case["fov"]
        
        logger.info(f"\n=== Test: {name} ===")
        logger.info(f"Coordinates: RA={ra_deg}°, Dec={dec_deg}°")
        logger.info(f"Field of view: {fov_deg}°")
        
        # Create overlay generator
        generator = OverlayGenerator(config, logger)
        
        try:
            result = generator.generate_overlay(
                ra_deg=ra_deg,
                dec_deg=dec_deg,
                output_file=f"test_ellipse_{name}.png",
                fov_width_deg=fov_deg,
                fov_height_deg=fov_deg,
                position_angle_deg=0.0,  # No rotation for testing
                image_size=(1200, 1200),
                mag_limit=12.0  # Higher magnitude limit to get more objects
            )
            
            if hasattr(result, 'is_success') and result.is_success:
                logger.info(f"✅ Ellipse overlay for {name} generated successfully")
                logger.info(f"   File: test_ellipse_{name}.png")
            else:
                logger.error(f"❌ Ellipse overlay for {name} failed: {result}")
                
        except Exception as e:
            logger.error(f"❌ Error during ellipse overlay generation for {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Test with rotation
    logger.info("\n=== Test: M31 with Rotation ===")
    ra_deg = 10.6847
    dec_deg = 41.2692
    fov_deg = 2.0
    position_angle_deg = 45.0
    
    logger.info(f"Coordinates: RA={ra_deg}°, Dec={dec_deg}°")
    logger.info(f"Field of view: {fov_deg}°")
    logger.info(f"Position angle: {position_angle_deg}°")
    
    try:
        result = generator.generate_overlay(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            output_file="test_ellipse_M31_rotated.png",
            fov_width_deg=fov_deg,
            fov_height_deg=fov_deg,
            position_angle_deg=position_angle_deg,
            image_size=(1200, 1200),
            mag_limit=12.0
        )
        
        if hasattr(result, 'is_success') and result.is_success:
            logger.info("✅ Rotated ellipse overlay generated successfully")
            logger.info("   File: test_ellipse_M31_rotated.png")
        else:
            logger.error(f"❌ Rotated ellipse overlay failed: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error during rotated ellipse overlay generation: {e}")
    
    logger.info("\n=== Test Summary ===")
    logger.info("Generated files:")
    for test_case in test_coordinates:
        name = test_case["name"]
        logger.info(f"- test_ellipse_{name}.png")
    logger.info("- test_ellipse_M31_rotated.png")
    logger.info("\nNote: Check the generated images to see:")
    logger.info("- Ellipses for galaxies and nebulae with dimension data")
    logger.info("- Standard markers for stars and objects without dimensions")
    logger.info("- Proper rotation of ellipses based on position angle")

if __name__ == "__main__":
    test_ellipse_overlay_features() 