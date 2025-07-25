# overlay_runner.py
import time
import subprocess
import sys
import signal
import os
from datetime import datetime
import logging
from typing import Optional, Tuple


# Import with error handling
try:
    from ascom_mount import ASCOMMount
    MOUNT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: ASCOM mount not available: {e}")
    MOUNT_AVAILABLE = False

try:
    from video_processor import VideoProcessor
    VIDEO_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Video processor not available: {e}")
    VIDEO_AVAILABLE = False

try:
    from generate_overlay import OverlayGenerator
    OVERLAY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Overlay generator not available: {e}")
    OVERLAY_AVAILABLE = False

from exceptions import MountError, OverlayError, VideoProcessingError
from status import MountStatus, OverlayStatus, success_status, error_status, warning_status

class OverlayRunner:
    def __init__(self, config=None, logger=None):
        from config_manager import ConfigManager
        default_config = ConfigManager()
        import logging
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or default_config
        self.running = True
        self.mount = None
        self.video_processor = None
        self.overlay_generator = None
        self.setup_signal_handlers()
        
        # Update config access for overlay update and display settings
        overlay_config = self.config.get_overlay_config()
        update_config = overlay_config.get('update', {})
        display_config = overlay_config.get('display', {})
        self.update_interval = update_config.get('update_interval', 30)
        self.max_retries = update_config.get('max_retries', 3)
        self.retry_delay = update_config.get('retry_delay', 5)
        self.use_timestamps = overlay_config.get('use_timestamps', False)
        self.timestamp_format = overlay_config.get('timestamp_format', '%Y%m%d_%H%M%S')
        
        # Video processing settings
        self.video_enabled = self.config.get_video_config().get('video_enabled', True)  # Enable video processing by default
        self.plate_solving_enabled = self.config.get_plate_solve_config().get('auto_solve', False)
        self.last_solve_result = None
        self.wait_for_plate_solve = self.config.get_overlay_config().get('wait_for_plate_solve', False)
        
        # Initialize overlay generator if available
        if OVERLAY_AVAILABLE:
            try:
                self.overlay_generator = OverlayGenerator()
                self.logger.info("Overlay generator initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize overlay generator: {e}")
                self.overlay_generator = None
        
    def setup_signal_handlers(self):
        """Sets up signal handlers for clean shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"\nSignal {signum} received. Shutting down...")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def generate_overlay_with_coords(self, ra_deg: float, dec_deg: float, output_file: Optional[str] = None,
                                   fov_width_deg: Optional[float] = None, fov_height_deg: Optional[float] = None,
                                   position_angle_deg: Optional[float] = None, image_size: Optional[Tuple[int, int]] = None) -> OverlayStatus:
        """Generiert ein Overlay für die gegebenen Koordinaten.
        Args:
            ra_deg: Rektaszension in Grad
            dec_deg: Deklination in Grad
            output_file: Optionaler Ausgabedateiname
            fov_width_deg: Field of view width in degrees (from plate-solving)
            fov_height_deg: Field of view height in degrees (from plate-solving)
            position_angle_deg: Position angle in degrees (from plate-solving)
            image_size: Image size as (width, height) in pixels (from camera)
        Returns:
            OverlayStatus: Status-Objekt mit Ergebnis oder Fehlerinformationen.
        """
        try:
            # Use class-based approach if available
            if self.overlay_generator:
                try:
                    result_file = self.overlay_generator.generate_overlay(
                        ra_deg, dec_deg, output_file, 
                        fov_width_deg, fov_height_deg, position_angle_deg, image_size
                    )
                    self.logger.info(f"Overlay created successfully: {result_file}")
                    return success_status(
                        f"Overlay created successfully: {result_file}",
                        data=result_file,
                        details={'ra_deg': ra_deg, 'dec_deg': dec_deg, 'fov_width_deg': fov_width_deg, 'fov_height_deg': fov_height_deg, 'position_angle_deg': position_angle_deg, 'image_size': image_size}
                    )
                except Exception as e:
                    self.logger.error(f"Error creating overlay: {e}")
                    return error_status(f"Error creating overlay: {e}", details={'ra_deg': ra_deg, 'dec_deg': dec_deg})
            
            # Fallback to subprocess approach
            #   TODO: Remove this fallback in the future when the overlay generator works consistently
            else:
                self.logger.warning("Using subprocess fallback for overlay generation")
                cmd = [
                    sys.executable,  # Current Python interpreter
                    "generate_overlay.py",
                    "--ra", str(ra_deg),
                    "--dec", str(dec_deg)
                ]
                
                if output_file:
                    cmd.extend(["--output", output_file])
                
                # Add new parameters if provided
                if fov_width_deg is not None:
                    cmd.extend(["--fov-width", str(fov_width_deg)])
                if fov_height_deg is not None:
                    cmd.extend(["--fov-height", str(fov_height_deg)])
                if position_angle_deg is not None:
                    cmd.extend(["--position-angle", str(position_angle_deg)])
                if image_size is not None:
                    cmd.extend(["--image-width", str(image_size[0]), "--image-height", str(image_size[1])])
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,  # Timeout after 60 seconds
                        cwd=os.path.dirname(os.path.abspath(__file__))  # Working directory
                    )
                    
                    if result.returncode == 0:
                        self.logger.info("Overlay created successfully")
                        if result.stdout:
                            self.logger.info(result.stdout.strip())
                        return success_status(
                            "Overlay created successfully via subprocess",
                            data=output_file,
                            details={'ra_deg': ra_deg, 'dec_deg': dec_deg, 'method': 'subprocess', 'fov_width_deg': fov_width_deg, 'fov_height_deg': fov_height_deg, 'position_angle_deg': position_angle_deg, 'image_size': image_size}
                        )
                    else:
                        error_msg = result.stderr.strip() if result.stderr else "Unknown subprocess error"
                        self.logger.error(f"Error creating overlay: {error_msg}")
                        return error_status(f"Subprocess error: {error_msg}", details={'ra_deg': ra_deg, 'dec_deg': dec_deg})
                        
                except subprocess.TimeoutExpired:
                    self.logger.error("Timeout while creating overlay")
                    return error_status("Timeout while creating overlay", details={'ra_deg': ra_deg, 'dec_deg': dec_deg})
                except Exception as e:
                    self.logger.error(f"Unexpected error: {e}")
                    return error_status(f"Unexpected error: {e}", details={'ra_deg': ra_deg, 'dec_deg': dec_deg})
                    
        except Exception as e:
            return error_status(f"Overlay generation failed: {e}", details={'ra_deg': ra_deg, 'dec_deg': dec_deg})

    def run(self) -> None:
        """Main loop of the overlay runner."""
        if not MOUNT_AVAILABLE:
            self.logger.error("ASCOM mount not available. Exiting.")
            return
            
        try:
            self.mount = ASCOMMount()
            self.logger.info("Overlay Runner started")
            self.logger.info(f"Update interval: {self.update_interval} seconds")
            
            # Initialize video processor if available and enabled
            if VIDEO_AVAILABLE and self.video_enabled:
                try:
                    self.video_processor = VideoProcessor()
                    
                    # Set up callbacks
                    def on_solve_result(result):
                        self.last_solve_result = result
                        self.logger.info(f"Plate-solving result: RA={result.ra_center:.4f}°, Dec={result.dec_center:.4f}°")
                    
                    def on_error(error):
                        self.logger.error(f"Video processing error: {error}")
                    
                    self.video_processor.set_callbacks(
                        on_solve_result=on_solve_result,
                        on_error=on_error
                    )
                    
                    if self.video_processor.start():
                        self.logger.info("Video processor started")
                    else:
                        self.logger.error("Failed to start video processor")
                        self.video_processor = None
                except Exception as e:
                    self.logger.error(f"Error initializing video processor: {e}")
                    self.video_processor = None
            else:
                self.logger.info("Video processing disabled or not available")
            
            consecutive_failures = 0
            
            while self.running:
                try:
                    # Read coordinates
                    mount_status = self.mount.get_coordinates()
                    
                    if not mount_status.is_success:
                        consecutive_failures += 1
                        self.logger.error(f"Failed to get coordinates: {mount_status.message}")
                        
                        if consecutive_failures >= self.max_retries:
                            self.logger.error(f"Too many consecutive errors ({consecutive_failures}). Exiting.")
                            break
                        
                        self.logger.info(f"Waiting {self.retry_delay} seconds before retry...")
                        time.sleep(self.retry_delay)
                        continue
                    
                    # Extract coordinates from status
                    ra_deg, dec_deg = mount_status.data
                    
                    # Video processing is handled automatically by the video processor
                    # Plate-solving results are available via callbacks
                    
                    # Wait for plate-solving result if required
                    if self.wait_for_plate_solve:
                        self.logger.info("Waiting for plate-solving result before generating overlay...")
                        while self.last_solve_result is None and self.running:
                            time.sleep(0.5)
                        if not self.running:
                            break
                        # Use plate-solving results for coordinates and parameters
                        ra_deg = self.last_solve_result.ra_center
                        dec_deg = self.last_solve_result.dec_center
                        fov_width_deg = self.last_solve_result.fov_width
                        fov_height_deg = self.last_solve_result.fov_height
                        position_angle_deg = self.last_solve_result.position_angle
                        image_size = self.last_solve_result.image_size
                        self.logger.info(f"Using plate-solving results: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°, FOV={fov_width_deg:.3f}°x{fov_height_deg:.3f}°, PA={position_angle_deg:.1f}°")
                    else:
                        # Use mount coordinates and default values
                        fov_width_deg = None
                        fov_height_deg = None
                        position_angle_deg = None
                        image_size = None
                        # Try to get image size from video config
                        try:
                            video_config = self.config.get_video_config()
                            if video_config.get('camera_type') == 'opencv':
                                opencv_config = video_config.get('opencv', {})
                                width = opencv_config.get('frame_width', 1920)
                                height = opencv_config.get('frame_height', 1080)
                                image_size = (width, height)
                        except Exception as e:
                            self.logger.warning(f"Could not get image size from config: {e}")
                    
                    # Generate output filename
                    if self.use_timestamps:
                        timestamp = datetime.now().strftime(self.timestamp_format)
                        output_file = f"overlay_{timestamp}.png"
                    else:
                        output_file = "overlay.png"
                    
                    # Create overlay with all available parameters
                    overlay_status = self.generate_overlay_with_coords(
                        ra_deg, dec_deg, output_file,
                        fov_width_deg, fov_height_deg, position_angle_deg, image_size
                    )
                    
                    if overlay_status.is_success:
                        consecutive_failures = 0
                        self.logger.info(f"Status: OK | Coordinates: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°")
                    else:
                        consecutive_failures += 1
                        self.logger.error(f"Error #{consecutive_failures}: {overlay_status.message}")
                        
                        if consecutive_failures >= self.max_retries:
                            self.logger.error(f"Too many consecutive errors ({consecutive_failures}). Exiting.")
                            break
                    
                    # Wait until next update
                    if self.running:
                        self.logger.info(f"Waiting {self.update_interval} seconds...")
                        time.sleep(self.update_interval)
                        
                except KeyboardInterrupt:
                    self.logger.info("\nStopped by user.")
                    break
                except Exception as e:
                    consecutive_failures += 1
                    self.logger.error(f"Error in main loop: {e}")
                    
                    if consecutive_failures >= self.max_retries:
                        self.logger.error(f"Too many consecutive errors ({consecutive_failures}). Exiting.")
                        break
                    
                    self.logger.info(f"Waiting {self.retry_delay} seconds before retry...")
                    time.sleep(self.retry_delay)
                    
        except Exception as e:
            self.logger.critical(f"Critical error: {e}")
        finally:
            if self.mount:
                disconnect_status = self.mount.disconnect()
                if not disconnect_status.is_success:
                    self.logger.warning(f"Error during disconnect: {disconnect_status.message}")
            if self.video_processor:
                self.video_processor.stop()
            self.logger.info("Overlay Runner stopped.")