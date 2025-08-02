"""
Alpyca Camera Wrapper - Python-native ASCOM camera interface.

This module provides a wrapper around the Alpyca library for ASCOM Alpaca devices,
offering a modern, platform-independent interface to astronomical cameras.
"""

from alpaca.camera import Camera as AlpycaCamera
from alpaca.exceptions import (
    NotConnectedException,
    InvalidOperationException,
    DriverException,
    NotImplementedException
)
from status import success_status, error_status, warning_status
import logging
import time
from pathlib import Path
import json
from datetime import datetime

class AlpycaCameraWrapper:
    """Python-native ASCOM camera wrapper using Alpyca."""
    
    def __init__(self, host="localhost", port=11111, device_id=0, config=None, logger=None):
        """Initialize Alpyca camera wrapper.
        
        Args:
            host: Alpaca server host
            port: Alpaca server port
            device_id: Camera device ID
            config: Configuration object
            logger: Logger instance
        """
        self.host = host
        self.port = port
        self.device_id = device_id
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.camera = None
        self.cooling_cache = {}
        self.cache_file = None
        
        # Initialize cache file path
        self._init_cache_path()
    
    def _init_cache_path(self):
        """Initialize cache file path."""
        try:
            cache_dir = Path("cache")
            cache_dir.mkdir(exist_ok=True)
            
            # Create cache filename based on connection info
            cache_filename = f"cooling_cache_alpaca_{self.host}_{self.port}_{self.device_id}.json"
            self.cache_file = cache_dir / cache_filename
        except Exception as e:
            self.logger.warning(f"Failed to initialize cache path: {e}")
    
    def connect(self):
        """Connect to the Alpyca camera.
        
        Returns:
            Status: Success or error status
        """
        try:
            self.logger.info(f"Connecting to Alpyca camera at {self.host}:{self.port}, device {self.device_id}")
            
            # Create connection string in the correct format
            connection_string = f"{self.host}:{self.port}"
            self.camera = AlpycaCamera(connection_string, self.device_id)
            self.camera.Connected = True
            
            # Load existing cache
            self._load_cooling_cache()
            
            self.logger.info(f"Successfully connected to: {self.camera.Name}")
            return success_status(f"Alpyca camera connected: {self.camera.Name}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Alpyca camera: {e}")
            return error_status(f"Failed to connect to Alpyca camera: {e}")
    
    def disconnect(self):
        """Disconnect from the Alpyca camera.
        
        Returns:
            Status: Success or error status
        """
        try:
            if self.camera:
                self.camera.Connected = False
                self.camera = None
                self.logger.info("Alpyca camera disconnected")
            return success_status("Alpyca camera disconnected")
        except Exception as e:
            self.logger.error(f"Failed to disconnect: {e}")
            return error_status(f"Failed to disconnect: {e}")
    
    def _load_cooling_cache(self):
        """Load cooling cache from file."""
        try:
            if self.cache_file and self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.cooling_cache = json.load(f)
                self.logger.debug(f"Loaded cooling cache from {self.cache_file}")
        except Exception as e:
            self.logger.warning(f"Failed to load cooling cache: {e}")
    
    def _save_cooling_cache(self):
        """Save cooling cache to file."""
        try:
            if self.cache_file:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.cooling_cache, f, indent=2)
                self.logger.debug(f"Saved cooling cache to {self.cache_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save cooling cache: {e}")
    
    def _update_cooling_cache(self):
        """Update cooling cache with current values."""
        try:
            if self.camera:
                self.cooling_cache = {
                    'temperature': self.ccd_temperature,
                    'target_temperature': self.set_ccd_temperature,
                    'cooler_on': self.cooler_on,
                    'cooler_power': self.cooler_power if self.can_get_cooler_power else None,
                    'timestamp': datetime.now().timestamp()
                }
                self._save_cooling_cache()
        except Exception as e:
            self.logger.warning(f"Failed to update cooling cache: {e}")
    
    # ============================================================================
    # Core Properties
    # ============================================================================
    
    @property
    def name(self):
        """Get camera name."""
        return self.camera.Name if self.camera else None
    
    @property
    def description(self):
        """Get camera description."""
        return self.camera.Description if self.camera else None
    
    @property
    def driver_info(self):
        """Get driver information."""
        return self.camera.DriverInfo if self.camera else None
    
    @property
    def driver_version(self):
        """Get driver version."""
        return self.camera.DriverVersion if self.camera else None
    
    @property
    def interface_version(self):
        """Get interface version."""
        return self.camera.InterfaceVersion if self.camera else None
    
    @property
    def connected(self):
        """Check if camera is connected."""
        return self.camera.Connected if self.camera else False
    
    # ============================================================================
    # Sensor Properties
    # ============================================================================
    
    @property
    def sensor_name(self):
        """Get sensor name."""
        return self.camera.SensorName if self.camera else None
    
    @property
    def sensor_type(self):
        """Get sensor type (monochrome/color)."""
        return self.camera.SensorType if self.camera else None
    
    @property
    def camera_x_size(self):
        """Get camera X size in pixels."""
        return self.camera.CameraXSize if self.camera else None
    
    @property
    def camera_y_size(self):
        """Get camera Y size in pixels."""
        return self.camera.CameraYSize if self.camera else None
    
    @property
    def pixel_size_x(self):
        """Get pixel size X in microns."""
        return self.camera.PixelSizeX if self.camera else None
    
    @property
    def pixel_size_y(self):
        """Get pixel size Y in microns."""
        return self.camera.PixelSizeY if self.camera else None
    
    @property
    def max_adu(self):
        """Get maximum ADU value."""
        return self.camera.MaxADU if self.camera else None
    
    @property
    def electrons_per_adu(self):
        """Get electrons per ADU."""
        return self.camera.ElectronsPerADU if self.camera else None
    
    @property
    def full_well_capacity(self):
        """Get full well capacity."""
        return self.camera.FullWellCapacity if self.camera else None
    
    # ============================================================================
    # Exposure Properties
    # ============================================================================
    
    @property
    def exposure_min(self):
        """Get minimum exposure time."""
        return self.camera.ExposureMin if self.camera else None
    
    @property
    def exposure_max(self):
        """Get maximum exposure time."""
        return self.camera.ExposureMax if self.camera else None
    
    @property
    def exposure_resolution(self):
        """Get exposure resolution."""
        return self.camera.ExposureResolution if self.camera else None
    
    @property
    def last_exposure_duration(self):
        """Get last exposure duration."""
        return self.camera.LastExposureDuration if self.camera else None
    
    @property
    def last_exposure_start_time(self):
        """Get last exposure start time."""
        return self.camera.LastExposureStartTime if self.camera else None
    
    @property
    def image_ready(self):
        """Check if image is ready."""
        return self.camera.ImageReady if self.camera else False
    
    @property
    def camera_state(self):
        """Get camera state."""
        return self.camera.CameraState if self.camera else None
    
    @property
    def percent_completed(self):
        """Get exposure completion percentage."""
        return self.camera.PercentCompleted if self.camera else None
    
    # ============================================================================
    # Binning Control
    # ============================================================================
    
    @property
    def bin_x(self):
        """Get X binning."""
        return self.camera.BinX if self.camera else None
    
    @bin_x.setter
    def bin_x(self, value):
        """Set X binning."""
        if self.camera:
            self.camera.BinX = value
    
    @property
    def bin_y(self):
        """Get Y binning."""
        return self.camera.BinY if self.camera else None
    
    @bin_y.setter
    def bin_y(self, value):
        """Set Y binning."""
        if self.camera:
            self.camera.BinY = value
    
    @property
    def max_bin_x(self):
        """Get maximum X binning."""
        return self.camera.MaxBinX if self.camera else None
    
    @property
    def max_bin_y(self):
        """Get maximum Y binning."""
        return self.camera.MaxBinY if self.camera else None
    
    @property
    def can_asymmetric_bin(self):
        """Check if asymmetric binning is supported."""
        return self.camera.CanAsymmetricBin if self.camera else False
    
    # ============================================================================
    # Cooling System
    # ============================================================================
    
    @property
    def can_set_ccd_temperature(self):
        """Check if CCD temperature can be set."""
        return self.camera.CanSetCCDTemperature if self.camera else False
    
    @property
    def can_get_cooler_power(self):
        """Check if cooler power can be read."""
        return self.camera.CanGetCoolerPower if self.camera else False
    
    @property
    def ccd_temperature(self):
        """Get current CCD temperature."""
        return self.camera.CCDTemperature if self.camera else None
    
    @property
    def set_ccd_temperature(self):
        """Get target CCD temperature."""
        return self.camera.SetCCDTemperature if self.camera else None
    
    @set_ccd_temperature.setter
    def set_ccd_temperature(self, value):
        """Set target CCD temperature."""
        if self.camera:
            self.camera.SetCCDTemperature = value
    
    @property
    def cooler_on(self):
        """Get cooler on/off state."""
        return self.camera.CoolerOn if self.camera else None
    
    @cooler_on.setter
    def cooler_on(self, value):
        """Set cooler on/off state."""
        if self.camera:
            self.camera.CoolerOn = value
    
    @property
    def cooler_power(self):
        """Get cooler power percentage."""
        return self.camera.CoolerPower if self.camera else None
    
    @property
    def heat_sink_temperature(self):
        """Get heat sink temperature."""
        return self.camera.HeatSinkTemperature if self.camera else None
    
    # ============================================================================
    # Gain and Offset Control
    # ============================================================================
    
    @property
    def gain(self):
        """Get current gain."""
        return self.camera.Gain if self.camera else None
    
    @gain.setter
    def gain(self, value):
        """Set gain."""
        if self.camera:
            self.camera.Gain = value
    
    @property
    def gain_min(self):
        """Get minimum gain."""
        return self.camera.GainMin if self.camera else None
    
    @property
    def gain_max(self):
        """Get maximum gain."""
        return self.camera.GainMax if self.camera else None
    
    @property
    def gains(self):
        """Get available gains."""
        return self.camera.Gains if self.camera else None
    
    @property
    def offset(self):
        """Get current offset."""
        return self.camera.Offset if self.camera else None
    
    @offset.setter
    def offset(self, value):
        """Set offset."""
        if self.camera:
            self.camera.Offset = value
    
    @property
    def offset_min(self):
        """Get minimum offset."""
        return self.camera.OffsetMin if self.camera else None
    
    @property
    def offset_max(self):
        """Get maximum offset."""
        return self.camera.OffsetMax if self.camera else None
    
    @property
    def offsets(self):
        """Get available offsets."""
        return self.camera.Offsets if self.camera else None
    
    # ============================================================================
    # Readout Modes
    # ============================================================================
    
    @property
    def readout_mode(self):
        """Get current readout mode."""
        return self.camera.ReadoutMode if self.camera else None
    
    @readout_mode.setter
    def readout_mode(self, value):
        """Set readout mode."""
        if self.camera:
            self.camera.ReadoutMode = value
    
    @property
    def readout_modes(self):
        """Get available readout modes."""
        return self.camera.ReadoutModes if self.camera else None
    
    @property
    def can_fast_readout(self):
        """Check if fast readout is supported."""
        return self.camera.CanFastReadout if self.camera else False
    
    @property
    def fast_readout(self):
        """Get fast readout state."""
        return self.camera.FastReadout if self.camera else None
    
    @fast_readout.setter
    def fast_readout(self, value):
        """Set fast readout state."""
        if self.camera:
            self.camera.FastReadout = value
    
    # ============================================================================
    # Camera Methods
    # ============================================================================
    
    def start_exposure(self, duration, light=True):
        """Start an exposure.
        
        Args:
            duration: Exposure duration in seconds
            light: True for light frame, False for dark frame
            
        Returns:
            Status: Success or error status
        """
        try:
            self.camera.StartExposure(duration, light)
            self.logger.info(f"Started {duration}s exposure (light={light})")
            return success_status("Exposure started")
        except Exception as e:
            self.logger.error(f"Failed to start exposure: {e}")
            return error_status(f"Failed to start exposure: {e}")
    
    def stop_exposure(self):
        """Stop the current exposure.
        
        Returns:
            Status: Success or error status
        """
        try:
            self.camera.StopExposure()
            self.logger.info("Exposure stopped")
            return success_status("Exposure stopped")
        except Exception as e:
            self.logger.error(f"Failed to stop exposure: {e}")
            return error_status(f"Failed to stop exposure: {e}")
    
    def abort_exposure(self):
        """Abort the current exposure.
        
        Returns:
            Status: Success or error status
        """
        try:
            self.camera.AbortExposure()
            self.logger.info("Exposure aborted")
            return success_status("Exposure aborted")
        except Exception as e:
            self.logger.error(f"Failed to abort exposure: {e}")
            return error_status(f"Failed to abort exposure: {e}")
    
    def get_image_array(self):
        """Get the image array.
        
        Returns:
            Status: Success with image data or error status
        """
        try:
            image_array = self.camera.ImageArray
            self.logger.info("Image array retrieved successfully")
            return success_status("Image retrieved", data=image_array)
        except Exception as e:
            self.logger.error(f"Failed to get image array: {e}")
            return error_status(f"Failed to get image array: {e}")
    
    # ============================================================================
    # Cooling Methods
    # ============================================================================
    
    def set_cooling(self, target_temp):
        """Set cooling target temperature.
        
        Args:
            target_temp: Target temperature in °C
            
        Returns:
            Status: Success or error status
        """
        try:
            if not self.can_set_ccd_temperature:
                return error_status("Cooling not supported by this camera")
            
            self.logger.info(f"Setting cooling target temperature to {target_temp}°C")
            
            # Set target temperature
            self.set_ccd_temperature = target_temp
            
            # Turn on cooler
            self.cooler_on = True
            
            # Update cache
            self._update_cooling_cache()
            
            self.logger.info(f"Cooling set successfully to {target_temp}°C")
            return success_status(f"Cooling set to {target_temp}°C")
        except Exception as e:
            self.logger.error(f"Failed to set cooling: {e}")
            return error_status(f"Failed to set cooling: {e}")
    
    def turn_cooling_off(self):
        """Turn off cooling.
        
        Returns:
            Status: Success or error status
        """
        try:
            if not self.can_set_ccd_temperature:
                return error_status("Cooling not supported by this camera")
            
            self.logger.info("Turning off cooling")
            
            # Turn off cooler
            self.cooler_on = False
            
            # Update cache
            self._update_cooling_cache()
            
            self.logger.info("Cooling turned off successfully")
            return success_status("Cooling turned off")
        except Exception as e:
            self.logger.error(f"Failed to turn off cooling: {e}")
            return error_status(f"Failed to turn off cooling: {e}")
    
    def get_cooling_status(self):
        """Get current cooling status.
        
        Returns:
            Status: Success with cooling data or error status
        """
        try:
            status = {
                'temperature': self.ccd_temperature,
                'target_temperature': self.set_ccd_temperature,
                'cooler_on': self.cooler_on,
                'cooler_power': self.cooler_power if self.can_get_cooler_power else None,
                'heat_sink_temperature': self.heat_sink_temperature
            }
            return success_status("Cooling status retrieved", data=status)
        except Exception as e:
            self.logger.error(f"Failed to get cooling status: {e}")
            return error_status(f"Failed to get cooling status: {e}")
    
    def force_refresh_cooling_status(self):
        """Force refresh cooling status by reading multiple times.
        
        Returns:
            Status: Success with refreshed cooling data or error status
        """
        try:
            if not self.can_set_ccd_temperature:
                return error_status("Cooling not supported by this camera")
            
            self.logger.info("Forcing cooling status refresh...")
            
            # Read multiple times to ensure fresh values
            temperatures = []
            powers = []
            cooler_states = []
            
            for i in range(5):
                try:
                    temp = self.ccd_temperature
                    temperatures.append(temp)
                    
                    if self.can_get_cooler_power:
                        power = self.cooler_power
                        powers.append(power)
                    
                    cooler_on = self.cooler_on
                    cooler_states.append(cooler_on)
                    
                    time.sleep(0.2)
                except Exception as e:
                    self.logger.warning(f"Error during refresh read {i+1}: {e}")
            
            # Use the last reading
            final_temp = temperatures[-1] if temperatures else None
            final_power = powers[-1] if powers else None
            final_cooler_on = cooler_states[-1] if cooler_states else None
            
            info = {
                'temperature': final_temp,
                'cooler_power': final_power,
                'cooler_on': final_cooler_on,
                'target_temperature': self.set_ccd_temperature,
                'can_set_cooler_power': self.can_get_cooler_power,
                'refresh_attempts': len(temperatures)
            }
            
            # Update cache
            self.cooling_cache.update({
                'temperature': final_temp,
                'cooler_power': final_power,
                'cooler_on': final_cooler_on,
                'target_temperature': self.set_ccd_temperature
            })
            self._save_cooling_cache()
            
            self.logger.info(f"Cooling status refreshed: temp={final_temp}°C, power={final_power}%, on={final_cooler_on}")
            return success_status("Cooling status refreshed", data=info)
            
        except Exception as e:
            self.logger.error(f"Error forcing cooling refresh: {e}")
            return error_status(f"Failed to refresh cooling status: {e}")
    
    def wait_for_cooling_stabilization(self, timeout=60, check_interval=2.0):
        """Wait for cooling system to stabilize.
        
        Args:
            timeout: Maximum time to wait in seconds
            check_interval: Interval between checks in seconds
            
        Returns:
            Status: Success with stabilization data or error status
        """
        try:
            if not self.can_set_ccd_temperature:
                return error_status("Cooling not supported by this camera")
            
            self.logger.info(f"Waiting for cooling stabilization (timeout: {timeout}s)...")
            
            start_time = time.time()
            last_power = None
            stable_count = 0
            
            while time.time() - start_time < timeout:
                # Force refresh
                refresh_status = self.force_refresh_cooling_status()
                if not refresh_status.is_success:
                    return refresh_status
                
                info = refresh_status.data
                current_power = info.get('cooler_power')
                current_temp = info.get('temperature')
                cooler_on = info.get('cooler_on')
                
                self.logger.info(f"Status: temp={current_temp}°C, power={current_power}%, on={cooler_on}")
                
                # Check if power is changing
                if current_power is not None:
                    if last_power is not None and abs(current_power - last_power) < 1.0:
                        stable_count += 1
                    else:
                        stable_count = 0
                    
                    last_power = current_power
                    
                    # If power is stable for 3 consecutive readings, consider it stabilized
                    if stable_count >= 3:
                        self.logger.info(f"Cooling stabilized: power={current_power}%, stable for {stable_count} readings")
                        return success_status("Cooling stabilized", data=info)
                
                time.sleep(check_interval)
            
            # Timeout reached
            final_info = self.get_cooling_status().data if self.get_cooling_status().is_success else {}
            return warning_status(f"Cooling stabilization timeout after {timeout}s", data=final_info)
            
        except Exception as e:
            self.logger.error(f"Error waiting for cooling stabilization: {e}")
            return error_status(f"Failed to wait for cooling stabilization: {e}")
    
    # ============================================================================
    # Utility Methods
    # ============================================================================
    
    def is_color_camera(self):
        """Check if the camera is a color camera.
        
        Returns:
            bool: True if color camera, False if monochrome
        """
        try:
            if not self.camera or not self.connected:
                return False
            
            sensor_type = self.sensor_type
            if sensor_type is not None:
                # Alpyca uses the same SensorType enum as ASCOM
                # 0 = Monochrome, 1 = Color, 2 = RgGg, 3 = RGGB, etc.
                if sensor_type in [1, 2, 3, 4, 5, 6]:  # All color types
                    self.logger.info(f"Color camera detected via SensorType: {sensor_type}")
                    return True
                elif sensor_type == 0:  # Monochrome
                    self.logger.info("Monochrome camera detected via SensorType: 0")
                    return False
            
            # Fallback: check if Bayer pattern is available
            if hasattr(self.camera, 'BayerOffsetX') and hasattr(self.camera, 'BayerOffsetY'):
                bayer_offset_x = self.camera.BayerOffsetX
                bayer_offset_y = self.camera.BayerOffsetY
                if bayer_offset_x is not None and bayer_offset_y is not None:
                    self.logger.info("Color camera detected via Bayer pattern")
                    return True
            
            # Default: assume monochrome
            self.logger.warning("Could not determine camera type, assuming monochrome")
            return False
            
        except Exception as e:
            self.logger.warning(f"Error detecting camera type: {e}")
            return False
    
    def get_camera_info(self):
        """Get comprehensive camera information.
        
        Returns:
            dict: Camera information dictionary
        """
        try:
            info = {
                'name': self.name,
                'description': self.description,
                'driver_info': self.driver_info,
                'driver_version': self.driver_version,
                'interface_version': self.interface_version,
                'connected': self.connected,
                'sensor_name': self.sensor_name,
                'sensor_type': self.sensor_type,
                'camera_size': f"{self.camera_x_size}x{self.camera_y_size}",
                'pixel_size': f"{self.pixel_size_x}x{self.pixel_size_y} μm",
                'max_adu': self.max_adu,
                'is_color': self.is_color_camera(),
                'cooling_supported': self.can_set_ccd_temperature,
                'cooler_power_supported': self.can_get_cooler_power,
                'binning_supported': self.max_bin_x is not None and self.max_bin_y is not None,
                'gain_supported': self.gain is not None,
                'offset_supported': self.offset is not None,
                'readout_modes_supported': self.readout_modes is not None
            }
            return success_status("Camera info retrieved", data=info)
        except Exception as e:
            self.logger.error(f"Failed to get camera info: {e}")
            return error_status(f"Failed to get camera info: {e}") 