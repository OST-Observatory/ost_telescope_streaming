#!/usr/bin/env python3
"""
Calibration Workflow with Cooling Management.

This script provides a complete calibration workflow including:
- Cooling initialization and stabilization
- Dark frame capture with cooling
- Flat frame capture with cooling
- Master frame creation
- Warmup phase at the end
"""

import sys
import logging
import argparse
import time
import signal
from pathlib import Path

# Add the code directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "code"))

from config_manager import ConfigManager
from dark_capture import DarkCapture
from flat_capture import FlatCapture
from master_frame_creator import MasterFrameCreator
from cooling_manager import create_cooling_manager
from status import success_status, error_status, warning_status


def setup_logging(level='INFO'):
    """Setup logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("calibration_workflow")


def initialize_cooling(config, logger):
    """Initialize cooling system."""
    try:
        # Get camera configuration
        camera_config = config.get_camera_config()
        camera_type = camera_config.get('camera_type', 'opencv')
        
        if camera_type == 'opencv':
            logger.warning("Cooling not supported for OpenCV cameras")
            return None, success_status("Cooling not applicable for OpenCV")
        
        # Create camera instance
        if camera_type == 'ascom':
            from ascom_camera import ASCOMCamera
            camera_config = config.get_camera_config()
            ascom_config = camera_config.get('ascom', {})
            camera = ASCOMCamera(
                driver_id=ascom_config.get('driver_id'),
                config=config,
                logger=logger
            )
        elif camera_type == 'alpaca':
            from alpaca_camera import AlpycaCameraWrapper
            camera_config = config.get_camera_config()
            alpaca_config = camera_config.get('alpaca', {})
            camera = AlpycaCameraWrapper(
                host=alpaca_config.get('host', 'localhost'),
                port=alpaca_config.get('port', 11111),
                device_id=alpaca_config.get('device_id', 0),
                config=config,
                logger=logger
            )
        else:
            return None, error_status(f"Unsupported camera type: {camera_type}")
        
        # Connect to camera
        connect_status = camera.connect()
        if not connect_status.is_success:
            return None, connect_status
        
        # Create cooling manager
        cooling_manager = create_cooling_manager(camera, config, logger)
        
        # Initialize cooling
        cooling_config = config.get_camera_config().get('cooling', {})
        target_temp = cooling_config.get('target_temperature', -10.0)
        wait_for_cooling = cooling_config.get('wait_for_cooling', True)
        cooling_timeout = cooling_config.get('cooling_timeout', 300)
        
        logger.info(f"Initializing cooling to {target_temp}°C")
        
        # Set target temperature
        set_status = cooling_manager.set_target_temperature(target_temp)
        if not set_status.is_success:
            return camera, set_status
        
        # Wait for stabilization if required
        if wait_for_cooling:
            logger.info("Waiting for temperature stabilization...")
            stabilization_status = cooling_manager.wait_for_stabilization(
                timeout=cooling_timeout
            )
            
            if not stabilization_status.is_success:
                logger.warning(f"Temperature stabilization: {stabilization_status.message}")
                return camera, warning_status(f"Cooling initialized but stabilization failed: {stabilization_status.message}")
            else:
                logger.info("✅ Cooling initialized and stabilized successfully")
        
        return camera, success_status("Cooling initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize cooling: {e}")
        return None, error_status(f"Failed to initialize cooling: {e}")


def capture_darks_with_cooling(config, logger, camera=None):
    """Capture dark frames with cooling management."""
    try:
        logger.info("=== DARK FRAME CAPTURE WITH COOLING ===")
        
        # Initialize cooling if not already done
        if camera is None:
            camera, cooling_status = initialize_cooling(config, logger)
            if not cooling_status.is_success:
                return cooling_status
        
        # Initialize video capture
        logger.info("Initializing video capture...")
        from video_capture import VideoCapture
        video_capture = VideoCapture(config=config, logger=logger)
        
        # Check if camera was initialized successfully
        if not video_capture.camera:
            logger.error("Failed to initialize video capture - no camera available")
            return error_status("Failed to initialize video capture - no camera available")
        
        # Create dark capture instance and initialize it
        dark_capture = DarkCapture(config, logger)
        if not dark_capture.initialize(video_capture):
            logger.error("Failed to initialize dark capture")
            return error_status("Failed to initialize dark capture")
        
        # Capture dark frames
        logger.info("Starting dark frame capture...")
        status = dark_capture.capture_darks()
        
        if status.is_success:
            logger.info("✅ Dark frame capture completed successfully")
        else:
            logger.error(f"❌ Dark frame capture failed: {status.message}")
        
        return status
        
    except Exception as e:
        logger.error(f"Error during dark capture: {e}")
        return error_status(f"Error during dark capture: {e}")


def capture_flats_with_cooling(config, logger, camera=None):
    """Capture flat frames with cooling management."""
    try:
        logger.info("=== FLAT FRAME CAPTURE WITH COOLING ===")
        
        # Initialize cooling if not already done
        if camera is None:
            camera, cooling_status = initialize_cooling(config, logger)
            if not cooling_status.is_success:
                return cooling_status
        
        # Initialize video capture
        logger.info("Initializing video capture...")
        from video_capture import VideoCapture
        video_capture = VideoCapture(config=config, logger=logger)
        
        # Check if camera was initialized successfully
        if not video_capture.camera:
            logger.error("Failed to initialize video capture - no camera available")
            return error_status("Failed to initialize video capture - no camera available")
        
        # Create flat capture instance and initialize it
        flat_capture = FlatCapture(config, logger)
        if not flat_capture.initialize(video_capture):
            logger.error("Failed to initialize flat capture")
            return error_status("Failed to initialize flat capture")
        
        # Capture flat frames
        logger.info("Starting flat frame capture...")
        status = flat_capture.capture_flats()
        
        if status.is_success:
            logger.info("✅ Flat frame capture completed successfully")
        else:
            logger.error(f"❌ Flat frame capture failed: {status.message}")
        
        return status
        
    except Exception as e:
        logger.error(f"Error during flat capture: {e}")
        return error_status(f"Error during flat capture: {e}")


def create_master_frames(config, logger):
    """Create master frames."""
    try:
        logger.info("=== MASTER FRAME CREATION ===")
        
        # Create master frame creator
        master_creator = MasterFrameCreator(config, logger)
        
        # Create master frames
        logger.info("Creating master frames...")
        status = master_creator.create_all_masters()
        
        if status.is_success:
            logger.info("✅ Master frame creation completed successfully")
        else:
            logger.error(f"❌ Master frame creation failed: {status.message}")
        
        return status
        
    except Exception as e:
        logger.error(f"Error during master frame creation: {e}")
        return error_status(f"Error during master frame creation: {e}")


def start_warmup(camera, config, logger):
    """Start warmup phase and wait for completion."""
    try:
        logger.info("=== WARMUP PHASE ===")
        
        if camera is None:
            logger.warning("No camera available for warmup")
            return success_status("Warmup skipped - no camera")
        
        # Create cooling manager
        cooling_manager = create_cooling_manager(camera, config, logger)
        
        # Start warmup
        logger.info("Starting warmup phase to prevent thermal shock...")
        warmup_status = cooling_manager.start_warmup()
        
        if warmup_status.is_success:
            logger.info("🔥 Warmup started successfully")
            
            # Wait for warmup to complete
            logger.info("🔥 Waiting for warmup to complete...")
            wait_status = cooling_manager.wait_for_warmup_completion(timeout=600)
            if wait_status.is_success:
                logger.info("🔥 Warmup completed successfully")
                logger.info("💡 Camera is now safe to disconnect")
            else:
                logger.warning(f"Warmup issue: {wait_status.message}")
            
            return wait_status
        else:
            logger.warning(f"Warmup start: {warmup_status.message}")
            return warmup_status
        
    except Exception as e:
        logger.error(f"Error during warmup: {e}")
        return error_status(f"Error during warmup: {e}")


def main():
    """Main calibration workflow."""
    parser = argparse.ArgumentParser(description="Calibration Workflow with Cooling Management")
    parser.add_argument("--config", type=str, required=True, help="Configuration file path")
    parser.add_argument("--darks-only", action='store_true', help="Capture only dark frames")
    parser.add_argument("--flats-only", action='store_true', help="Capture only flat frames")
    parser.add_argument("--masters-only", action='store_true', help="Create only master frames")
    parser.add_argument("--skip-cooling", action='store_true', help="Skip cooling initialization")
    parser.add_argument("--skip-warmup", action='store_true', help="Skip warmup phase")
    parser.add_argument("--log-level", type=str, default='INFO', help="Logging level")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_level)
    
    # Global variables for signal handling
    global_camera = None
    global_cooling_manager = None
    global_shutdown_in_progress = False
    
    def signal_handler(signum, frame):
        """Handle Ctrl+C signal."""
        nonlocal global_shutdown_in_progress
        
        if global_shutdown_in_progress:
            logger.info("\nShutdown already in progress, forcing exit...")
            sys.exit(1)
        
        global_shutdown_in_progress = True
        logger.info("\nReceived interrupt signal, stopping calibration workflow...")
        
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
            
            # Disconnect camera
            if global_camera:
                global_camera.disconnect()
                logger.info("Camera disconnected")
            
            logger.info("Calibration workflow stopped by user")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            sys.exit(1)
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Load configuration
        config = ConfigManager(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
        
        camera = None
        cooling_status = None
        
        # Initialize cooling unless skipped
        if not args.skip_cooling:
            camera, cooling_status = initialize_cooling(config, logger)
            global_camera = camera  # Set global variable for signal handler
            
            if not cooling_status.is_success:
                logger.error(f"Cooling initialization failed: {cooling_status.message}")
                if cooling_status.level.value == 'ERROR':
                    return 1
            
            # Get cooling manager for signal handler
            if camera:
                global_cooling_manager = create_cooling_manager(camera, config, logger)
        
        # Run calibration workflow
        if args.darks_only:
            status = capture_darks_with_cooling(config, logger, camera)
        elif args.flats_only:
            status = capture_flats_with_cooling(config, logger, camera)
        elif args.masters_only:
            status = create_master_frames(config, logger)
        else:
            # Full workflow
            logger.info("=== FULL CALIBRATION WORKFLOW ===")
            
            # Capture dark frames
            dark_status = capture_darks_with_cooling(config, logger, camera)
            if not dark_status.is_success:
                logger.error(f"Dark capture failed: {dark_status.message}")
            
            # Capture flat frames
            flat_status = capture_flats_with_cooling(config, logger, camera)
            if not flat_status.is_success:
                logger.error(f"Flat capture failed: {flat_status.message}")
            
            # Create master frames
            master_status = create_master_frames(config, logger)
            if not master_status.is_success:
                logger.error(f"Master frame creation failed: {master_status.message}")
            
            # Overall status
            if all(s.is_success for s in [dark_status, flat_status, master_status]):
                status = success_status("Full calibration workflow completed successfully")
            else:
                status = warning_status("Calibration workflow completed with some issues")
        
        # Start warmup unless skipped
        if not args.skip_warmup and camera:
            warmup_status = start_warmup(camera, config, logger)
            if not warmup_status.is_success:
                logger.warning(f"Warmup failed: {warmup_status.message}")
        
        # Disconnect camera
        if camera:
            camera.disconnect()
            logger.info("Camera disconnected")
        
        # Final status
        if status.is_success:
            logger.info("🎉 Calibration workflow completed successfully!")
            return 0
        else:
            logger.error(f"❌ Calibration workflow failed: {status.message}")
            return 1
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 