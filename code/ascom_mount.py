# ascom_mount.py
import time
import sys
import platform

# Import configuration
from config_manager import config

# Platform-specific imports
if platform.system() == "Windows":
    try:
        import win32com.client
        WINDOWS_AVAILABLE = True
    except ImportError:
        print("Warning: win32com not available. Install with: pip install pywin32")
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False
    print("Warning: ASCOM is only available on Windows.")

class ASCOMMount:
    def __init__(self, prog_id=None):
        if not WINDOWS_AVAILABLE:
            raise RuntimeError("ASCOM mount is only available on Windows")
        
        # Use config or fallback to default
        if prog_id is None:
            prog_id = config.get('mount.driver_id', 'ASCOM.tenmicron_mount.Telescope')
        
        mount_config = config.get_mount_config()
        connection_timeout = mount_config.get('connection_timeout', 10)
        validate_coords = mount_config.get('validate_coordinates', True)
        
        self.validate_coordinates = validate_coords
        
        try:
            self.telescope = win32com.client.Dispatch(prog_id)
            if not self.telescope.Connected:
                print("Connecting to 10Micron mount...")
                self.telescope.Connected = True
                time.sleep(1)  # Brief pause for connection establishment
                
            if not self.telescope.Connected:
                raise ConnectionError("Failed to connect to mount")
                
        except Exception as e:
            raise ConnectionError(f"Error connecting to mount: {e}")

    def get_coordinates(self):
        """Returns current mount coordinates (RA, Dec) in degrees."""
        try:
            if not self.telescope.Connected:
                raise ConnectionError("Mount not connected")
                
            ra_hours = self.telescope.RightAscension  # in hours
            dec_deg = self.telescope.Declination      # in degrees
            
            # Validate values if enabled
            if self.validate_coordinates:
                if not (0 <= ra_hours <= 24):
                    raise ValueError(f"Invalid RA value: {ra_hours}")
                if not (-90 <= dec_deg <= 90):
                    raise ValueError(f"Invalid Dec value: {dec_deg}")
                
            ra_deg = ra_hours * 15  # hours -> degrees
            return ra_deg, dec_deg
            
        except Exception as e:
            raise RuntimeError(f"Error reading coordinates: {e}")

    def disconnect(self):
        """Disconnects from the mount."""
        try:
            if hasattr(self, 'telescope') and self.telescope.Connected:
                self.telescope.Connected = False
                print("Disconnected from mount.")
        except Exception as e:
            print(f"Warning: Error disconnecting: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

if __name__ == "__main__":
    try:
        with ASCOMMount() as mount:
            while True:
                ra, dec = mount.get_coordinates()
                print(f"RA: {ra:.4f}°, Dec: {dec:.4f}°")
                time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
