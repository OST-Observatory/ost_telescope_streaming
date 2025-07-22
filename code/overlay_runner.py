# overlay_runner.py
import time
import subprocess
import sys
import signal
import os
from datetime import datetime
import logging
from typing import Optional

# Import configuration
from config_manager import config

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
        from config_manager import config as default_config
        import logging
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or default_config
        self.running = True
        self.mount = None
        self.video_processor = None
        self.overlay_generator = None
        self.setup_signal_handlers()
        
        # Load configuration
        streaming_config = self.config.get_streaming_config()
        logging_config = self.config.get_logging_config()
        video_config = self.config.get_video_config()
        
        self.update_interval = streaming_config.get('update_interval', 30)
        self.max_retries = streaming_config.get('max_retries', 3)
        self.retry_delay = streaming_config.get('retry_delay', 5)
        self.use_timestamps = streaming_config.get('use_timestamps', True)
        self.timestamp_format = streaming_config.get('timestamp_format', '%Y%m%d_%H%M%S')
        
        # Video processing settings
        self.video_enabled = video_config.get('plate_solving_enabled', False)
        self.last_solve_result = None
        
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
    
    def generate_overlay_with_coords(self, ra_deg: float, dec_deg: float, output_file: Optional[str] = None) -> OverlayStatus:
        """Generiert ein Overlay für die gegebenen Koordinaten.
        Args:
            ra_deg: Rektaszension in Grad
            dec_deg: Deklination in Grad
            output_file: Optionaler Ausgabedateiname
        Returns:
            OverlayStatus: Status-Objekt mit Ergebnis oder Fehlerinformationen.
        """
        try:
            # Use class-based approach if available
            if self.overlay_generator:
                try:
                    result_file = self.overlay_generator.generate_overlay(ra_deg, dec_deg, output_file)
                    self.logger.info(f"Overlay created successfully: {result_file}")
                    return success_status(
                        f"Overlay created successfully: {result_file}",
                        data=result_file,
                        details={'ra_deg': ra_deg, 'dec_deg': dec_deg}
                    )
                except Exception as e:
                    self.logger.error(f"Error creating overlay: {e}")
                    return error_status(f"Error creating overlay: {e}", details={'ra_deg': ra_deg, 'dec_deg': dec_deg})
            
            # Fallback to subprocess approach
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
                            details={'ra_deg': ra_deg, 'dec_deg': dec_deg, 'method': 'subprocess'}
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
                    
                    # Generate output filename
                    if self.use_timestamps:
                        timestamp = datetime.now().strftime(self.timestamp_format)
                        output_file = f"overlay_{timestamp}.png"
                    else:
                        output_file = None
                    
                    # Create overlay
                    overlay_status = self.generate_overlay_with_coords(ra_deg, dec_deg, output_file)
                    
                    # Video processing is handled automatically by the video processor
                    # Plate-solving results are available via callbacks
                    
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