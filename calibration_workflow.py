#!/usr/bin/env python3
"""
Calibration Workflow Runner

This script provides a unified interface for the complete calibration workflow:
1. Dark frame capture
2. Flat frame capture  
3. Master frame creation

All operations use a single configuration file for consistency and simplicity.

Usage:
    python calibration_workflow.py --config config_calibration_frames.yaml
    python calibration_workflow.py --config config_calibration_frames.yaml --step darks
    python calibration_workflow.py --config config_calibration_frames.yaml --step flats
    python calibration_workflow.py --config config_calibration_frames.yaml --step masters
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
from flat_capture import FlatCapture
from master_frame_creator import MasterFrameCreator
from video_capture import VideoCapture


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'calibration_workflow_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        ]
    )


def main():
    """Main function for calibration workflow."""
    parser = argparse.ArgumentParser(
        description='Complete Calibration Workflow System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Complete calibration workflow (darks + flats + masters)
  python calibration_workflow.py --config config_calibration_frames.yaml
  
  # Individual steps
  python calibration_workflow.py --config config_calibration_frames.yaml --step darks
  python calibration_workflow.py --config config_calibration_frames.yaml --step flats
  python calibration_workflow.py --config config_calibration_frames.yaml --step masters
  
  # Skip confirmation prompts
  python calibration_workflow.py --config config_calibration_frames.yaml --no-confirm
  
  # Debug mode
  python calibration_workflow.py --config config_calibration_frames.yaml --debug
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config_calibration_frames.yaml',
        help='Configuration file path (default: config_calibration_frames.yaml)'
    )
    
    parser.add_argument(
        '--step',
        type=str,
        choices=['darks', 'flats', 'masters', 'all'],
        default='all',
        help='Calibration step to run (default: all)'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Skip confirmation prompts'
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
    logger = logging.getLogger('calibration_workflow')
    
    try:
        # Load configuration
        if not os.path.exists(args.config):
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)
        
        config = ConfigManager(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
        
        # Display workflow information
        logger.info("=" * 60)
        logger.info("CALIBRATION WORKFLOW SYSTEM")
        logger.info("=" * 60)
        
        if args.step == 'all':
            logger.info("Mode: Complete calibration workflow")
            logger.info("Steps: Darks → Flats → Master Frames")
        else:
            logger.info(f"Mode: Single step - {args.step}")
        
        logger.info("=" * 60)
        
        # Initialize video capture (required for all operations)
        logger.info("Initializing video capture...")
        video_capture = VideoCapture(config=config, logger=logger)
        
        if not video_capture.initialize():
            logger.error("Failed to initialize video capture")
            sys.exit(1)
        
        # Run calibration steps
        if args.step in ['darks', 'all']:
            if not run_dark_capture(config, video_capture, logger, args.no_confirm):
                sys.exit(1)
        
        if args.step in ['flats', 'all']:
            if not run_flat_capture(config, video_capture, logger, args.no_confirm):
                sys.exit(1)
        
        if args.step in ['masters', 'all']:
            if not run_master_frame_creation(config, logger, args.no_confirm):
                sys.exit(1)
        
        logger.info("=" * 60)
        logger.info("✅ CALIBRATION WORKFLOW COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        
        # Display summary
        display_summary(config, logger)
        
    except KeyboardInterrupt:
        logger.info("\nCalibration workflow interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def run_dark_capture(config, video_capture, logger, no_confirm):
    """Run dark capture step."""
    logger.info("\n" + "=" * 40)
    logger.info("STEP 1: DARK FRAME CAPTURE")
    logger.info("=" * 40)
    
    try:
        # Initialize dark capture
        dark_capture = DarkCapture(config=config, logger=logger)
        
        if not dark_capture.initialize(video_capture):
            logger.error("Failed to initialize dark capture")
            return False
        
        # Display dark capture settings
        dark_config = config.get_dark_config()
        logger.info("Dark Capture Settings:")
        logger.info(f"  Number of darks per exposure: {dark_config['num_darks']}")
        logger.info(f"  Science exposure time: {dark_config['science_exposure_time']:.3f}s")
        logger.info(f"  Exposure factors: {dark_config['exposure_factors']}")
        logger.info(f"  Output directory: {dark_config['output_dir']}")
        
        # Confirm before starting
        if not no_confirm:
            logger.info("\nMake sure the camera is covered and no light can enter")
            logger.info("Press Enter to start dark capture or Ctrl+C to cancel...")
            try:
                input()
            except KeyboardInterrupt:
                logger.info("Dark capture cancelled by user")
                return False
        
        # Capture darks
        result = dark_capture.capture_darks()
        
        if result.is_success:
            logger.info("✅ Dark capture completed successfully!")
            total_captured = result.details.get('total_captured', 0)
            exposure_times = result.details.get('exposure_times', [])
            logger.info(f"Total frames captured: {total_captured}")
            logger.info(f"Exposure times: {exposure_times}")
            return True
        else:
            logger.error(f"❌ Dark capture failed: {result.message}")
            return False
            
    except Exception as e:
        logger.error(f"Error during dark capture: {e}")
        return False


def run_flat_capture(config, video_capture, logger, no_confirm):
    """Run flat capture step."""
    logger.info("\n" + "=" * 40)
    logger.info("STEP 2: FLAT FRAME CAPTURE")
    logger.info("=" * 40)
    
    try:
        # Initialize flat capture
        flat_capture = FlatCapture(config=config, logger=logger)
        
        if not flat_capture.initialize(video_capture):
            logger.error("Failed to initialize flat capture")
            return False
        
        # Display flat capture settings
        flat_config = config.get_flat_config()
        logger.info("Flat Capture Settings:")
        logger.info(f"  Target count rate: {flat_config['target_count_rate']:.1%}")
        logger.info(f"  Count tolerance: {flat_config['count_tolerance']:.1%}")
        logger.info(f"  Number of flats: {flat_config['num_flats']}")
        logger.info(f"  Output directory: {flat_config['output_dir']}")
        
        # Confirm before starting
        if not no_confirm:
            logger.info("\nMake sure you have a light source set up for flat frames")
            logger.info("Press Enter to start flat capture or Ctrl+C to cancel...")
            try:
                input()
            except KeyboardInterrupt:
                logger.info("Flat capture cancelled by user")
                return False
        
        # Capture flats
        result = flat_capture.capture_flats()
        
        if result.is_success:
            logger.info("✅ Flat capture completed successfully!")
            captured_files = result.data
            logger.info(f"Flat frames captured: {len(captured_files)}")
            return True
        else:
            logger.error(f"❌ Flat capture failed: {result.message}")
            return False
            
    except Exception as e:
        logger.error(f"Error during flat capture: {e}")
        return False


def run_master_frame_creation(config, logger, no_confirm):
    """Run master frame creation step."""
    logger.info("\n" + "=" * 40)
    logger.info("STEP 3: MASTER FRAME CREATION")
    logger.info("=" * 40)
    
    try:
        # Initialize master frame creator
        master_creator = MasterFrameCreator(config=config, logger=logger)
        
        # Display master frame settings
        master_config = config.get_master_config()
        logger.info("Master Frame Settings:")
        logger.info(f"  Output directory: {master_config['output_dir']}")
        logger.info(f"  Rejection method: {master_config['rejection_method']}")
        logger.info(f"  Sigma threshold: {master_config['sigma_threshold']}")
        logger.info(f"  Normalization method: {master_config['normalization_method']}")
        
        # Confirm before starting
        if not no_confirm:
            logger.info("\nThis will process existing dark and flat frames")
            logger.info("Press Enter to start master frame creation or Ctrl+C to cancel...")
            try:
                input()
            except KeyboardInterrupt:
                logger.info("Master frame creation cancelled by user")
                return False
        
        # Create master frames
        result = master_creator.create_all_master_frames()
        
        if result.is_success:
            logger.info("✅ Master frame creation completed successfully!")
            dark_count = result.details.get('dark_count', 0)
            flat_count = result.details.get('flat_count', 0)
            logger.info(f"Master darks created: {dark_count}")
            logger.info(f"Master flats created: {flat_count}")
            return True
        else:
            logger.error(f"❌ Master frame creation failed: {result.message}")
            return False
            
    except Exception as e:
        logger.error(f"Error during master frame creation: {e}")
        return False


def display_summary(config, logger):
    """Display calibration workflow summary."""
    logger.info("\n" + "=" * 60)
    logger.info("CALIBRATION WORKFLOW SUMMARY")
    logger.info("=" * 60)
    
    # Get configuration details
    dark_config = config.get_dark_config()
    flat_config = config.get_flat_config()
    master_config = config.get_master_config()
    
    logger.info("Configuration Used:")
    logger.info(f"  Dark frames per exposure: {dark_config['num_darks']}")
    logger.info(f"  Science exposure time: {dark_config['science_exposure_time']:.3f}s")
    logger.info(f"  Flat frames: {flat_config['num_flats']}")
    logger.info(f"  Target flat count rate: {flat_config['target_count_rate']:.1%}")
    logger.info(f"  Master frame rejection: {master_config['rejection_method']}")
    logger.info(f"  Master frame normalization: {master_config['normalization_method']}")
    
    logger.info("\nOutput Directories:")
    logger.info(f"  Dark frames: {dark_config['output_dir']}")
    logger.info(f"  Flat frames: {flat_config['output_dir']}")
    logger.info(f"  Master frames: {master_config['output_dir']}")
    
    logger.info("\nNext Steps:")
    logger.info("  1. Verify master frame quality")
    logger.info("  2. Apply calibration to science images")
    logger.info("  3. Monitor calibration quality over time")
    
    logger.info("\nCalibration Formula:")
    logger.info("  calibrated_image = (science_image - master_dark) / master_flat")
    
    logger.info("=" * 60)


if __name__ == '__main__':
    main() 