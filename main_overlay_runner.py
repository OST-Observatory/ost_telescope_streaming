import logging
import sys
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
from overlay_runner import OverlayRunner
import argparse

def main():
    parser = argparse.ArgumentParser(description="OST Telescope Streaming - Overlay Runner")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    
    # Parse config argument first to load the right configuration
    args, remaining = parser.parse_known_args()
    
    # Load configuration
    if args.config:
        config = ConfigManager(config_path=args.config)
    else:
        config = ConfigManager()
    
    print("OST Telescope Streaming - Overlay Runner")
    print("=" * 50)
    logger = logging.getLogger("overlay_runner_cli")
    runner = OverlayRunner(config=config, logger=logger)
    runner.run()

if __name__ == "__main__":
    main() 