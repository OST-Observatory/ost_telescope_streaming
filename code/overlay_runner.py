# overlay_runner.py
import time
import subprocess
import sys
import signal
import os
from datetime import datetime

# Import configuration
from config_manager import config

# Import with error handling
try:
    from ascom_mount import ASCOMMount
    MOUNT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ASCOM mount not available: {e}")
    MOUNT_AVAILABLE = False

class OverlayRunner:
    def __init__(self):
        self.running = True
        self.mount = None
        self.setup_signal_handlers()
        
        # Load configuration
        streaming_config = config.get_streaming_config()
        logging_config = config.get_logging_config()
        
        self.update_interval = streaming_config.get('update_interval', 30)
        self.max_retries = streaming_config.get('max_retries', 3)
        self.retry_delay = streaming_config.get('retry_delay', 5)
        self.use_timestamps = streaming_config.get('use_timestamps', True)
        self.timestamp_format = streaming_config.get('timestamp_format', '%Y%m%d_%H%M%S')
        self.show_emojis = logging_config.get('show_emojis', True)
        
    def setup_signal_handlers(self):
        """Sets up signal handlers for clean shutdown."""
        def signal_handler(signum, frame):
            if self.show_emojis:
                print(f"\n🛑 Signal {signum} received. Shutting down...")
            else:
                print(f"\nSignal {signum} received. Shutting down...")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def generate_overlay_with_coords(self, ra_deg, dec_deg, output_file=None):
        """Generates an overlay for the given coordinates."""
        if self.show_emojis:
            print(f"🖼️  Generating overlay for RA: {ra_deg:.4f}°, Dec: {dec_deg:.4f}° ...")
        else:
            print(f"Generating overlay for RA: {ra_deg:.4f}°, Dec: {dec_deg:.4f}° ...")
        
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
                if self.show_emojis:
                    print("✅ Overlay created successfully")
                else:
                    print("Overlay created successfully")
                if result.stdout:
                    print(result.stdout.strip())
            else:
                if self.show_emojis:
                    print(f"❌ Error creating overlay:")
                else:
                    print(f"Error creating overlay:")
                print(result.stderr.strip())
                return False
                
        except subprocess.TimeoutExpired:
            if self.show_emojis:
                print("⏰ Timeout while creating overlay")
            else:
                print("Timeout while creating overlay")
            return False
        except Exception as e:
            if self.show_emojis:
                print(f"❌ Unexpected error: {e}")
            else:
                print(f"Unexpected error: {e}")
            return False
            
        return True
    
    def run(self):
        """Main loop of the overlay runner."""
        if not MOUNT_AVAILABLE:
            if self.show_emojis:
                print("❌ ASCOM mount not available. Exiting.")
            else:
                print("ASCOM mount not available. Exiting.")
            return
            
        try:
            self.mount = ASCOMMount()
            if self.show_emojis:
                print("🚀 Overlay Runner started")
                print(f"⏱️  Update interval: {self.update_interval} seconds")
            else:
                print("Overlay Runner started")
                print(f"Update interval: {self.update_interval} seconds")
            
            consecutive_failures = 0
            
            while self.running:
                try:
                    # Read coordinates
                    ra_deg, dec_deg = self.mount.get_coordinates()
                    
                    # Generate output filename
                    if self.use_timestamps:
                        timestamp = datetime.now().strftime(self.timestamp_format)
                        output_file = f"overlay_{timestamp}.png"
                    else:
                        output_file = None
                    
                    # Create overlay
                    success = self.generate_overlay_with_coords(ra_deg, dec_deg, output_file)
                    
                    if success:
                        consecutive_failures = 0
                        if self.show_emojis:
                            print(f"📊 Status: OK | Coordinates: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°")
                        else:
                            print(f"Status: OK | Coordinates: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°")
                    else:
                        consecutive_failures += 1
                        if self.show_emojis:
                            print(f"⚠️  Error #{consecutive_failures}")
                        else:
                            print(f"Error #{consecutive_failures}")
                        
                        if consecutive_failures >= self.max_retries:
                            if self.show_emojis:
                                print(f"❌ Too many consecutive errors ({consecutive_failures}). Exiting.")
                            else:
                                print(f"Too many consecutive errors ({consecutive_failures}). Exiting.")
                            break
                    
                    # Wait until next update
                    if self.running:
                        if self.show_emojis:
                            print(f"⏳ Waiting {self.update_interval} seconds...")
                        else:
                            print(f"Waiting {self.update_interval} seconds...")
                        time.sleep(self.update_interval)
                        
                except KeyboardInterrupt:
                    if self.show_emojis:
                        print("\n⛔ Stopped by user.")
                    else:
                        print("\nStopped by user.")
                    break
                except Exception as e:
                    consecutive_failures += 1
                    if self.show_emojis:
                        print(f"❌ Error in main loop: {e}")
                    else:
                        print(f"Error in main loop: {e}")
                    
                    if consecutive_failures >= self.max_retries:
                        if self.show_emojis:
                            print(f"❌ Too many consecutive errors ({consecutive_failures}). Exiting.")
                        else:
                            print(f"Too many consecutive errors ({consecutive_failures}). Exiting.")
                        break
                    
                    if self.show_emojis:
                        print(f"⏳ Waiting {self.retry_delay} seconds before retry...")
                    else:
                        print(f"Waiting {self.retry_delay} seconds before retry...")
                    time.sleep(self.retry_delay)
                    
        except Exception as e:
            if self.show_emojis:
                print(f"❌ Critical error: {e}")
            else:
                print(f"Critical error: {e}")
        finally:
            if self.mount:
                self.mount.disconnect()
            if self.show_emojis:
                print("👋 Overlay Runner stopped.")
            else:
                print("Overlay Runner stopped.")

def main():
    """Main function."""
    if config.get('logging.show_emojis', True):
        print("🔭 OST Telescope Streaming - Overlay Runner")
        print("=" * 50)
    else:
        print("OST Telescope Streaming - Overlay Runner")
        print("=" * 50)
    
    runner = OverlayRunner()
    runner.run()

if __name__ == "__main__":
    main()