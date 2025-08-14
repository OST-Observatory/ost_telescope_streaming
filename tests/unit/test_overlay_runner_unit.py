import types


class _Cfg:
    def get_overlay_config(self):
        return {
            "update": {"update_interval": 1, "max_retries": 1, "retry_delay": 0},
            "use_timestamps": False,
        }

    def get_frame_processing_config(self):
        return {"enabled": False}

    def get_camera_config(self):
        return {"cooling": {"enable_cooling": False}}


def test_overlay_runner_start_stop(monkeypatch):
    from overlay.runner import OverlayRunner

    # Monkeypatch ASCOM mount availability path in runner (avoid import in run())
    monkeypatch.setitem(__import__("sys").modules, "ascom_mount", types.SimpleNamespace())

    runner = OverlayRunner(config=_Cfg())
    status = runner.start_observation()
    assert status.is_success
    status = runner.stop_observation()
    assert status.is_success
