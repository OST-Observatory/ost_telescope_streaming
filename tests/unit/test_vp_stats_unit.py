from processing.processor import VideoProcessor


class DummyConfig:
    def get_frame_processing_config(self):
        return {"enabled": False}

    def get_plate_solve_config(self):
        return {"auto_solve": False}

    def get_mount_config(self):
        return {}


def test_get_statistics_contains_rolling_timings():
    vp = VideoProcessor(config=DummyConfig())
    # simulate timings
    vp._telemetry = {
        "capture": [10.0, 20.0, 30.0],
        "save": [5.0],
        "solve": [],
    }
    status = vp.get_statistics()
    assert status.is_success
    data = status.data
    assert "timings_ms" in data
    assert data["timings_ms"]["capture"]["avg"] == 20.0
    assert data["timings_ms"]["save"]["min"] == 5.0
    assert data["timings_ms"]["solve"]["max"] == 0.0
