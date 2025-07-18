#!/usr/bin/env python3
"""
Video processor module for telescope streaming system.
Coordinates video capture and plate-solving operations.
"""

import time
import threading
import logging
from typing import Optional, Callable, Dict, Any
from pathlib import Path
from datetime import datetime

# Import local modules
from video_capture import VideoCapture
from plate_solver import PlateSolverFactory, PlateSolveResult
from config_manager import config

class VideoProcessor:
    """Coordinates video capture and plate-solving operations."""
    
    def __init__(self):
        """Initialize video processor."""
        self.video_capture = None
        self.plate_solver = None
        self.is_running = False
        self.processing_thread = None
        
        # Load configuration
        self.video_config = config.get_video_config()
        self.plate_solve_config = config.get_plate_solve_config()
        
        # Video capture settings
        self.video_enabled = self.video_config.get('plate_solving_enabled', False)
        self.capture_interval = self.video_config.get('plate_solving_interval', 60)
        self.save_frames = self.video_config.get('save_plate_solve_frames', True)
        self.frame_dir = Path(self.video_config.get('plate_solve_dir', 'plate_solve_frames'))
        
        # Plate-solving settings
        self.solver_type = self.plate_solve_config.get('default_solver', 'platesolve2')
        self.auto_solve = self.plate_solve_config.get('auto_solve', True)
        self.min_solve_interval = self.plate_solve_config.get('min_solve_interval', 30)
        
        # State tracking
        self.last_capture_time = 0
        self.last_solve_time = 0
        self.last_solve_result = None
        self.capture_count = 0
        self.solve_count = 0
        self.successful_solves = 0
        
        # Callbacks
        self.on_solve_result = None
        self.on_capture_frame = None
        self.on_error = None
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Ensure frame directory exists
        if self.save_frames:
            self.frame_dir.mkdir(exist_ok=True)
    
    def initialize(self) -> bool:
        """Initialize video capture and plate solver."""
        success = True
        
        # Initialize video capture
        if self.video_enabled:
            try:
                self.video_capture = VideoCapture()
                if self.video_capture.connect():
                    self.logger.info("Video capture initialized")
                else:
                    self.logger.error("Failed to connect to video camera")
                    success = False
            except Exception as e:
                self.logger.error(f"Error initializing video capture: {e}")
                success = False
        
        # Initialize plate solver
        if self.auto_solve:
            try:
                self.plate_solver = PlateSolverFactory.create_solver(self.solver_type)
                if self.plate_solver and self.plate_solver.is_available():
                    self.logger.info(f"Plate solver initialized: {self.plate_solver.get_name()}")
                else:
                    self.logger.warning(f"Plate solver not available: {self.solver_type}")
                    self.plate_solver = None
            except Exception as e:
                self.logger.error(f"Error initializing plate solver: {e}")
                self.plate_solver = None
        
        return success
    
    def start(self) -> bool:
        """Start video processing."""
        if not self.initialize():
            return False
        
        if not self.video_capture:
            self.logger.error("Video capture not available")
            return False
        
        if not self.video_capture.start_capture():
            self.logger.error("Failed to start video capture")
            return False
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("Video processor started")
        return True
    
    def stop(self):
        """Stop video processing."""
        self.is_running = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        
        if self.video_capture:
            self.video_capture.stop_capture()
            self.video_capture.disconnect()
        
        self.logger.info("Video processor stopped")
    
    def _processing_loop(self):
        """Main processing loop."""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Check if it's time for a new capture/solve cycle
                if current_time - self.last_capture_time >= self.capture_interval:
                    self._capture_and_solve()
                    self.last_capture_time = current_time
                
                # Sleep briefly to avoid busy waiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                if self.on_error:
                    self.on_error(e)
                time.sleep(5)  # Wait before retrying
    
    def _capture_and_solve(self):
        """Capture a frame and optionally solve it."""
        if not self.video_capture:
            return
        
        try:
            # Capture frame
            frame = self.video_capture.get_current_frame()
            if frame is None:
                self.logger.warning("No frame available for capture")
                return
            
            self.capture_count += 1
            
            # Save frame if enabled
            frame_filename = None
            if self.save_frames:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                frame_filename = self.frame_dir / f"capture_{timestamp}_{self.capture_count:04d}.jpg"
                
                if self.video_capture.save_frame(frame, str(frame_filename)):
                    self.logger.debug(f"Frame saved: {frame_filename}")
                else:
                    self.logger.warning("Failed to save frame")
                    frame_filename = None
            
            # Trigger capture callback
            if self.on_capture_frame:
                self.on_capture_frame(frame, frame_filename)
            
            # Plate-solve if enabled and enough time has passed
            if (self.plate_solver and self.auto_solve and 
                time.time() - self.last_solve_time >= self.min_solve_interval):
                
                if frame_filename and frame_filename.exists():
                    self._solve_frame(str(frame_filename))
                else:
                    self.logger.warning("No frame file available for plate-solving")
            
        except Exception as e:
            self.logger.error(f"Error in capture and solve: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _solve_frame(self, frame_path: str) -> Optional[PlateSolveResult]:
        """Solve a specific frame."""
        if not self.plate_solver:
            return None
        
        try:
            self.logger.info(f"Plate-solving frame: {frame_path}")
            
            result = self.plate_solver.solve(frame_path)
            self.solve_count += 1
            
            if result.success:
                self.successful_solves += 1
                self.last_solve_result = result
                self.logger.info(f"Plate-solving successful: {result}")
                
                # Trigger solve callback
                if self.on_solve_result:
                    self.on_solve_result(result)
            else:
                self.logger.warning(f"Plate-solving failed: {result.error_message}")
            
            self.last_solve_time = time.time()
            return result
            
        except Exception as e:
            self.logger.error(f"Error in plate-solving: {e}")
            if self.on_error:
                self.on_error(e)
            return None
    
    def solve_frame(self, frame_path: str) -> Optional[PlateSolveResult]:
        """Manually solve a specific frame."""
        if not self.plate_solver:
            self.logger.error("No plate solver available")
            return None
        
        return self._solve_frame(frame_path)
    
    def get_current_frame(self):
        """Get the most recent captured frame."""
        if self.video_capture:
            return self.video_capture.get_current_frame()
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            'captures': self.capture_count,
            'solves': self.solve_count,
            'successful_solves': self.successful_solves,
            'success_rate': (self.successful_solves / self.solve_count * 100) if self.solve_count > 0 else 0,
            'last_solve_result': self.last_solve_result,
            'video_enabled': self.video_enabled,
            'solver_available': self.plate_solver is not None and self.plate_solver.is_available(),
            'is_running': self.is_running
        }
    
    def set_callbacks(self, 
                     on_solve_result: Optional[Callable[[PlateSolveResult], None]] = None,
                     on_capture_frame: Optional[Callable] = None,
                     on_error: Optional[Callable[[Exception], None]] = None):
        """Set callback functions."""
        self.on_solve_result = on_solve_result
        self.on_capture_frame = on_capture_frame
        self.on_error = on_error

def main():
    """Test function for video processor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test video processor")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--interval", type=int, default=10, help="Capture interval in seconds")
    parser.add_argument("--solve", action="store_true", help="Enable plate-solving")
    
    args = parser.parse_args()
    
    def on_solve_result(result):
        print(f"Plate-solving result: {result}")
    
    def on_capture_frame(frame, filename):
        print(f"Frame captured: {filename}")
    
    def on_error(error):
        print(f"Error: {error}")
    
    # Update config for testing
    config.update_video_config({
        'plate_solving_interval': args.interval,
        'plate_solving_enabled': True
    })
    
    if args.solve:
        config.update_plate_solve_config({
            'auto_solve': True,
            'min_solve_interval': 5
        })
    
    processor = VideoProcessor()
    processor.set_callbacks(on_solve_result, on_capture_frame, on_error)
    
    print(f"Starting video processor test for {args.duration} seconds...")
    
    if processor.start():
        try:
            time.sleep(args.duration)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            processor.stop()
            
            stats = processor.get_statistics()
            print(f"\nStatistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
    else:
        print("Failed to start video processor")

if __name__ == "__main__":
    main() 