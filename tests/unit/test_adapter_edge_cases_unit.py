import pytest


def test_alpaca_start_exposure_raises():
    from capture.adapters import AlpacaCameraAdapter

    class _Cam:
        def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
            raise RuntimeError("fail")

    adapter = AlpacaCameraAdapter(_Cam())
    with pytest.raises(RuntimeError):
        adapter.start_exposure(0.1, True)


def test_alpaca_image_ready_missing_attribute_defaults_false():
    from capture.adapters import AlpacaCameraAdapter

    class _Cam:
        def get_image_array(self):  # pragma: no cover - not used here
            return None

    adapter = AlpacaCameraAdapter(_Cam())
    assert adapter.image_ready is False


def test_alpaca_get_image_array_passthrough_none():
    from capture.adapters import AlpacaCameraAdapter

    class _Cam:
        image_ready = True

        def start_exposure(self, exposure_time_s: float, light: bool = True) -> None:
            pass

        def get_image_array(self):
            return None

    adapter = AlpacaCameraAdapter(_Cam())
    adapter.start_exposure(0.01, True)
    assert adapter.wait_for_image_ready(0.1) is True
    assert adapter.get_image_array() is None


def test_ascom_get_image_array_handles_missing_data():
    from capture.adapters import AscomCameraAdapter

    class _Cam:
        def connect(self):
            class _S:
                is_success = True

            return _S()

        def disconnect(self) -> None:
            pass

        def expose(self, *args, **kwargs) -> None:
            pass

        def get_image(self):
            class _S:
                is_success = True
                data = None

            return _S()

    adapter = AscomCameraAdapter(_Cam())
    adapter.start_exposure(0.1, True)
    assert adapter.wait_for_image_ready(0.05)
    assert adapter.get_image_array() is None


def test_ascom_property_defaults_and_color_flag():
    from capture.adapters import AscomCameraAdapter

    class _Cam:
        # no is_color_camera method, so adapter should return False
        pass

    adapter = AscomCameraAdapter(_Cam())
    assert adapter.is_color_camera() is False
    assert adapter.bin_x is None
    assert adapter.bin_y is None
