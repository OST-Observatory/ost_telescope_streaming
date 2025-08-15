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
import threading
import time
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
        # Status/logging interval used by monitor and stabilization loop
        try:
            self.status_interval = float(cooling_config.get("status_interval", 30))
        except Exception:
            self.status_interval = 30.0
        self.is_cooling = False
        self.is_warming_up = False
        self.cooling_start_time = None
        self.warmup_start_time = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop: Optional[threading.Event] = None

    def set_target_temperature(self, target_temp: float) -> Status:
        try:
            self.logger.info(f"Setting cooling target temperature to {target_temp}°C")
            # Capability detection: support various camera APIs (snake_case, CamelCase)
            can_set = bool(
                getattr(self.camera, "can_set_ccd_temperature", False)
                or getattr(self.camera, "CanSetCCDTemperature", False)
            )
            if not can_set:
                return error_status("Camera does not support cooling")
            # Read current temperature safely
            current_temp = self._get_temperature()
            # Set target temperature (property or method)
            try:
                if hasattr(self.camera, "set_ccd_temperature"):
                    self.camera.set_ccd_temperature = target_temp
                elif hasattr(self.camera, "SetCCDTemperature"):
                    # Some drivers expose a setter method
                    self.camera.SetCCDTemperature(target_temp)
            except Exception:
                self.logger.debug("Cooling: failed to set target via primary API, trying alt names")
                # Try common alternates some drivers use
                try:
                    if hasattr(self.camera, "temperature_setpoint"):
                        self.camera.temperature_setpoint = target_temp
                    elif hasattr(self.camera, "TargetTemperature"):
                        self.camera.TargetTemperature = target_temp
                except Exception:
                    pass
            # Switch cooler on if supported
            try:
                if hasattr(self.camera, "cooler_on"):
                    self.camera.cooler_on = True
                elif hasattr(self.camera, "CoolerOn"):
                    self.camera.CoolerOn = True
                elif hasattr(self.camera, "set_cooler_on"):
                    self.camera.set_cooler_on = True
            except Exception:
                pass
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
                current_temp = self._get_temperature()
                # Compare against the manager's target (robust across drivers)
                if current_temp is not None:
                    diff = abs(float(current_temp) - float(self.target_temp))
                else:
                    diff = float("inf")
                # Add power and cooler-on status to log
                cooler_power = self._get_any(self.camera, ["cooler_power", "CoolerPower"], None)
                cooler_on = bool(
                    self._get_any(self.camera, ["cooler_on", "CoolerOn", "set_cooler_on"], False)
                )
                self.logger.info(
                    "Temp: %.1f°C, Target: %.1f°C, Diff: %+0.1f°C, Power: %s, Cooler: %s",
                    current_temp if current_temp is not None else float("nan"),
                    float(self.target_temp),
                    diff,
                    str(cooler_power),
                    str(cooler_on),
                )
                if diff <= tolerance:
                    return success_status(
                        f"Temperature stabilized at {current_temp:.1f}°C",
                        details={"final_temp": current_temp},
                    )
                # Sleep between updates to avoid log spam
                time.sleep(max(1.0, float(self.status_interval)))
        except Exception as e:
            return error_status(f"Error during temperature stabilization: {e}")
        # On timeout, include safe target readout
        tgt = None
        try:
            tgt = self._get_any(
                self.camera,
                [
                    "set_ccd_temperature",
                    "SetCCDTemperature",
                    "TargetTemperature",
                    "temperature_setpoint",
                ],
                None,
            )
        except Exception:
            tgt = None
        return warning_status("Temperature stabilization timeout", details={"target": tgt})

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
        try:
            if self._monitor_stop is not None:
                self._monitor_stop.set()
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
            self._monitor_stop = None
            return success_status("Cooling status monitor stopped")
        except Exception as e:
            return warning_status(f"Failed to stop cooling status monitor: {e}")

    def start_status_monitor(self, interval: float):
        try:
            # If already running, don't start another
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return warning_status("Cooling status monitor already running")

            self._monitor_stop = threading.Event()

            def _loop() -> None:
                assert self._monitor_stop is not None
                while not self._monitor_stop.is_set():
                    try:
                        status = self.get_cooling_status()
                        temp = status.get("temperature")
                        tgt = status.get("target_temperature")
                        pwr = status.get("cooler_power")
                        cooling = status.get("is_cooling")
                        warming = status.get("is_warming_up")
                        self.logger.info(
                            "🌡️  Cooling status: T=%s°C target=%s°C power=%s cooling=%s warming=%s",
                            str(temp),
                            str(tgt),
                            str(pwr),
                            str(cooling),
                            str(warming),
                        )
                    except Exception as exc:
                        self.logger.debug(f"Cooling status monitor error: {exc}")
                    time.sleep(max(1.0, float(interval)))

            self._monitor_thread = threading.Thread(
                target=_loop, name="CoolingStatusMonitor", daemon=True
            )
            self._monitor_thread.start()
            return success_status("Cooling status monitor started")
        except Exception as e:
            return warning_status(f"Failed to start cooling status monitor: {e}")

    def wait_for_warmup_completion(self, timeout: int) -> Status:
        """Block until warmup completes or timeout.

        Warmup is considered complete when the sensor temperature rises to or above
        the configured warmup_final_temp (or when the cooler is off and temp stops rising).
        """
        try:
            start = time.time()
            last_temp = None
            while (time.time() - start) < float(timeout):
                try:
                    t = self._get_temperature()
                    current_temp = float(t) if t is not None else None
                except Exception:
                    current_temp = None

                # Consider warmup done if we reached or exceeded target warmup temp
                if current_temp is not None:
                    if current_temp >= float(self.warmup_final_temp):
                        self.is_warming_up = False
                        return success_status(
                            f"Warmup completed at {current_temp:.1f}°C",
                            details={"final_temp": current_temp},
                        )
                    # If temperature stagnates and cooler is off, assume done
                    if last_temp is not None:
                        temp_delta = abs(current_temp - last_temp)  # type: ignore[unreachable]
                        cooler_on_attr = getattr(self.camera, "cooler_on", False)
                        cooler_on_flag = bool(cooler_on_attr)
                        if (temp_delta < 0.1) and (not cooler_on_flag):
                            self.is_warming_up = False
                            return success_status(
                                f"Warmup completed (stabilized at {current_temp:.1f}°C)",
                                details={"final_temp": current_temp},
                            )

                last_temp = current_temp
                time.sleep(1.0)

            # Timeout
            return warning_status(
                "Warmup timeout",
                details={"timeout": timeout, "final_temp": last_temp},
            )
        except Exception as e:
            return error_status(f"Error waiting for warmup completion: {e}")

    def get_cooling_status(self) -> Dict[str, Any]:
        try:
            return {
                "temperature": self._get_temperature(),
                "target_temperature": self.target_temp,
                "cooler_power": self._get_any(self.camera, ["cooler_power", "CoolerPower"], None),
                "cooler_on": bool(
                    self._get_any(self.camera, ["cooler_on", "CoolerOn", "set_cooler_on"], False)
                ),
                "is_cooling": self.is_cooling,
                "is_warming_up": self.is_warming_up,
                "can_set_temperature": bool(
                    self._get_any(
                        self.camera, ["can_set_ccd_temperature", "CanSetCCDTemperature"], False
                    )
                ),
                "can_get_power": bool(
                    self._get_any(self.camera, ["can_get_cooler_power", "CanGetCoolerPower"], False)
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    # --- helpers ---
    def _get_any(self, obj: Any, names: list[str], default: Any) -> Any:
        for name in names:
            try:
                val = getattr(obj, name)
                return val
            except Exception:
                continue
        return default

    def _get_temperature(self) -> Optional[float]:
        try:
            val = self._get_any(
                self.camera, ["ccd_temperature", "CCDTemperature", "Temperature"], None
            )
            return float(val) if val is not None else None
        except Exception:
            return None


def create_cooling_manager(camera, config, logger=None) -> CoolingManager:
    return CoolingManager(camera, config, logger)
