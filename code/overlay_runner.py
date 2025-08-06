# overlay_runner.py
import time
import subprocess
import sys
import signal
import os
from datetime import datetime
import logging
from typing import Optional, Tuple, Dict, Any


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
from status import MountStatus, OverlayStatus, success_status, error_status, warning_status, Status

class OverlayRunner:
    def __init__(self, config, logger=None):
        """Initialize overlay runner with cooling support."""
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Overlay configuration
        overlay_config = config.get_overlay_config()
        self.update_interval = overlay_config.get('update', {}).get('update_interval', 30)
        self.wait_for_plate_solve = overlay_config.get('wait_for_plate_solve', False)
        
        # Frame processing configuration
        frame_config = config.get_frame_processing_config()
        self.frame_enabled = frame_config.get('enabled', False)
        
        # Get cooling settings from camera config
        camera_config = config.get_camera_config()
        self.enable_cooling = camera_config.get('cooling', {}).get('enable_cooling', False)
        
        # Components
        self.video_processor = None
        self.cooling_manager = None
        
        # State
        self.running = False
        self.last_update = None
        self.last_solve_result = None
        
        # Retry configuration
        self.max_retries = overlay_config.get('update', {}).get('max_retries', 3)
        self.retry_delay = overlay_config.get('update', {}).get('retry_delay', 5)
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize video processor and cooling manager."""
        try:
            if self.frame_enabled and VIDEO_AVAILABLE:
                self.video_processor = VideoProcessor(self.config, self.logger)
                
                # Cooling manager will be initialized after video capture is available
                
                # Start observation session immediately
                session_status = self.video_processor.start_observation_session()
                if session_status.is_success:
                    self.logger.info("Observation session started successfully")
                else:
                    self.logger.error(f"Failed to start observation session: {session_status.message}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
    
    def start_observation(self) -> Status:
        """Start observation session with cooling initialization."""
        try:
            self.logger.info("Starting observation session...")
            
            # Video processor observation session is already started in _initialize_components
            if self.video_processor:
                self.logger.info("Video processor observation session already active")
                
                # Try to initialize cooling manager now that video capture should be available
                if self.enable_cooling and not self.cooling_manager:
                    self._initialize_cooling_manager()
            
            self.running = True
            self.last_update = datetime.now()
            
            return success_status("Overlay runner observation session ready")
            
        except Exception as e:
            self.logger.error(f"Failed to start observation: {e}")
            return error_status(f"Failed to start observation: {e}")
    
    def stop_observation(self) -> Status:
        """Stop observation session with optional warmup."""
        try:
            self.logger.info("Stopping observation session...")
            
            # Stop the main loop first
            self.running = False
            
            # Stop video processor processing immediately to stop all captures
            # but keep camera connection alive for cooling operations
            if self.video_processor:
                self.logger.info("Stopping video processor processing...")
                stop_status = self.video_processor.stop_processing_only()
                if not stop_status.is_success:
                    self.logger.warning(f"Failed to stop video processor: {stop_status.message}")
                else:
                    self.logger.info("Video processor processing stopped successfully")
            
            # Stop cooling with warmup if enabled
            if self.cooling_manager:
                # Shutdown cooling manager (starts warmup if cooling was active)
                shutdown_status = self.cooling_manager.shutdown()
                if shutdown_status.is_success:
                    self.logger.info("🌡️  Cooling manager shutdown initiated")
                    
                    # If warmup was started, wait for it to complete
                    if self.cooling_manager.is_warming_up:
                        self.logger.info("🔥 Waiting for warmup to complete before stopping other components...")
                        warmup_status = self.cooling_manager.wait_for_warmup_completion(timeout=600)
                        if not warmup_status.is_success:
                            self.logger.warning(f"Warmup issue: {warmup_status.message}")
                        else:
                            self.logger.info("🔥 Warmup completed, now stopping other components")
                else:
                    self.logger.warning(f"Failed to shutdown cooling manager: {shutdown_status.message}")
                
                # Now stop the status monitor
                stop_status = self.cooling_manager.stop_status_monitor()
                if stop_status.is_success:
                    self.logger.info("🌡️  Cooling status monitor stopped")
                else:
                    self.logger.warning(f"Failed to stop cooling status monitor: {stop_status.message}")
            
            return success_status("Observation session stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to stop observation: {e}")
            return error_status(f"Failed to stop observation: {e}")
    
    def finalize_shutdown(self) -> Status:
        """Finalize shutdown after warmup is complete."""
        try:
            self.logger.info("Finalizing shutdown...")
            
            # Disconnect camera after warmup is complete
            if self.video_processor:
                disconnect_status = self.video_processor.disconnect_camera()
                if not disconnect_status.is_success:
                    self.logger.warning(f"Failed to disconnect camera: {disconnect_status.message}")
            
            self.logger.info("Shutdown sequence completed")
            
            return success_status("Shutdown finalized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to finalize shutdown: {e}")
            return error_status(f"Failed to finalize shutdown: {e}")
    
    def _initialize_cooling_manager(self) -> bool:
        """Initialize cooling manager after video capture is available."""
        if not self.enable_cooling:
            return False
            
        try:
            # Try to get cooling manager from video processor
            if hasattr(self.video_processor, 'video_capture') and self.video_processor.video_capture:
                if hasattr(self.video_processor.video_capture, 'cooling_manager') and self.video_processor.video_capture.cooling_manager:
                    self.cooling_manager = self.video_processor.video_capture.cooling_manager
                    self.logger.info("Cooling manager initialized from video capture")
                    
                    # Start cooling status monitor automatically
                    cooling_config = self.config.get_camera_config().get('cooling', {})
                    status_interval = cooling_config.get('status_interval', 30)
                    
                    monitor_status = self.cooling_manager.start_status_monitor(interval=status_interval)
                    if monitor_status.is_success:
                        self.logger.info(f"🌡️  Cooling status monitor started automatically (interval: {status_interval}s)")
                        return True
                    else:
                        self.logger.warning(f"Failed to start cooling status monitor: {monitor_status.message}")
                        return False
                else:
                    self.logger.warning("Cooling enabled but no cooling manager available in video capture")
                    return False
            else:
                self.logger.debug("Cooling enabled but video capture not yet available")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize cooling manager: {e}")
            return False
    
    def get_cooling_status(self) -> Dict[str, Any]:
        """Get current cooling status."""
        if self.cooling_manager:
            return self.cooling_manager.get_cooling_status()
        return {}
    
    def generate_overlay_with_coords(self, ra_deg: float, dec_deg: float, output_file: Optional[str] = None,
                                   fov_width_deg: Optional[float] = None, fov_height_deg: Optional[float] = None,
                                   position_angle_deg: Optional[float] = None, image_size: Optional[Tuple[int, int]] = None,
                                   mag_limit: Optional[float] = None, is_flipped: Optional[bool] = None) -> OverlayStatus:
        """Generate astronomical overlay with given coordinates."""
        if not OVERLAY_AVAILABLE:
            return error_status("Overlay generator not available")
        
        try:
            overlay_generator = OverlayGenerator(self.config, self.logger)
            
            # Generate overlay
            overlay_status = overlay_generator.generate_overlay(
                ra_deg=ra_deg,
                dec_deg=dec_deg,
                output_file=output_file,
                fov_width_deg=fov_width_deg,
                fov_height_deg=fov_height_deg,
                position_angle_deg=position_angle_deg,
                image_size=image_size,
                mag_limit=mag_limit,
                is_flipped=is_flipped
            )
            
            if overlay_status.is_success:
                self.logger.info(f"Overlay generated successfully: {overlay_status.data}")
            else:
                self.logger.warning(f"Overlay generation failed: {overlay_status.message}")
            
            return overlay_status
            
        except Exception as e:
            self.logger.error(f"Error generating overlay: {e}")
            return error_status(f"Error generating overlay: {e}")
    
    def run(self) -> None:
        """Main loop of the overlay runner."""
        if not MOUNT_AVAILABLE:
            self.logger.error("ASCOM mount not available. Exiting.")
            return
            
        try:
            # Observation session is already started in __init__
            self.running = True
            
            with ASCOMMount(config=self.config, logger=self.logger) as self.mount:
                self.logger.info("Overlay Runner started")
                self.logger.info(f"Update interval: {self.update_interval} seconds")
                
                # Use existing video processor from initialization
                if self.video_processor:
                    try:
                        # Try to initialize cooling manager one more time if not already done
                        if self.enable_cooling and not self.cooling_manager:
                            self._initialize_cooling_manager()
                        
                        # Set up callbacks
                        def on_solve_result(result):
                            self.last_solve_result = result
                            self.logger.info(f"Plate-solving successful: RA={result.ra_center:.4f}°, Dec={result.dec_center:.4f}°")
                        
                        def on_error(error):
                            # Don't log every plate-solving failure as an error
                            # Only log actual system errors
                            if "plate-solving" not in str(error).lower() and "no stars" not in str(error).lower():
                                self.logger.error(f"Video processing error: {error}")
                            else:
                                self.logger.debug(f"Plate-solving attempt failed (normal for poor conditions): {error}")
                        
                        self.video_processor.set_callbacks(
                            on_solve_result=on_solve_result,
                            on_error=on_error
                        )
                        
                        start_status = self.video_processor.start()
                        if start_status.is_success:
                            self.logger.info("Video processor started")
                        else:
                            self.logger.error(f"Failed to start video processor: {start_status.message}")
                            self.video_processor = None
                    except Exception as e:
                        self.logger.error(f"Error starting video processor: {e}")
                        self.video_processor = None
                else:
                    self.logger.info("Frame processing disabled or not available")
                
                consecutive_failures = 0
                
                while self.running:
                    try:
                        # Check for KeyboardInterrupt and re-raise it
                        if not self.running:
                            break
                        # Check if we need to wait for warmup
                        if self.cooling_manager and self.cooling_manager.is_warming_up:
                            self.logger.info("🔥 Warmup in progress, pausing main loop...")
                            while self.cooling_manager.is_warming_up and self.running:
                                time.sleep(5)  # Check every 5 seconds
                            if self.cooling_manager.is_warming_up:
                                self.logger.info("🔥 Warmup completed, resuming main loop")
                        
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
                            
                            # Get flip information from plate-solving result
                            is_flipped = getattr(self.last_solve_result, 'is_flipped', False)
                            if is_flipped:
                                self.logger.info("Plate-solving detected flipped image, will apply flip correction to overlay")
                            
                            self.logger.info(f"Using plate-solving results: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°, FOV={fov_width_deg:.3f}°x{fov_height_deg:.3f}°, PA={position_angle_deg:.1f}°, Flipped={is_flipped}")
                        else:
                            # Use mount coordinates and default values
                            fov_width_deg = None
                            fov_height_deg = None
                            position_angle_deg = None
                            image_size = None
                            is_flipped = False
                            
                            # Try to get actual image size from captured frame
                            if self.video_processor:
                                try:
                                    latest_frame = self.video_processor.get_latest_frame_path()
                                    if latest_frame and os.path.exists(latest_frame):
                                        # Get actual image dimensions from the captured frame
                                        from PIL import Image
                                        with Image.open(latest_frame) as img:
                                            image_size = img.size
                                            self.logger.debug(f"Detected image size from captured frame: {image_size}")
                                except Exception as e:
                                    self.logger.warning(f"Could not get image size from captured frame: {e}")
                                    # Fallback to config if frame detection fails
                                    try:
                                        overlay_config = self.config.get_overlay_config()
                                        image_size = overlay_config.get('image_size', [1920, 1080])
                                        if isinstance(image_size, list) and len(image_size) == 2:
                                            image_size = tuple(image_size)
                                        else:
                                            image_size = (1920, 1080)  # Default fallback
                                        self.logger.debug(f"Using fallback image size from overlay config: {image_size}")
                                    except Exception as e:
                                        self.logger.warning(f"Could not get image size from overlay config: {e}")
                                        image_size = (1920, 1080)  # Final fallback
                        
                        # Generate output filename
                        if self.use_timestamps:
                            timestamp = datetime.now().strftime(self.timestamp_format)
                            output_file = f"overlay_{timestamp}.png"
                        else:
                            output_file = "overlay.png"
                        
                        # Create overlay with all available parameters
                        overlay_status = self.generate_overlay_with_coords(
                            ra_deg, dec_deg, output_file,
                            fov_width_deg, fov_height_deg, position_angle_deg, image_size, None, is_flipped
                        )
                        
                        if overlay_status.is_success:
                            # Get the overlay file path
                            overlay_file = overlay_status.data
                            
                            # Combine overlay with captured image if video processor is available
                            if self.video_processor and hasattr(self.video_processor, 'combine_overlay_with_image'):
                                try:
                                    # Get the latest captured frame
                                    latest_frame = self.video_processor.get_latest_frame_path()
                                    if latest_frame and os.path.exists(latest_frame):
                                        # Generate combined image filename
                                        if self.use_timestamps:
                                            timestamp = datetime.now().strftime(self.timestamp_format)
                                            combined_file = f"combined_{timestamp}.png"
                                        else:
                                            combined_file = "combined.png"
                                        
                                        # Combine overlay with captured image
                                        combine_status = self.video_processor.combine_overlay_with_image(
                                            latest_frame, overlay_file, combined_file
                                        )
                                        
                                        if combine_status.is_success:
                                            self.logger.info(f"Combined image created: {combined_file}")
                                        else:
                                            self.logger.warning(f"Failed to combine images: {combine_status.message}")
                                    else:
                                        self.logger.info("No captured frame available for combination")
                                except Exception as e:
                                    self.logger.warning(f"Error combining overlay with image: {e}")
                            
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
            # ASCOMMount is a context manager, so it will be cleaned up automatically
            if self.video_processor:
                self.video_processor.stop()
            self.logger.info("Overlay Runner stopped.")