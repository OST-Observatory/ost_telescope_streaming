import logging
from code.config_manager import config
from code.plate_solver_automated import PlateSolve2Automated
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test automated PlateSolve 2")
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
        fov_height_deg=args.fov_height
    )
    print(f"Status: {status.level.value.upper()} - {status.message}")
    if status.details:
        print(f"Details: {status.details}")
    if status.is_success and status.data:
        result = status.data
        print(f"  RA: {result.get('ra_center', 'N/A'):.4f}°")
        print(f"  Dec: {result.get('dec_center', 'N/A'):.4f}°")
        print(f"  FOV: {result.get('fov_width', 0):.3f}° x {result.get('fov_height', 0):.3f}°")
        print(f"  Confidence: {result.get('confidence', 0):.2f}")
        print(f"  Stars detected: {result.get('stars_detected', 0)}")
        print(f"  Solving time: {result.get('solving_time', 0):.1f}s")
    else:
        exit(1)

if __name__ == "__main__":
    main() 