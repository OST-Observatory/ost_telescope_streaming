# ascom_mount.py
import time
import sys
import platform
import logging

# Import exceptions and status
from exceptions import MountError, ConnectionError, ValidationError
from status import MountStatus, success_status, error_status, warning_status

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
    def __init__(self, prog_id: str = None, config=None, logger=None) -> None:
        """Initialisiert die ASCOM-Mount-Verbindung.
        Args:
            prog_id: Optionaler ASCOM-ProgID-String.
        Raises:
            MountError: Wenn ASCOM nicht verfügbar ist.
            ConnectionError: Wenn die Verbindung fehlschlägt.
        """
        from config_manager import ConfigManager
        # Only create default config if no config is provided
        # This prevents loading config.yaml when config is passed from tests
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None
        import logging
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or default_config
        if not WINDOWS_AVAILABLE:
            raise MountError("ASCOM mount is only available on Windows")
        
        # Use config or fallback to default
        if prog_id is None:
            prog_id = self.config.get('mount.driver_id', 'ASCOM.tenmicron_mount.Telescope')
        
        mount_config = self.config.get_mount_config()
        connection_timeout = mount_config.get('connection_timeout', 10)
        validate_coords = mount_config.get('validate_coordinates', True)
        
        self.validate_coordinates = validate_coords
        
        try:
            self.telescope = win32com.client.Dispatch(prog_id)
            if not self.telescope.Connected:
                self.logger.info("Connecting to 10Micron mount...")
                self.telescope.Connected = True
                time.sleep(1)  # Brief pause for connection establishment
                
            if not self.telescope.Connected:
                raise ConnectionError("Failed to connect to mount")
                
        except Exception as e:
            raise ConnectionError(f"Error connecting to mount: {e}")

    def get_coordinates(self) -> MountStatus:
        """Gibt aktuelle Mount-Koordinaten (RA, Dec) in Grad zurück.
        Returns:
            MountStatus: Status-Objekt mit Koordinaten oder Fehlerinformationen.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={'is_connected': False})
                
            ra_hours = self.telescope.RightAscension  # in hours
            dec_deg = self.telescope.Declination      # in degrees
            
            # Validate values if enabled
            if self.validate_coordinates:
                if not (0 <= ra_hours <= 24):
                    raise ValidationError(f"Invalid RA value: {ra_hours}")
                if not (-90 <= dec_deg <= 90):
                    raise ValidationError(f"Invalid Dec value: {dec_deg}")
                
            ra_deg = ra_hours * 15  # hours -> degrees
            coordinates = (ra_deg, dec_deg)
            
            return success_status(
                f"Coordinates retrieved: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°",
                data=coordinates,
                details={'is_connected': True, 'ra_hours': ra_hours, 'dec_deg': dec_deg}
            )
            
        except ValidationError as e:
            return error_status(f"Coordinate validation failed: {e}", details={'is_connected': True})
        except Exception as e:
            return error_status(f"Error reading coordinates: {e}", details={'is_connected': False})

    def disconnect(self) -> MountStatus:
        """Trennt die Verbindung zur Montierung.
        Returns:
            MountStatus: Status-Objekt mit Verbindungsinformationen.
        """
        try:
            if hasattr(self, 'telescope') and self.telescope.Connected:
                self.telescope.Connected = False
                self.logger.info("Disconnected from mount.")
                return success_status("Successfully disconnected from mount", details={'is_connected': False})
            else:
                return warning_status("Mount was not connected", details={'is_connected': False})
        except Exception as e:
            self.logger.warning(f"Error disconnecting: {e}")
            return error_status(f"Error disconnecting: {e}", details={'is_connected': True})

    def is_slewing(self) -> MountStatus:
        """Prüft, ob die Montierung gerade eine Slewing-Bewegung ausführt.
        Returns:
            MountStatus: Status-Objekt mit Slewing-Information.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={'is_connected': False, 'is_slewing': False})
            
            # Check if mount is slewing
            is_slewing = self.telescope.Slewing
            
            return success_status(
                f"Mount slewing status: {'Slewing' if is_slewing else 'Not slewing'}",
                data=is_slewing,
                details={'is_connected': True, 'is_slewing': is_slewing}
            )
            
        except Exception as e:
            self.logger.error(f"Error checking slewing status: {e}")
            return error_status(f"Error checking slewing status: {e}", details={'is_connected': True, 'is_slewing': None})

    def wait_for_slewing_complete(self, timeout: float = 300.0, check_interval: float = 1.0) -> MountStatus:
        """Wartet, bis die Slewing-Bewegung abgeschlossen ist.
        Args:
            timeout: Maximale Wartezeit in Sekunden (Standard: 5 Minuten)
            check_interval: Intervall zwischen den Prüfungen in Sekunden (Standard: 1 Sekunde)
        Returns:
            MountStatus: Status-Objekt mit Ergebnis.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={'is_connected': False})
            
            start_time = time.time()
            self.logger.info(f"Waiting for slewing to complete (timeout: {timeout}s)...")
            
            while time.time() - start_time < timeout:
                slewing_status = self.is_slewing()
                
                if not slewing_status.is_success:
                    return slewing_status
                
                if not slewing_status.data:  # Not slewing
                    elapsed_time = time.time() - start_time
                    self.logger.info(f"Slewing completed after {elapsed_time:.1f} seconds")
                    return success_status(
                        "Slewing completed",
                        data=True,
                        details={'is_connected': True, 'is_slewing': False, 'wait_time': elapsed_time}
                    )
                
                # Still slewing, wait and check again
                time.sleep(check_interval)
            
            # Timeout reached
            elapsed_time = time.time() - start_time
            self.logger.warning(f"Slewing timeout after {elapsed_time:.1f} seconds")
            return warning_status(
                f"Slewing timeout after {elapsed_time:.1f} seconds",
                data=False,
                details={'is_connected': True, 'is_slewing': True, 'wait_time': elapsed_time, 'timeout': True}
            )
            
        except Exception as e:
            self.logger.error(f"Error waiting for slewing completion: {e}")
            return error_status(f"Error waiting for slewing completion: {e}", details={'is_connected': True})

    def get_mount_status(self) -> MountStatus:
        """Gibt den vollständigen Status der Montierung zurück.
        Returns:
            MountStatus: Status-Objekt mit allen Mount-Informationen.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={'is_connected': False})
            
            # Get coordinates
            coord_status = self.get_coordinates()
            if not coord_status.is_success:
                return coord_status
            
            # Get slewing status
            slewing_status = self.is_slewing()
            if not slewing_status.is_success:
                return slewing_status
            
            # Get additional mount properties if available
            mount_info = {
                'is_connected': True,
                'is_slewing': slewing_status.data,
                'coordinates': coord_status.data,
                'ra_deg': coord_status.data[0],
                'dec_deg': coord_status.data[1]
            }
            
            # Try to get additional properties
            try:
                if hasattr(self.telescope, 'AtPark'):
                    mount_info['at_park'] = self.telescope.AtPark
                if hasattr(self.telescope, 'Tracking'):
                    mount_info['tracking'] = self.telescope.Tracking
                if hasattr(self.telescope, 'SideOfPier'):
                    mount_info['side_of_pier'] = self.telescope.SideOfPier
            except Exception as e:
                self.logger.debug(f"Could not get additional mount properties: {e}")
            
            return success_status(
                f"Mount status: RA={mount_info['ra_deg']:.4f}°, Dec={mount_info['dec_deg']:.4f}°, Slewing={'Yes' if mount_info['is_slewing'] else 'No'}",
                data=mount_info,
                details=mount_info
            )
            
        except Exception as e:
            self.logger.error(f"Error getting mount status: {e}")
            return error_status(f"Error getting mount status: {e}", details={'is_connected': False})

    def __enter__(self) -> 'ASCOMMount':
        """Context-Manager-Einstieg."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context-Manager-Ausstieg."""
        self.disconnect()
