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
import signal
from pathlib import Path
from datetime import datetime

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
from dark_capture import DarkCapture
from video_capture import VideoCapture
from cooling_manager import create_cooling_manager


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
        description='Automatic Dark Frame Capture System with Cooling Management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Complete dark capture (all exposure times) with cooling
  python dark_capture_runner.py --config config_dark_capture.yaml
  
  # Bias frames only (minimum exposure time) with cooling
  python dark_capture_runner.py --config config_dark_capture.yaml --bias-only
  
  # Science darks only (science exposure time) with cooling
  python dark_capture_runner.py --config config_dark_capture.yaml --science-only
  
  # Custom number of darks with cooling
  python dark_capture_runner.py --config config_dark_capture.yaml --num-darks 30
  
  # Debug mode with cooling
  python dark_capture_runner.py --config config_dark_capture.yaml --debug
  
  # Skip cooling (not recommended for scientific imaging)
  python dark_capture_runner.py --config config_dark_capture.yaml --skip-cooling
  
  # Skip warmup (not recommended for camera protection)
  python dark_capture_runner.py --config config_dark_capture.yaml --skip-warmup
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
    
    parser.add_argument(
        '--skip-cooling',
        action='store_true',
        help='Skip cooling initialization (not recommended for scientific imaging)'
    )
    
    parser.add_argument(
        '--skip-warmup',
        action='store_true',
        help='Skip warmup phase (not recommended for camera protection)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    if args.debug:
        log_level = logging.DEBUG
    
    setup_logging(log_level)
    logger = logging.getLogger('dark_capture_runner')
    
    # Global variables for signal handling
    global_dark_capture = None
    global_cooling_manager = None
    global_shutdown_in_progress = False
    
    def signal_handler(signum, frame):
        """Handle Ctrl+C signal."""
        nonlocal global_shutdown_in_progress
        
        if global_shutdown_in_progress:
            logger.info("\nShutdown already in progress, forcing exit...")
            sys.exit(1)
        
        global_shutdown_in_progress = True
        logger.info("\nReceived interrupt signal, stopping dark capture...")
        
        try:
            # Start warmup if cooling manager is available
            if global_cooling_manager and not args.skip_warmup:
                logger.info("Starting warmup phase...")
                warmup_status = global_cooling_manager.start_warmup()
                if warmup_status.is_success:
                    logger.info("🔥 Warmup started successfully")
                    
                    # Wait for warmup to complete
                    logger.info("🔥 Waiting for warmup to complete...")
                    wait_status = global_cooling_manager.wait_for_warmup_completion(timeout=600)
                    if wait_status.is_success:
                        logger.info("🔥 Warmup completed successfully")
                    else:
                        logger.warning(f"Warmup issue: {wait_status.message}")
                else:
                    logger.warning(f"Warmup start: {warmup_status.message}")
            
            logger.info("Dark capture stopped by user")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            sys.exit(1)
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
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
        
        # Initialize cooling if not skipped
        if not args.skip_cooling:
            logger.info("Initializing cooling system...")
            if hasattr(video_capture, 'camera') and video_capture.camera:
                global_cooling_manager = create_cooling_manager(video_capture.camera, config, logger)
                
                # Get cooling configuration
                cooling_config = config.get_camera_config().get('cooling', {})
                target_temp = cooling_config.get('target_temperature', -10.0)
                wait_for_cooling = cooling_config.get('wait_for_cooling', True)
                cooling_timeout = cooling_config.get('cooling_timeout', 300)
                
                logger.info(f"Setting cooling target temperature to {target_temp}°C")
                
                # Set target temperature
                set_status = global_cooling_manager.set_target_temperature(target_temp)
                if not set_status.is_success:
                    logger.warning(f"Failed to set target temperature: {set_status.message}")
                
                # Wait for stabilization if required
                if wait_for_cooling:
                    logger.info("Waiting for temperature stabilization...")
                    stabilization_status = global_cooling_manager.wait_for_stabilization(timeout=cooling_timeout)
                    if not stabilization_status.is_success:
                        logger.warning(f"Temperature stabilization: {stabilization_status.message}")
                    else:
                        logger.info("✅ Cooling initialized and stabilized successfully")
                else:
                    logger.info("✅ Cooling initialized (stabilization skipped)")
            else:
                logger.warning("No camera available for cooling")
        else:
            logger.info("Cooling initialization skipped")
        
        # Initialize dark capture
        logger.info("Initializing dark capture system...")
        dark_capture = DarkCapture(config=config, logger=logger)
        global_dark_capture = dark_capture
        
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
            
            # Start warmup if cooling was used and not skipped
            if global_cooling_manager and not args.skip_warmup:
                logger.info("=== WARMUP PHASE ===")
                logger.info("Starting warmup phase to prevent thermal shock...")
                
                warmup_status = global_cooling_manager.start_warmup()
                if warmup_status.is_success:
                    logger.info("🔥 Warmup started successfully")
                    
                    # Wait for warmup to complete
                    logger.info("🔥 Waiting for warmup to complete...")
                    wait_status = global_cooling_manager.wait_for_warmup_completion(timeout=600)
                    if wait_status.is_success:
                        logger.info("🔥 Warmup completed successfully")
                        logger.info("💡 Camera is now safe to disconnect")
                    else:
                        logger.warning(f"Warmup issue: {wait_status.message}")
                else:
                    logger.warning(f"Warmup start: {warmup_status.message}")
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