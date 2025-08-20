from __future__ import annotations

from typing import Any, Dict


def test_overlay_generator_reads_cooling_status_safely(monkeypatch, cfg_no_ui):
    # Fake VideoProcessor with cooling_service that returns a minimal status-like object
    class _Stat:
        is_success = True
        data = {"set_point": -10.0, "power": 0.5}
        message = "ok"
        details: Dict[str, Any] = {}

    class _Cooling:
        def get_cooling_status(self):
            return _Stat()

    class _VP:
        cooling_service = _Cooling()

    from overlay.generator import OverlayGenerator

    gen = OverlayGenerator(config=cfg_no_ui)
    gen.video_processor = _VP()

    # Ensure astroquery is available via fake to reach info panel path
    monkeypatch.setitem(__import__("sys").modules, "astroquery", object())
    monkeypatch.setitem(__import__("sys").modules, "astroquery.simbad", object())

    # Should not raise when assembling info panel
    assert hasattr(gen, "_get_info_panel_font")
