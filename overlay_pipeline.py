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
  python overlay_pipeline.py
  
  # Run with custom config and 60-second intervals
  python overlay_pipeline.py --config my_config.yaml --interval 60
  
  # Run with debug logging
  python overlay_pipeline.py --debug
  
  # Run with frame processing and plate-solving
  python overlay_pipeline.py --enable-frame-processing --wait-for-plate-solve
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
        '--enable-frame-processing',
        action='store_true',
        help='Enable frame processing and image capture'
    )
    
    parser.add_argument(
        '--enable-cooling',
        action='store_true',
        help='Enable camera cooling during observation'
    )
    
    parser.add_argument(
        '--cooling-temp',
        type=float,
        help='Target temperature for cooling (overrides config)'
    )
    
    parser.add_argument(
        '--wait-for-cooling',
        action='store_true',
        help='Wait for temperature stabilization before starting'
    )
    
    parser.add_argument(
        '--cooling-timeout',
        type=int,
        default=300,
        help='Timeout for cooling stabilization in seconds (default: 300)'
    )
    
    parser.add_argument(
        '--warmup-at-end',
        action='store_true',
        help='Start warmup phase when stopping observation'
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
        
        if args.enable_frame_processing:
            frame_config = config.get_frame_processing_config()
            frame_config['enabled'] = True
            logger.info("Frame processing enabled")
        
        # Handle cooling configuration
        if args.enable_cooling:
            camera_config = config.get_camera_config()
            cooling_config = camera_config.get('cooling', {})
            cooling_config['enable_cooling'] = True
            
            if args.cooling_temp is not None:
                camera_cooling = camera_config.get('cooling', {})
                camera_cooling['target_temperature'] = args.cooling_temp
                logger.info(f"Cooling target temperature set to {args.cooling_temp}°C")
            
            if args.wait_for_cooling:
                cooling_config['wait_for_cooling'] = True
                logger.info("Waiting for temperature stabilization enabled")
            
            if args.cooling_timeout != 300:
                cooling_config['cooling_timeout'] = args.cooling_timeout
                logger.info(f"Cooling timeout set to {args.cooling_timeout} seconds")
            
            if args.warmup_at_end:
                cooling_config['warmup_at_end'] = True
                logger.info("Warmup at end enabled")
            
            logger.info("Camera cooling enabled")
        
        # Create overlay runner (VideoProcessor wird automatisch initialisiert)
        runner = OverlayRunner(config=config, logger=logger)
        
        logger.info("Starting Overlay Runner with image combination...")
        if args.enable_frame_processing:
            logger.info("Frame processing enabled")
        if args.enable_cooling:
            logger.info("Cooling management enabled")
        logger.info("Press Ctrl+C to stop")
        
        # Run the overlay runner (startet VideoProcessor und Hauptschleife)
        try:
            runner.run()
        except KeyboardInterrupt:
            logger.info("\nStopping observation session...")
            
            # Stop observation with warmup if enabled
            stop_status = runner.stop_observation()
            if stop_status.is_success:
                logger.info("✅ Observation session stopped successfully")
            else:
                logger.warning(f"Session stop: {stop_status.message}")
            
            logger.info("Stopped by user")
            
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 