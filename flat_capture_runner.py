#!/usr/bin/env python3
"""
Flat Capture Runner

This script provides a command-line interface for capturing flat field images
with automatic exposure adjustment to achieve target count rates.

Usage:
    python flat_capture_runner.py --config config_flat_capture.yaml
    python flat_capture_runner.py --config config_flat_capture.yaml --num-flats 50
    python flat_capture_runner.py --config config_flat_capture.yaml --target-count-rate 0.6
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
from flat_capture import FlatCapture
from video_capture import VideoCapture


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'flat_capture_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        ]
    )


def main():
    """Main function for flat capture runner."""
    parser = argparse.ArgumentParser(
        description='Automatic Flat Field Capture System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic flat capture with default settings
  python flat_capture_runner.py --config config_flat_capture.yaml
  
  # Custom number of flats
  python flat_capture_runner.py --config config_flat_capture.yaml --num-flats 50
  
  # Custom target count rate (60% instead of 50%)
  python flat_capture_runner.py --config config_flat_capture.yaml --target-count-rate 0.6
  
  # Debug mode with custom tolerance
  python flat_capture_runner.py --config config_flat_capture.yaml --debug --tolerance 0.15
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config_flat_capture.yaml',
        help='Configuration file path (default: config_flat_capture.yaml)'
    )
    
    parser.add_argument(
        '--num-flats',
        type=int,
        help='Number of flat frames to capture (overrides config)'
    )
    
    parser.add_argument(
        '--target-count-rate',
        type=float,
        help='Target count rate as fraction of maximum (overrides config)'
    )
    
    parser.add_argument(
        '--tolerance',
        type=float,
        help='Count rate tolerance (overrides config)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
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
    
    setup_logging(log_level)
    logger = logging.getLogger('flat_capture_runner')
    
    try:
        # Load configuration
        if not os.path.exists(args.config):
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)
        
        config = ConfigManager(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
        
        # Override config settings with command line arguments
        flat_config = config.get_flat_config()
        
        if args.num_flats:
            flat_config['num_flats'] = args.num_flats
            logger.info(f"Number of flats set to: {args.num_flats}")
        
        if args.target_count_rate:
            flat_config['target_count_rate'] = args.target_count_rate
            logger.info(f"Target count rate set to: {args.target_count_rate:.1%}")
        
        if args.tolerance:
            flat_config['count_tolerance'] = args.tolerance
            logger.info(f"Count tolerance set to: {args.tolerance:.1%}")
        
        # Initialize video capture
        logger.info("Initializing video capture...")
        video_capture = VideoCapture(config=config, logger=logger)
        
        if not video_capture.initialize():
            logger.error("Failed to initialize video capture")
            sys.exit(1)
        
        # Initialize flat capture
        logger.info("Initializing flat capture system...")
        flat_capture = FlatCapture(config=config, logger=logger)
        
        if not flat_capture.initialize(video_capture):
            logger.error("Failed to initialize flat capture")
            sys.exit(1)
        
        # Display settings
        logger.info("Flat Capture Settings:")
        logger.info(f"  Target count rate: {flat_config['target_count_rate']:.1%}")
        logger.info(f"  Count tolerance: {flat_config['count_tolerance']:.1%}")
        logger.info(f"  Number of flats: {flat_config['num_flats']}")
        logger.info(f"  Exposure range: {flat_config['min_exposure']:.3f}s - {flat_config['max_exposure']:.1f}s")
        logger.info(f"  Output directory: {flat_config['output_dir']}")
        
        # Start flat capture
        logger.info("Starting flat capture process...")
        logger.info("Make sure you have a uniform light source (e.g., twilight sky, light box)")
        logger.info("Press Enter to continue or Ctrl+C to cancel...")
        
        try:
            input()
        except KeyboardInterrupt:
            logger.info("Flat capture cancelled by user")
            sys.exit(0)
        
        # Capture flats
        result = flat_capture.capture_flats()
        
        if result.is_success:
            logger.info("✅ Flat capture completed successfully!")
            logger.info(f"Captured files: {len(result.data)}")
            logger.info(f"Output directory: {flat_config['output_dir']}")
            
            if result.details:
                logger.info("Details:")
                for key, value in result.details.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.error(f"❌ Flat capture failed: {result.message}")
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nFlat capture interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 