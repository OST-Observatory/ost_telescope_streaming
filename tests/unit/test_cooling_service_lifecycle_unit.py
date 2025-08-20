from __future__ import annotations

from typing import Any, Dict


def test_cooling_service_start_stop_paths(monkeypatch):
    # Minimal fake camera and config to drive cooling paths
    class _Cam:
        pass

    class _Cfg:
        def get_camera_config(self) -> Dict[str, Any]:
            return {"cooling": {"enable_cooling": True, "status_interval": 1}}

    # Import service
    from services.cooling.service import CoolingService

    svc = CoolingService(_Cfg(), logger=None)
    svc.initialize(_Cam())
    # Start and stop status monitor (should handle gracefully even if no real backend)
    svc.start_status_monitor(1)
    svc.stop_status_monitor()
    # Properties should be accessible without raising
    _ = svc.is_cooling
    _ = svc.is_warming_up
