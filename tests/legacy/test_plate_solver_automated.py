import logging
from pathlib import Path
import sys

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

import argparse

from config_manager import ConfigManager
from platesolve.platesolve2 import PlateSolve2Automated


def main():
    parser = argparse.ArgumentParser(description="Test automated PlateSolve 2")
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()

    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()

    # Recreate parser with the loaded configuration defaults
    parser = argparse.ArgumentParser(description="Test automated PlateSolve 2")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("image", help="Image file to solve")
    parser.add_argument("--ra", type=float, help="Right Ascension in degrees")
    parser.add_argument("--dec", type=float, help="Declination in degrees")
    parser.add_argument("--fov-width", type=float, help="Field of view width in degrees")
    parser.add_argument("--fov-height", type=float, help="Field of view height in degrees")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logger = logging.getLogger("platesolve2_automated_cli")
    solver = PlateSolve2Automated(config=config, logger=logger)
    if args.verbose:
        solver.verbose = True
    print(f"Testing automated PlateSolve 2 with: {args.image}")
    status = solver.solve(
        args.image,
        ra_deg=args.ra,
        dec_deg=args.dec,
        fov_width_deg=args.fov_width,
        fov_height_deg=args.fov_height,
    )
    print(f"Status: {status.level.value.upper()} - {status.message}")
    if status.details:
        print(f"  Solving time: {status.details.get('solving_time', 0):.1f}s")
    if status.is_success and status.data:
        result = status.data
        print(f"  RA: {result.get('ra_center', 'N/A'):.4f}°")
        print(f"  Dec: {result.get('dec_center', 'N/A'):.4f}°")
        print(f"  Pixel scale: {result.get('pixel_scale', 'N/A'):.5f} arcsec/pixel")
        print(f"  Position angle: {result.get('position_angle', 'N/A'):.1f}°")
        print(f"  Confidence: {result.get('confidence', 0):.2f}")
        print(f"  Stars detected: {result.get('stars_detected', 0)}")
        if result.get("flipped", 0) >= 1:
            print("  Image is flipped")
    else:
        exit(1)


if __name__ == "__main__":
    main()
