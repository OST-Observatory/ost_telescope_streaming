import logging
from code.config_manager import config
from code.generate_overlay import OverlayGenerator
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Generates an overlay based on RA/Dec.")
    parser.add_argument("--ra", type=float, required=True, help="Right Ascension in degrees")
    parser.add_argument("--dec", type=float, required=True, help="Declination in degrees")
    parser.add_argument("--output", type=str, help="Output file (default: from config)")
    args = parser.parse_args()
    try:
        logger = logging.getLogger("overlay_cli")
        generator = OverlayGenerator(config=config, logger=logger)
        status = generator.generate_overlay(args.ra, args.dec, args.output)
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