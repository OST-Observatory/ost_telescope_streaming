import logging
import sys
import argparse
import os
from pathlib import Path
from datetime import datetime

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
from overlay_runner import OverlayRunner

def main():
    """Command-line interface for the overlay runner with image combination functionality.
    
    This script demonstrates the complete workflow:
    1. Plate-solving of captured images
    2. Generation of astronomical overlays
    3. Combination of overlays with captured images
    4. Saving of annotated images
    """
    parser = argparse.ArgumentParser(
        description='Overlay Runner with image combination functionality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python overlay_runner.py
  
  # Run with custom config and 60-second intervals
  python overlay_runner.py --config my_config.yaml --interval 60
  
  # Run with debug logging
  python overlay_runner.py --debug
  
  # Run with video processing and plate-solving
  python overlay_runner.py --enable-video --wait-for-plate-solve
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=30,
        help='Update interval in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--wait-for-plate-solve',
        action='store_true',
        help='Wait for plate-solving results before generating overlays'
    )
    
    parser.add_argument(
        '--enable-video',
        action='store_true',
        help='Enable video processing and frame capture'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    if args.debug:
        log_level = logging.DEBUG
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'overlay_runner_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        ],
        force=True
    )
    
    logger = logging.getLogger('overlay_runner_cli')
    
    try:
        # Load configuration
        if not os.path.exists(args.config):
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)
        
        config = ConfigManager(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
        
        # Override config settings with command line arguments
        if args.interval != 30:
            overlay_config = config.get_overlay_config()
            overlay_config['update'] = overlay_config.get('update', {})
            overlay_config['update']['update_interval'] = args.interval
            logger.info(f"Update interval set to {args.interval} seconds")
        
        if args.wait_for_plate_solve:
            overlay_config = config.get_overlay_config()
            overlay_config['wait_for_plate_solve'] = True
            logger.info("Waiting for plate-solving results enabled")
        
        if args.enable_video:
            video_config = config.get_video_config()
            video_config['video_enabled'] = True
            logger.info("Video processing enabled")
        
        # Create and run overlay runner
        runner = OverlayRunner(config=config, logger=logger)
        
        logger.info("Starting Overlay Runner with image combination...")
        logger.info("Press Ctrl+C to stop")
        
        # Run the overlay runner
        runner.run()
        
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 