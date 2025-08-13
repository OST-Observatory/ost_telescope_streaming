# ascom_mount.py
"""
ASCOM Mount Interface Module

This module provides a high-level interface for controlling ASCOM-compatible telescope mounts.
It handles connection management, coordinate retrieval, slewing detection, and status monitoring.

Key Features:
- Automatic connection management with configurable timeouts
- Coordinate validation and conversion (hours to degrees)
- Slewing detection to prevent captures during mount movement
- Comprehensive mount status monitoring
- Context manager support for automatic cleanup

Dependencies:
- Windows platform (ASCOM is Windows-only)
- pywin32 library for COM object access
- ASCOM drivers installed on the system
"""

import logging
import platform
import time
from typing import Optional

# Import exceptions and status
from exceptions import ConnectionError, MountError, ValidationError
from status import MountStatus, error_status, success_status, warning_status

# Platform-specific imports
# ASCOM is only available on Windows, so we need to handle this gracefully
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
    """
    ASCOM Mount Interface Class

    Provides a high-level interface for controlling ASCOM-compatible telescope mounts.
    Handles connection management, coordinate retrieval, slewing detection, and status monitoring.

    This class uses lazy loading for configuration to prevent automatic loading of config.yaml
    when the class is instantiated from test scripts with a specific configuration.
    """

    def __init__(self, prog_id: Optional[str] = None, config=None, logger=None) -> None:
        """Initialize the ASCOM mount connection.

        Args:
            prog_id: Optional ASCOM ProgID string. If None, uses config or default.
            config: Optional ConfigManager instance. If None, creates default config.
            logger: Optional logger instance. If None, creates module logger.

        Raises:
            MountError: If ASCOM is not available on this platform.
            ConnectionError: If connection to the mount fails.

        Note:
            Uses lazy loading for configuration to prevent double loading when
            config is passed from test scripts. This ensures only one config file
            is loaded even when --config option is used.
        """
        from config_manager import ConfigManager

        # Only create default config if no config is provided
        # This prevents loading config.yaml when config is passed from tests
        if config is None:
            default_config = ConfigManager()
        else:
            default_config = None

        self.logger = logger or logging.getLogger(__name__)
        self.config = config or default_config

        if not WINDOWS_AVAILABLE:
            raise MountError("ASCOM mount is only available on Windows")

        # Use config or fallback to default
        if prog_id is None:
            prog_id = self.config.get("mount.driver_id", "ASCOM.tenmicron_mount.Telescope")

        mount_config = self.config.get_mount_config()
        validate_coords = mount_config.get("validate_coordinates", True)

        self.validate_coordinates = validate_coords

        try:
            # Create COM object for the ASCOM driver
            self.telescope = win32com.client.Dispatch(prog_id)

            # Connect if not already connected
            if not self.telescope.Connected:
                self.logger.info("Connecting to 10Micron mount...")
                self.telescope.Connected = True
                time.sleep(1)  # Brief pause for connection establishment

            if not self.telescope.Connected:
                raise ConnectionError("Failed to connect to mount")

        except Exception as e:
            raise ConnectionError(f"Error connecting to mount: {e}") from e

    def get_coordinates(self) -> MountStatus:
        """Get current mount coordinates (RA, Dec) in degrees.

        Retrieves the current Right Ascension and Declination from the mount
        and converts RA from hours to degrees for consistency.

        Returns:
            MountStatus: Status object with coordinates or error information.

        Note:
            RA is returned in degrees (0-360) for consistency with other systems,
            even though ASCOM provides it in hours (0-24). This conversion makes
            it easier to work with coordinate calculations and comparisons.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={"is_connected": False})

            ra_hours = self.telescope.RightAscension  # ASCOM provides RA in hours
            dec_deg = self.telescope.Declination  # ASCOM provides Dec in degrees

            # Validate values if enabled
            # This prevents invalid coordinates from causing downstream issues
            if self.validate_coordinates:
                if not (0 <= ra_hours <= 24):
                    raise ValidationError(f"Invalid RA value: {ra_hours}")
                if not (-90 <= dec_deg <= 90):
                    raise ValidationError(f"Invalid Dec value: {dec_deg}")

            # Convert RA from hours to degrees for consistency
            # Most astronomical calculations use degrees, so this conversion
            # makes the coordinates more useful for plate-solving and other operations
            ra_deg = ra_hours * 15  # hours -> degrees (24 hours = 360 degrees)
            coordinates = (ra_deg, dec_deg)

            return success_status(
                f"Coordinates retrieved: RA={ra_deg:.4f}°, Dec={dec_deg:.4f}°",
                data=coordinates,
                details={"is_connected": True, "ra_hours": ra_hours, "dec_deg": dec_deg},
            )

        except ValidationError as e:
            return error_status(
                f"Coordinate validation failed: {e}", details={"is_connected": True}
            )
        except Exception as e:
            return error_status(f"Error reading coordinates: {e}", details={"is_connected": False})

    def disconnect(self) -> MountStatus:
        """Disconnect from the mount.

        Safely disconnects from the ASCOM mount driver and cleans up resources.

        Returns:
            MountStatus: Status object with connection information.
        """
        try:
            if hasattr(self, "telescope") and self.telescope.Connected:
                self.telescope.Connected = False
                self.logger.info("Disconnected from mount.")
                return success_status(
                    "Successfully disconnected from mount", details={"is_connected": False}
                )
            else:
                return warning_status("Mount was not connected", details={"is_connected": False})
        except Exception as e:
            self.logger.warning(f"Error disconnecting: {e}")
            return error_status(f"Error disconnecting: {e}", details={"is_connected": True})

    def is_slewing(self) -> MountStatus:
        """Check if the mount is currently slewing.

        This method is critical for preventing image captures during mount movement.
        It queries the ASCOM Slewing property to determine if the mount is in motion.

        Returns:
            MountStatus: Status object with slewing information.

        Note:
            This method is called before each image capture to ensure only
            stationary images are captured. This prevents blurred images and
            improves plate-solving success rates.
        """
        try:
            if not self.telescope.Connected:
                return error_status(
                    "Mount not connected", details={"is_connected": False, "is_slewing": False}
                )

            # Check if mount is slewing using ASCOM property
            # This is the most reliable way to detect mount movement
            is_slewing = self.telescope.Slewing

            return success_status(
                f"Mount slewing status: {'Slewing' if is_slewing else 'Not slewing'}",
                data=is_slewing,
                details={"is_connected": True, "is_slewing": is_slewing},
            )

        except Exception as e:
            self.logger.error(f"Error checking slewing status: {e}")
            return error_status(
                f"Error checking slewing status: {e}",
                details={"is_connected": True, "is_slewing": None},
            )

    def wait_for_slewing_complete(
        self, timeout: float = 300.0, check_interval: float = 1.0
    ) -> MountStatus:
        """Wait for slewing to complete.

        This method provides an alternative to skipping captures during slewing.
        Instead of skipping, it waits for the slewing to finish and then allows
        the capture to proceed. This is useful for critical imaging sequences
        where every possible frame is needed.

        Args:
            timeout: Maximum wait time in seconds (default: 5 minutes)
            check_interval: Interval between checks in seconds (default: 1 second)

        Returns:
            MountStatus: Status object with result.

        Note:
            This method uses polling rather than events because ASCOM doesn't
            provide reliable event-based slewing completion notifications.
            The polling interval can be adjusted for performance vs. responsiveness.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={"is_connected": False})

            start_time = time.time()
            self.logger.info(f"Waiting for slewing to complete (timeout: {timeout}s)...")

            # Poll for slewing completion
            # We use polling instead of events because ASCOM event handling
            # can be unreliable across different mount drivers
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
                        details={
                            "is_connected": True,
                            "is_slewing": False,
                            "wait_time": elapsed_time,
                        },
                    )

                # Still slewing, wait and check again
                # The check_interval balances responsiveness with system load
                time.sleep(check_interval)

            # Timeout reached
            # This prevents infinite waiting if the mount gets stuck
            elapsed_time = time.time() - start_time
            self.logger.warning(f"Slewing timeout after {elapsed_time:.1f} seconds")
            return warning_status(
                f"Slewing timeout after {elapsed_time:.1f} seconds",
                data=False,
                details={
                    "is_connected": True,
                    "is_slewing": True,
                    "wait_time": elapsed_time,
                    "timeout": True,
                },
            )

        except Exception as e:
            self.logger.error(f"Error waiting for slewing completion: {e}")
            return error_status(
                f"Error waiting for slewing completion: {e}", details={"is_connected": True}
            )

    def get_mount_status(self) -> MountStatus:
        """Get complete mount status including slewing information.

        This method provides a comprehensive view of the mount's current state,
        including coordinates, slewing status, and additional properties if available.
        It's useful for monitoring and debugging mount behavior.

        Returns:
            MountStatus: Status object with all mount information.

        Note:
            Additional properties (AtPark, Tracking, SideOfPier) are only included
            if they're available on the specific mount driver. This ensures
            compatibility across different ASCOM drivers.
        """
        try:
            if not self.telescope.Connected:
                return error_status("Mount not connected", details={"is_connected": False})

            # Get coordinates
            coord_status = self.get_coordinates()
            if not coord_status.is_success:
                return coord_status

            # Get slewing status
            slewing_status = self.is_slewing()
            if not slewing_status.is_success:
                return slewing_status

            # Build comprehensive mount information
            # This provides a single source of truth for mount state
            mount_info = {
                "is_connected": True,
                "is_slewing": slewing_status.data,
                "coordinates": coord_status.data,
                "ra_deg": coord_status.data[0],
                "dec_deg": coord_status.data[1],
            }

            # Try to get additional properties if available
            # These properties are optional and may not be supported by all drivers
            try:
                if hasattr(self.telescope, "AtPark"):
                    mount_info["at_park"] = self.telescope.AtPark
                if hasattr(self.telescope, "Tracking"):
                    mount_info["tracking"] = self.telescope.Tracking
                if hasattr(self.telescope, "SideOfPier"):
                    mount_info["side_of_pier"] = self.telescope.SideOfPier
            except Exception as e:
                self.logger.debug(f"Could not get additional mount properties: {e}")

            message = (
                f"Mount status: RA={mount_info['ra_deg']:.4f}°, "
                f"Dec={mount_info['dec_deg']:.4f}°, "
                f"Slewing={'Yes' if mount_info['is_slewing'] else 'No'}"
            )
            return success_status(message, data=mount_info, details=mount_info)

        except Exception as e:
            self.logger.error(f"Error getting mount status: {e}")
            return error_status(f"Error getting mount status: {e}", details={"is_connected": False})

    def __enter__(self) -> "ASCOMMount":
        """Context manager entry point.

        Enables the use of this class with Python's 'with' statement,
        ensuring automatic cleanup of resources.

        Returns:
            ASCOMMount: Self instance for context management.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit point.

        Automatically disconnects from the mount when exiting the context,
        ensuring proper cleanup even if exceptions occur.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self.disconnect()
