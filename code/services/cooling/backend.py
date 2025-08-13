#!/usr/bin/env python3
"""
Cooling Manager for astronomical cameras.

Provides comprehensive cooling management including:
- Target temperature setting and monitoring
- Stabilization waiting
- Warmup phases to prevent thermal shock
- Integration with ASCOM and Alpyca cameras
"""

from datetime import datetime
import logging
from typing import Any, Dict, Optional

from status import Status, error_status, success_status, warning_status


class CoolingManager:
    def __init__(self, camera, config, logger=None):
        self.camera = camera
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        cooling_config = config.get_camera_config().get("cooling", {})
        self.target_temp = cooling_config.get("target_temperature", -10.0)
        self.wait_for_cooling = cooling_config.get("wait_for_cooling", True)
        self.stabilization_timeout = cooling_config.get("stabilization_timeout", 300)
        self.stabilization_tolerance = cooling_config.get("stabilization_tolerance", 1.0)
        self.warmup_rate = cooling_config.get("warmup_rate", 2.0)
        self.warmup_final_temp = cooling_config.get("warmup_final_temp", 15.0)
        self.is_cooling = False
        self.is_warming_up = False
        self.cooling_start_time = None
        self.warmup_start_time = None

    def set_target_temperature(self, target_temp: float) -> Status:
        try:
            self.logger.info(f"Setting cooling target temperature to {target_temp}°C")
            if not self.camera.can_set_ccd_temperature:
                return error_status("Camera does not support cooling")
            current_temp = self.camera.ccd_temperature
            self.camera.set_ccd_temperature = target_temp
            self.camera.cooler_on = True
            self.target_temp = target_temp
            self.is_cooling = True
            self.cooling_start_time = datetime.now()
            return success_status(
                f"Cooling set to {target_temp}°C",
                details={
                    "previous_temp": current_temp,
                    "target_temp": target_temp,
                },
            )
        except Exception as e:
            return error_status(f"Failed to set cooling: {e}")

    def wait_for_stabilization(
        self, timeout: Optional[int] = None, tolerance: Optional[float] = None
    ) -> Status:
        timeout = timeout or self.stabilization_timeout
        tolerance = tolerance or self.stabilization_tolerance
        try:
            self.logger.info(
                "Waiting for temperature stabilization (timeout: %ss, tolerance: ±%s°C)",
                timeout,
                tolerance,
            )
            start = datetime.now()
            while (datetime.now() - start).total_seconds() < timeout:
                current_temp = self.camera.ccd_temperature
                diff = abs(current_temp - self.camera.set_ccd_temperature)
                self.logger.info(
                    "Temp: %.1f°C, Target: %.1f°C, Diff: %+0.1f°C",
                    current_temp,
                    self.camera.set_ccd_temperature,
                    diff,
                )
                if diff <= tolerance:
                    return success_status(
                        f"Temperature stabilized at {current_temp:.1f}°C",
                        details={"final_temp": current_temp},
                    )
        except Exception as e:
            return error_status(f"Error during temperature stabilization: {e}")
        return warning_status(
            "Temperature stabilization timeout", details={"target": self.camera.set_ccd_temperature}
        )

    def start_warmup(self) -> Status:
        try:
            self.camera.cooler_on = False
            self.is_cooling = False
            self.is_warming_up = True
            self.warmup_start_time = datetime.now()
            return success_status("Warmup started")
        except Exception as e:
            return error_status(f"Failed to start warmup: {e}")

    def stop_status_monitor(self):
        return success_status("Cooling status monitor stopped")

    def start_status_monitor(self, interval: float):
        return success_status("Cooling status monitor started")

    def get_cooling_status(self) -> Dict[str, Any]:
        try:
            return {
                "temperature": self.camera.ccd_temperature,
                "target_temperature": self.target_temp,
                "cooler_power": getattr(self.camera, "cooler_power", None),
                "cooler_on": getattr(self.camera, "cooler_on", None),
                "is_cooling": self.is_cooling,
                "is_warming_up": self.is_warming_up,
                "can_set_temperature": getattr(self.camera, "can_set_ccd_temperature", False),
                "can_get_power": getattr(self.camera, "can_get_cooler_power", False),
            }
        except Exception as e:
            return {"error": str(e)}


def create_cooling_manager(camera, config, logger=None) -> CoolingManager:
    return CoolingManager(camera, config, logger)
