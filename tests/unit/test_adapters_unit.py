from typing import Any

import numpy as np


class _FakeAscomCam:
    def __init__(self) -> None:
        self.gain = 100.0
        self.offset = 50
        self.readout_mode = 0

    def connect(self):
        class _S:
            is_success = True

        return _S()

    def disconnect(self) -> None:
        pass

    def expose(
        self, exposure_time_s: float, gain: Any, binning: int, offset: Any, readout: Any
    ) -> None:
        self._image = np.zeros((2, 2), dtype=np.uint8)

    def get_image(self):
        class _S:
            is_success = True
            data = np.zeros((2, 2), dtype=np.uint8)

        return _S()


def test_ascom_adapter_basic():
    from capture.adapters import AscomCameraAdapter

    cam = _FakeAscomCam()
    adapter = AscomCameraAdapter(cam)
    assert adapter.connect().is_success
    adapter.start_exposure(0.1, True)
    assert adapter.wait_for_image_ready(0.1)
    img = adapter.get_image_array()
    assert isinstance(img, np.ndarray)
