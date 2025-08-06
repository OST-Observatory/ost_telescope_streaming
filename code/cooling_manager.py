#!/usr/bin/env python3
"""
Cooling Manager for astronomical cameras.

This module provides comprehensive cooling management including:
- Target temperature setting and monitoring
- Stabilization waiting
- Warmup phases to prevent thermal shock
- Integration with ASCOM and Alpyca cameras
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from status import Status, success_status, error_status, warning_status
from exceptions import CoolingError


class CoolingManager:
    """Manages camera cooling operations with thermal shock prevention."""
    
    def __init__(self, camera, config, logger=None):
        """Initialize cooling manager.
        
        Args:
            camera: Camera object (ASCOM or Alpyca)
            config: Configuration manager
            logger: Logger instance
        """
        self.camera = camera
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Cooling settings from config
        cooling_config = config.get_camera_config().get('cooling', {})
        self.target_temp = cooling_config.get('target_temperature', -10.0)
        self.wait_for_cooling = cooling_config.get('wait_for_cooling', True)
        self.stabilization_timeout = cooling_config.get('stabilization_timeout', 300)  # 5 minutes
        self.stabilization_tolerance = cooling_config.get('stabilization_tolerance', 1.0)  # 1°C
        self.warmup_rate = cooling_config.get('warmup_rate', 2.0)  # 2°C per minute
        self.warmup_final_temp = cooling_config.get('warmup_final_temp', 15.0)  # 15°C
        
        # State tracking
        self.is_cooling = False
        self.is_warming_up = False
        self.cooling_start_time = None
        self.warmup_start_time = None
        self.monitor_thread = None
        self.monitoring = False
        
        # Auto-start cooling if enabled
        enable_cooling = cooling_config.get('enable_cooling', False)
        if enable_cooling and self.target_temp is not None and self.camera.can_set_ccd_temperature:
            self.logger.info(f"Auto-starting cooling to {self.target_temp}°C")
            self.set_target_temperature(self.target_temp)
        elif enable_cooling and not self.camera.can_set_ccd_temperature:
            self.logger.warning("Cooling enabled but camera does not support cooling")
        elif not enable_cooling:
            self.logger.info("Cooling disabled in configuration")
        
    def set_target_temperature(self, target_temp: float) -> Status:
        """Set target temperature and start cooling.
        
        Args:
            target_temp: Target temperature in °C
            
        Returns:
            Status: Success or error status
        """
        try:
            self.logger.info(f"Setting cooling target temperature to {target_temp}°C")
            
            # Check if camera supports cooling
            if not self.camera.can_set_ccd_temperature:
                return error_status("Camera does not support cooling")
            
            # Get current status
            current_temp = self.camera.ccd_temperature
            current_power = self.camera.cooler_power
            current_cooler_on = self.camera.cooler_on
            
            self.logger.info(f"Current status - Temp: {current_temp}°C, Power: {current_power}%, Cooler on: {current_cooler_on}")
            
            # Set target temperature
            self.camera.set_ccd_temperature = target_temp
            self.logger.info(f"Target temperature set to {target_temp}°C")
            
            # Turn on cooler
            self.camera.cooler_on = True
            self.logger.info("Cooler turned on")
            
            # Wait for settings to take effect
            time.sleep(2.0)
            
            # Verify settings
            new_temp = self.camera.ccd_temperature
            new_power = self.camera.cooler_power
            new_cooler_on = self.camera.cooler_on
            new_target = self.camera.set_ccd_temperature
            
            self.logger.info(f"New status - Temp: {new_temp}°C, Power: {new_power}%, Cooler on: {new_cooler_on}, Target: {new_target}°C")
            
            # Update state
            self.target_temp = target_temp
            self.is_cooling = True
            self.cooling_start_time = datetime.now()
            
            details = {
                'target_temp': target_temp,
                'current_temp': current_temp,
                'new_temp': new_temp,
                'current_power': current_power,
                'new_power': new_power,
                'current_cooler_on': current_cooler_on,
                'new_cooler_on': new_cooler_on,
                'new_target': new_target
            }
            
            if new_cooler_on and new_target == target_temp:
                self.logger.info(f"Cooling set successfully to {target_temp}°C")
                return success_status(f"Cooling set to {target_temp}°C", details=details)
            else:
                self.logger.warning("Cooling settings may not have been applied correctly")
                return warning_status("Cooling set but verification failed", details=details)
                
        except Exception as e:
            self.logger.error(f"Failed to set cooling: {e}")
            return error_status(f"Failed to set cooling: {e}")
    
    def wait_for_stabilization(self, timeout: Optional[int] = None, 
                              tolerance: Optional[float] = None) -> Status:
        """Wait for temperature to stabilize at target.
        
        Args:
            timeout: Timeout in seconds (default: from config)
            tolerance: Temperature tolerance in °C (default: from config)
            
        Returns:
            Status: Success or error status
        """
        timeout = timeout or self.stabilization_timeout
        tolerance = tolerance or self.stabilization_tolerance
        
        try:
            self.logger.info(f"Waiting for temperature stabilization (timeout: {timeout}s, tolerance: ±{tolerance}°C)")
            
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=timeout)
            
            # Track temperature readings for stability check
            temp_readings = []
            stable_count = 0
            required_stable_readings = 6  # 30 seconds of stability (6 * 5s)
            
            while datetime.now() < end_time:
                current_temp = self.camera.ccd_temperature
                current_power = self.camera.cooler_power
                target_temp = self.camera.set_ccd_temperature
                
                temp_readings.append(current_temp)
                if len(temp_readings) > 10:  # Keep last 10 readings
                    temp_readings.pop(0)
                
                elapsed = (datetime.now() - start_time).total_seconds()
                temp_diff = abs(current_temp - target_temp)
                
                self.logger.info(f"[{elapsed:6.1f}s] Temp: {current_temp:5.1f}°C, Power: {current_power:5.1f}%, "
                               f"Target: {target_temp:5.1f}°C, Diff: {temp_diff:4.1f}°C")
                
                # Check if temperature is within tolerance
                if temp_diff <= tolerance:
                    stable_count += 1
                    if stable_count >= required_stable_readings:
                        self.logger.info(f"✅ Temperature stabilized at {current_temp:.1f}°C (target: {target_temp:.1f}°C)")
                        return success_status(f"Temperature stabilized at {current_temp:.1f}°C", 
                                            details={'final_temp': current_temp, 'target_temp': target_temp, 
                                                   'elapsed_seconds': elapsed})
                else:
                    stable_count = 0
                
                time.sleep(5)  # Check every 5 seconds
            
            # Timeout reached
            final_temp = self.camera.ccd_temperature
            final_diff = abs(final_temp - target_temp)
            
            self.logger.warning(f"Temperature stabilization timeout. Final temp: {final_temp:.1f}°C, "
                              f"target: {target_temp:.1f}°C, diff: {final_diff:.1f}°C")
            
            return warning_status(f"Temperature stabilization timeout. Final temp: {final_temp:.1f}°C", 
                                details={'final_temp': final_temp, 'target_temp': target_temp, 
                                       'elapsed_seconds': timeout, 'final_diff': final_diff})
            
        except Exception as e:
            self.logger.error(f"Error during temperature stabilization: {e}")
            return error_status(f"Error during temperature stabilization: {e}")
    
    def start_warmup(self, final_temp: Optional[float] = None) -> Status:
        """Start warmup phase to prevent thermal shock.
        
        Args:
            final_temp: Final temperature for warmup (default: from config)
            
        Returns:
            Status: Success or error status
        """
        final_temp = final_temp or self.warmup_final_temp
        
        try:
            self.logger.info(f"Starting warmup phase to {final_temp}°C")
            
            # Turn off cooler
            self.camera.cooler_on = False
            self.logger.info("Cooler turned off")
            
            # Update state
            self.is_cooling = False
            self.is_warming_up = True
            self.warmup_start_time = datetime.now()
            
            # Start monitoring thread
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._warmup_monitor, args=(final_temp,))
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            return success_status(f"Warmup started to {final_temp}°C")
            
        except Exception as e:
            self.logger.error(f"Failed to start warmup: {e}")
            return error_status(f"Failed to start warmup: {e}")
    
    def _warmup_monitor(self, final_temp: float):
        """Monitor warmup progress."""
        try:
            while self.monitoring:
                current_temp = self.camera.ccd_temperature
                elapsed = (datetime.now() - self.warmup_start_time).total_seconds()
                
                self.logger.info(f"[{elapsed:6.1f}s] Warmup - Temp: {current_temp:5.1f}°C, Target: {final_temp:5.1f}°C")
                
                # Check if warmup is complete
                if current_temp >= final_temp:
                    self.logger.info(f"✅ Warmup completed. Final temperature: {current_temp:.1f}°C")
                    self.is_warming_up = False
                    break
                
                time.sleep(30)  # Check every 30 seconds
                
        except Exception as e:
            self.logger.error(f"Error during warmup monitoring: {e}")
        finally:
            self.monitoring = False
    
    def stop_warmup(self) -> Status:
        """Stop warmup phase."""
        try:
            self.logger.info("Stopping warmup phase")
            self.monitoring = False
            self.is_warming_up = False
            
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            
            return success_status("Warmup stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop warmup: {e}")
            return error_status(f"Failed to stop warmup: {e}")
    
    def get_cooling_status(self) -> Dict[str, Any]:
        """Get current cooling status."""
        try:
            status = {
                'temperature': self.camera.ccd_temperature,
                'target_temperature': self.target_temp,  # Use configured target temperature
                'cooler_power': self.camera.cooler_power,
                'cooler_on': self.camera.cooler_on,
                'is_cooling': self.is_cooling,
                'is_warming_up': self.is_warming_up,
                'can_set_temperature': self.camera.can_set_ccd_temperature,
                'can_get_power': self.camera.can_get_cooler_power
            }
            
            if self.cooling_start_time:
                status['cooling_duration'] = (datetime.now() - self.cooling_start_time).total_seconds()
            
            if self.warmup_start_time:
                status['warmup_duration'] = (datetime.now() - self.warmup_start_time).total_seconds()
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get cooling status: {e}")
            return {'error': str(e)}
    
    def start_status_monitor(self, interval: int = 30, callback=None) -> Status:
        """Start periodic cooling status monitoring.
        
        Args:
            interval: Update interval in seconds
            callback: Optional callback function(status_data) for status updates
            
        Returns:
            Status: Success or error status
        """
        try:
            if self.monitoring:
                return warning_status("Status monitor already running")
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(
                target=self._status_monitor_loop,
                args=(interval, callback),
                daemon=True
            )
            self.monitor_thread.start()
            
            self.logger.info(f"🌡️  Cooling status monitor started (interval: {interval}s)")
            return success_status(f"Cooling status monitor started (interval: {interval}s)")
            
        except Exception as e:
            self.logger.error(f"Failed to start status monitor: {e}")
            return error_status(f"Failed to start status monitor: {e}")
    
    def stop_status_monitor(self) -> Status:
        """Stop cooling status monitoring."""
        try:
            if not self.monitoring:
                return success_status("Status monitor not running")
            
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5.0)
            
            self.logger.info("🌡️  Cooling status monitor stopped")
            return success_status("Cooling status monitor stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop status monitor: {e}")
            return error_status(f"Failed to stop status monitor: {e}")
    
    def _status_monitor_loop(self, interval: int, callback=None):
        """Internal status monitoring loop."""
        try:
            while self.monitoring:
                # Get current status
                status_data = self.get_cooling_status()
                
                if 'error' not in status_data:
                    # Format status for display
                    temperature = status_data.get('temperature')
                    target_temp = status_data.get('target_temperature')
                    cooler_power = status_data.get('cooler_power')
                    cooler_on = status_data.get('cooler_on')
                    
                    if temperature is not None:
                        # Format temperature display
                        temp_str = f"{temperature:.1f}°C"
                        if target_temp is not None:
                            temp_diff = temperature - target_temp
                            if abs(temp_diff) <= 1.0:
                                temp_status = "✅"
                            elif temp_diff > 0:
                                temp_status = "📈"
                            else:
                                temp_status = "📉"
                            temp_str += f" (Target: {target_temp:.1f}°C, Diff: {temp_diff:+.1f}°C) {temp_status}"
                        
                        # Format cooler power display
                        power_str = ""
                        if cooler_power is not None:
                            if cooler_on:
                                if cooler_power > 0:
                                    power_str = f"❄️  Cooler: {cooler_power:.0f}%"
                                else:
                                    power_str = "❄️  Cooler: 0% (at target)"
                            else:
                                power_str = "❄️  Cooler: OFF"
                        
                        # Combine status information
                        status_parts = [f"🌡️  Sensor: {temp_str}"]
                        if power_str:
                            status_parts.append(power_str)
                        
                        status_message = " | ".join(status_parts)
                        
                        # Log status
                        self.logger.info(status_message)
                        
                        # Call callback if provided
                        if callback:
                            try:
                                callback(status_data)
                            except Exception as e:
                                self.logger.warning(f"Callback error: {e}")
                    else:
                        self.logger.debug("🌡️  Cooling status: No temperature data available")
                else:
                    self.logger.debug("🌡️  Cooling status: No cooling data available")
                
                # Wait for next update or stop signal
                for _ in range(interval):
                    if not self.monitoring:
                        break
                    time.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"Error in status monitor loop: {e}")
        finally:
            self.monitoring = False
    
    def shutdown(self) -> Status:
        """Shutdown cooling manager and start warmup."""
        try:
            self.logger.info("Shutting down cooling manager")
            
            # Stop any monitoring
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            
            # Start warmup if cooling was active
            if self.is_cooling:
                return self.start_warmup()
            else:
                return success_status("Cooling manager shutdown complete")
                
        except Exception as e:
            self.logger.error(f"Failed to shutdown cooling manager: {e}")
            return error_status(f"Failed to shutdown cooling manager: {e}")


def create_cooling_manager(camera, config, logger=None) -> CoolingManager:
    """Factory function to create cooling manager for any camera type."""
    return CoolingManager(camera, config, logger) 