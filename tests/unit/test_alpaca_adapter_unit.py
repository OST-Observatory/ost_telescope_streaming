import numpy as np


class _FakeAlpacaCam:
    def __init__(self) -> None:
        self.gain = 100.0
        self.offset = 50
        self.readout_mode = 0
        self.image_ready = False

    def connect(self):
        class _S:
            is_success = True

        return _S()

    def disconnect(self) -> None:
        pass

    def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
        self.image_ready = True

    def get_image_array(self):
        return np.zeros((2, 2), dtype=np.uint8)

    def is_color_camera(self) -> bool:
        return True


def test_alpaca_adapter_basic():
    from capture.adapters import AlpacaCameraAdapter

    cam = _FakeAlpacaCam()
    adapter = AlpacaCameraAdapter(cam)
    assert adapter.connect().is_success
    adapter.start_exposure(0.05, True)
    assert adapter.wait_for_image_ready(0.1)
    img = adapter.get_image_array()
    assert isinstance(img, np.ndarray)


def test_alpaca_adapter_properties_roundtrip():
    from capture.adapters import AlpacaCameraAdapter

    cam = _FakeAlpacaCam()
    adapter = AlpacaCameraAdapter(cam)
    adapter.gain = 120.0
    adapter.offset = 60
    adapter.readout_mode = 1
    assert cam.gain == 120.0
    assert cam.offset == 60
    assert cam.readout_mode == 1


def test_alpaca_adapter_wait_timeout_false(monkeypatch):
    from capture.adapters import AlpacaCameraAdapter

    class _Cam:
        image_ready = False

        def connect(self):  # pragma: no cover - trivial stub
            class _S:
                is_success = True

            return _S()

        def disconnect(self) -> None:  # pragma: no cover - trivial stub
            pass

        def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
            # Never becomes ready
            self.image_ready = False

        def get_image_array(self):  # pragma: no cover - not reached in timeout test
            return np.zeros((2, 2), dtype=np.uint8)

    adapter = AlpacaCameraAdapter(_Cam())
    adapter.start_exposure(0.01, True)
    assert adapter.wait_for_image_ready(0.2) is False
