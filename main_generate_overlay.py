import logging
import sys
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import config
from generate_overlay import OverlayGenerator
import argparse

def main():
    parser = argparse.ArgumentParser(description="Generates an overlay based on RA/Dec.")
    parser.add_argument("--ra", type=float, required=True, help="Right Ascension in degrees")
    parser.add_argument("--dec", type=float, required=True, help="Declination in degrees")
    parser.add_argument("--output", type=str, help="Output file (default: from config)")
    parser.add_argument("--fov-width", type=float, help="Field of view width in degrees (from plate-solving)")
    parser.add_argument("--fov-height", type=float, help="Field of view height in degrees (from plate-solving)")
    parser.add_argument("--position-angle", type=float, help="Position angle in degrees (from plate-solving)")
    parser.add_argument("--image-width", type=int, help="Image width in pixels (from camera)")
    parser.add_argument("--image-height", type=int, help="Image height in pixels (from camera)")
    args = parser.parse_args()
    
    # Prepare image_size tuple if both width and height are provided
    image_size = None
    if args.image_width is not None and args.image_height is not None:
        image_size = (args.image_width, args.image_height)
    elif args.image_width is not None or args.image_height is not None:
        print("Warning: Both --image-width and --image-height must be provided for image_size to be used")
    
    try:
        logger = logging.getLogger("overlay_cli")
        generator = OverlayGenerator(config=config, logger=logger)
        status = generator.generate_overlay(
            args.ra, args.dec, args.output,
            args.fov_width, args.fov_height, args.position_angle, image_size
        )
        print(f"Status: {status.level.value.upper()} - {status.message}")
        if status.details:
            print(f"Details: {status.details}")
        if status.is_success:
            print(f"Overlay file: {status.data}")
        else:
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 