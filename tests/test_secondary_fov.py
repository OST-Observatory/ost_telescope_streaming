#!/usr/bin/env python3
"""
Test script for secondary FOV overlay features:
- Camera-based rectangular FOV
- Eyepiece-based circular FOV
- Position offsets
- Different display styles
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

def test_secondary_fov_features():
    """Test the secondary FOV overlay features."""
    
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
    
    # Test coordinates (M31 - Andromeda Galaxy)
    ra_deg = 10.6847
    dec_deg = 41.2692
    
    # Test parameters
    fov_width_deg = 1.5
    fov_height_deg = 1.0
    position_angle_deg = 45.0  # Test rotation
    
    logger.info("Testing secondary FOV overlay features...")
    logger.info(f"Coordinates: RA={ra_deg}°, Dec={dec_deg}°")
    logger.info(f"Field of view: {fov_width_deg}°×{fov_height_deg}°")
    logger.info(f"Position angle: {position_angle_deg}°")
    
    # Test 1: Camera-based secondary FOV
    logger.info("\n=== Test 1: Camera-based Secondary FOV ===")
    config.overlay_config['secondary_fov']['enabled'] = True
    config.overlay_config['secondary_fov']['type'] = 'camera'
    config.overlay_config['secondary_fov']['display']['style'] = 'dashed'
    
    generator = OverlayGenerator(config, logger)
    
    try:
        result = generator.generate_overlay(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            output_file="test_secondary_fov_camera.png",
            fov_width_deg=fov_width_deg,
            fov_height_deg=fov_height_deg,
            position_angle_deg=position_angle_deg,
            image_size=(1200, 800),
            mag_limit=8.0
        )
        
        if hasattr(result, 'is_success') and result.is_success:
            logger.info("✅ Camera-based secondary FOV overlay generated successfully")
        else:
            logger.error(f"❌ Camera-based secondary FOV failed: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error during camera-based secondary FOV generation: {e}")
    
    # Test 2: Eyepiece-based secondary FOV
    logger.info("\n=== Test 2: Eyepiece-based Secondary FOV ===")
    config.overlay_config['secondary_fov']['type'] = 'eyepiece'
    config.overlay_config['secondary_fov']['display']['style'] = 'solid'
    
    try:
        result = generator.generate_overlay(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            output_file="test_secondary_fov_eyepiece.png",
            fov_width_deg=fov_width_deg,
            fov_height_deg=fov_height_deg,
            position_angle_deg=position_angle_deg,
            image_size=(1200, 800),
            mag_limit=8.0
        )
        
        if hasattr(result, 'is_success') and result.is_success:
            logger.info("✅ Eyepiece-based secondary FOV overlay generated successfully")
        else:
            logger.error(f"❌ Eyepiece-based secondary FOV failed: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error during eyepiece-based secondary FOV generation: {e}")
    
    # Test 3: Secondary FOV with position offset
    logger.info("\n=== Test 3: Secondary FOV with Position Offset ===")
    config.overlay_config['secondary_fov']['position_offset']['ra_offset_arcmin'] = 30.0
    config.overlay_config['secondary_fov']['position_offset']['dec_offset_arcmin'] = 15.0
    config.overlay_config['secondary_fov']['type'] = 'camera'
    config.overlay_config['secondary_fov']['display']['style'] = 'dashed'
    
    try:
        result = generator.generate_overlay(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            output_file="test_secondary_fov_offset.png",
            fov_width_deg=fov_width_deg,
            fov_height_deg=fov_height_deg,
            position_angle_deg=position_angle_deg,
            image_size=(1200, 800),
            mag_limit=8.0
        )
        
        if hasattr(result, 'is_success') and result.is_success:
            logger.info("✅ Secondary FOV with offset generated successfully")
        else:
            logger.error(f"❌ Secondary FOV with offset failed: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error during secondary FOV with offset generation: {e}")
    
    # Test 4: Disabled secondary FOV
    logger.info("\n=== Test 4: Disabled Secondary FOV ===")
    config.overlay_config['secondary_fov']['enabled'] = False
    
    try:
        result = generator.generate_overlay(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            output_file="test_secondary_fov_disabled.png",
            fov_width_deg=fov_width_deg,
            fov_height_deg=fov_height_deg,
            position_angle_deg=position_angle_deg,
            image_size=(1200, 800),
            mag_limit=8.0
        )
        
        if hasattr(result, 'is_success') and result.is_success:
            logger.info("✅ Overlay without secondary FOV generated successfully")
        else:
            logger.error(f"❌ Overlay without secondary FOV failed: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error during overlay without secondary FOV generation: {e}")
    
    logger.info("\n=== Test Summary ===")
    logger.info("Generated files:")
    logger.info("- test_secondary_fov_camera.png (Camera-based FOV)")
    logger.info("- test_secondary_fov_eyepiece.png (Eyepiece-based FOV)")
    logger.info("- test_secondary_fov_offset.png (FOV with position offset)")
    logger.info("- test_secondary_fov_disabled.png (No secondary FOV)")

if __name__ == "__main__":
    test_secondary_fov_features() 