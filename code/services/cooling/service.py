#!/usr/bin/env python3
"""
CoolingService encapsulates cooling manager lifecycle and shields callers from
direct dependencies. It provides a narrow API used by capture/processor layers.
"""

from __future__ import annotations

from typing import Any, Optional

from status import success_status, error_status, warning_status


class CoolingService:
    def __init__(self, config, logger=None) -> None:
        self.config = config
        self.logger = logger
        self.manager = None
        self.enabled: bool = bool(self.config.get_camera_config().get('cooling', {}).get('enable_cooling', False))

    def initialize(self, camera: Any):
        if not self.enabled:
            return success_status("Cooling disabled")
        try:
            from services.cooling.backend import create_cooling_manager
            self.manager = create_cooling_manager(camera, self.config, self.logger)
            return success_status("Cooling manager initialized")
        except Exception as e:
            self.manager = None
            return error_status(f"Failed to initialize cooling manager: {e}")

    def initialize_and_stabilize(self, target_temp: float, wait_for_cooling: bool, timeout_s: float):
        if not self.enabled:
            return success_status("Cooling not enabled")
        if not self.manager:
            return error_status("Cooling manager not initialized")
        try:
            status = self.manager.set_target_temperature(target_temp)
            if not status.is_success:
                return status
            if wait_for_cooling:
                stabilization_status = self.manager.wait_for_stabilization(timeout=timeout_s)
                if not stabilization_status.is_success:
                    return warning_status(f"Cooling initialized but stabilization failed: {stabilization_status.message}")
            return success_status("Cooling initialized successfully")
        except Exception as e:
            return error_status(f"Failed to initialize cooling: {e}")

    def start_warmup(self):
        if not self.manager:
            return error_status("Cooling manager not available")
        return self.manager.start_warmup()

    def wait_for_warmup_completion(self, timeout: float):
        if not self.manager:
            return error_status("Cooling manager not available")
        return self.manager.wait_for_warmup_completion(timeout=timeout)

    def start_status_monitor(self, interval: float):
        if not self.manager:
            return error_status("Cooling manager not available")
        return self.manager.start_status_monitor(interval=interval)

    def stop_status_monitor(self):
        if not self.manager:
            return error_status("Cooling manager not available")
        return self.manager.stop_status_monitor()

    @property
    def is_cooling(self) -> bool:
        try:
            return bool(self.manager and self.manager.is_cooling)
        except Exception:
            return False

    @property
    def is_warming_up(self) -> bool:
        try:
            return bool(self.manager and self.manager.is_warming_up)
        except Exception:
            return False

    def get_cooling_status(self):
        if not self.manager:
            return {'error': 'Cooling manager not available'}
        return self.manager.get_cooling_status()


