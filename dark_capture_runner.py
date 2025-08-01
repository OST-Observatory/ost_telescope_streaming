#!/usr/bin/env python3
"""
Dark Capture Runner

This script provides a command-line interface for capturing dark frame images
for multiple exposure times to provide comprehensive calibration data.

Usage:
    python dark_capture_runner.py --config config_dark_capture.yaml
    python dark_capture_runner.py --config config_dark_capture.yaml --bias-only
    python dark_capture_runner.py --config config_dark_capture.yaml --science-only
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
from dark_capture import DarkCapture
from video_capture import VideoCapture


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'dark_capture_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        ]
    )


def main():
    """Main function for dark capture runner."""
    parser = argparse.ArgumentParser(
        description='Automatic Dark Frame Capture System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Complete dark capture (all exposure times)
  python dark_capture_runner.py --config config_dark_capture.yaml
  
  # Bias frames only (minimum exposure time)
  python dark_capture_runner.py --config config_dark_capture.yaml --bias-only
  
  # Science darks only (science exposure time)
  python dark_capture_runner.py --config config_dark_capture.yaml --science-only
  
  # Custom number of darks
  python dark_capture_runner.py --config config_dark_capture.yaml --num-darks 30
  
  # Debug mode
  python dark_capture_runner.py --config config_dark_capture.yaml --debug
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config_dark_capture.yaml',
        help='Configuration file path (default: config_dark_capture.yaml)'
    )
    
    parser.add_argument(
        '--num-darks',
        type=int,
        help='Number of dark frames per exposure time (overrides config)'
    )
    
    parser.add_argument(
        '--science-exposure-time',
        type=float,
        help='Science exposure time in seconds (overrides config)'
    )
    
    parser.add_argument(
        '--bias-only',
        action='store_true',
        help='Capture only bias frames (minimum exposure time)'
    )
    
    parser.add_argument(
        '--science-only',
        action='store_true',
        help='Capture only science darks (science exposure time)'
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
    logger = logging.getLogger('dark_capture_runner')
    
    try:
        # Load configuration
        if not os.path.exists(args.config):
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)
        
        config = ConfigManager(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
        
        # Override config settings with command line arguments
        dark_config = config.get_dark_config()
        
        if args.num_darks:
            dark_config['num_darks'] = args.num_darks
            logger.info(f"Number of darks set to: {args.num_darks}")
        
        if args.science_exposure_time:
            dark_config['science_exposure_time'] = args.science_exposure_time
            logger.info(f"Science exposure time set to: {args.science_exposure_time}s")
        
        # Initialize video capture
        logger.info("Initializing video capture...")
        video_capture = VideoCapture(config=config, logger=logger)
        
        if not video_capture.initialize():
            logger.error("Failed to initialize video capture")
            sys.exit(1)
        
        # Initialize dark capture
        logger.info("Initializing dark capture system...")
        dark_capture = DarkCapture(config=config, logger=logger)
        
        if not dark_capture.initialize(video_capture):
            logger.error("Failed to initialize dark capture")
            sys.exit(1)
        
        # Display settings
        logger.info("Dark Capture Settings:")
        logger.info(f"  Number of darks per exposure: {dark_config['num_darks']}")
        logger.info(f"  Science exposure time: {dark_config['science_exposure_time']:.3f}s")
        logger.info(f"  Exposure factors: {dark_config['exposure_factors']}")
        logger.info(f"  Exposure range: {dark_config['min_exposure']:.3f}s - {dark_config['max_exposure']:.1f}s")
        logger.info(f"  Output directory: {dark_config['output_dir']}")
        
        # Determine capture mode
        if args.bias_only:
            logger.info("Mode: Bias frames only")
            capture_mode = "bias"
        elif args.science_only:
            logger.info("Mode: Science darks only")
            capture_mode = "science"
        else:
            logger.info("Mode: Complete dark capture (all exposure times)")
            capture_mode = "complete"
        
        # Start dark capture
        logger.info("Starting dark capture process...")
        logger.info("Make sure the camera is covered and no light can enter")
        logger.info("Press Enter to continue or Ctrl+C to cancel...")
        
        try:
            input()
        except KeyboardInterrupt:
            logger.info("Dark capture cancelled by user")
            sys.exit(0)
        
        # Capture darks based on mode
        if capture_mode == "bias":
            result = dark_capture.capture_bias_only()
        elif capture_mode == "science":
            result = dark_capture.capture_science_darks_only()
        else:
            result = dark_capture.capture_darks()
        
        if result.is_success:
            logger.info("✅ Dark capture completed successfully!")
            
            if capture_mode == "complete":
                total_captured = result.details.get('total_captured', 0)
                exposure_times = result.details.get('exposure_times', [])
                logger.info(f"Total frames captured: {total_captured}")
                logger.info(f"Exposure times: {exposure_times}")
            else:
                captured_files = result.data
                logger.info(f"Captured files: {len(captured_files)}")
            
            logger.info(f"Output directory: {dark_config['output_dir']}")
            
            if result.details:
                logger.info("Details:")
                for key, value in result.details.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.error(f"❌ Dark capture failed: {result.message}")
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nDark capture interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 