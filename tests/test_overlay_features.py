#!/usr/bin/env python3
"""
Test script for new overlay features:
- Information panel with camera/telescope parameters
- Configurable title/header
"""

import os
from pathlib import Path
import sys

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager

try:
    from overlay.generator import OverlayGenerator
except Exception:
    from generate_overlay import OverlayGenerator
import logging


def test_overlay_features():
    """Test the new overlay features."""

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

    # Create overlay generator
    generator = OverlayGenerator(config, logger)

    # Test coordinates (M31 - Andromeda Galaxy)
    ra_deg = 10.6847
    dec_deg = 41.2692

    # Test parameters
    fov_width_deg = 1.5
    fov_height_deg = 1.0
    position_angle_deg = 45.0  # Test rotation

    logger.info("Testing overlay generation with new features...")
    logger.info(f"Coordinates: RA={ra_deg}°, Dec={dec_deg}°")
    logger.info(f"Field of view: {fov_width_deg}°×{fov_height_deg}°")
    logger.info(f"Position angle: {position_angle_deg}°")

    # Generate overlay
    output_file = "test_overlay_with_info.png"

    try:
        result = generator.generate_overlay(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            output_file=output_file,
            fov_width_deg=fov_width_deg,
            fov_height_deg=fov_height_deg,
            position_angle_deg=position_angle_deg,
            image_size=(1200, 800),  # Smaller size for testing
            mag_limit=8.0,
        )

        if hasattr(result, "is_success") and result.is_success:
            logger.info(f"✅ Overlay generated successfully: {output_file}")
            logger.info(f"Details: {result.details}")
        else:
            logger.error(f"❌ Overlay generation failed: {result}")

    except Exception as e:
        logger.error(f"❌ Error during overlay generation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_overlay_features()
