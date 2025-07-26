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
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    # Get logger for overlay runner
    logger = logging.getLogger("overlay_runner_cli")
    
    # Set logger level from config if available
    try:
        log_config = config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        logger.setLevel(getattr(logging, log_level.upper()))
    except Exception as e:
        print(f"Warning: Could not set log level from config: {e}")
    
    runner = OverlayRunner(config=config, logger=logger)
    runner.run()

if __name__ == "__main__":
    main() 