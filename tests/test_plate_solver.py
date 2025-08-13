import logging
import sys
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
from platesolve.solver import PlateSolve2, PlateSolverFactory
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test plate solver")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    
    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()
    
    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()
    
    # Recreate parser with the loaded configuration defaults
    parser = argparse.ArgumentParser(description="Test plate solver")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("image", help="Image file to solve")
    parser.add_argument("--solver", default="platesolve2", help="Solver to use")
    parser.add_argument("--list", action="store_true", help="List available solvers")
    args = parser.parse_args()

    logger = logging.getLogger("plate_solver_cli")

    if args.list:
        print("Available solvers:")
        available = PlateSolverFactory.get_available_solvers()
        for name, is_available in available.items():
            status = "✓" if is_available else "✗"
            print(f"  {status} {name}")
        return

    solver = PlateSolverFactory.create_solver(args.solver, config=config, logger=logger)
    if not solver:
        print(f"Failed to create solver: {args.solver}")
        return
    if not solver.is_available():
        print(f"Solver {args.solver} is not available")
        return
    print(f"Solving {args.image} with {solver.get_name()}...")
    status = solver.solve(args.image)
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