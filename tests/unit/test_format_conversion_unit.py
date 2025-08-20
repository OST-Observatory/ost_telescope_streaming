import numpy as np


class _Cfg:
    def get_frame_processing_config(self):
        return {"normalization": {"method": "hist"}}

    def get_camera_config(self):
        return {"auto_debayer": False}


def test_convert_grayscale_without_cv2(monkeypatch):
    from processing import format_conversion as fc

    # Force cv2 unavailability path
    monkeypatch.setattr(fc, "cv2", None, raising=False)
    img16 = (np.arange(100, dtype=np.uint16).reshape(10, 10) * 10).astype(np.uint16)
    out = fc.convert_camera_data_to_opencv(
        img16, camera=type("C", (), {"sensor_type": None})(), config=_Cfg()
    )
    assert out is not None
    assert out.dtype == np.uint8
    assert out.shape == img16.shape


def test_convert_color_bayer_with_cv2(monkeypatch):
    from processing import format_conversion as fc

    # Fake minimal cv2 with COLOR constants and cvtColor behavior
    class _CV2:
        COLOR_BayerRG2BGR = 1
        COLOR_BayerGR2BGR = 2
        COLOR_BayerGB2BGR = 3
        COLOR_BayerBG2BGR = 4
        COLOR_GRAY2BGR = 5
        COLOR_RGB2BGR = 6
        COLOR_RGBA2BGR = 7

        @staticmethod
        def cvtColor(arr, code):
            # Return a 3-channel uint8 array to simulate BGR conversion
            import numpy as _np

            if arr.ndim == 2:
                h, w = arr.shape
                out = _np.stack([arr, arr, arr], axis=2)
                return (out / 256).astype(_np.uint8)
            if arr.ndim == 3:
                return arr.astype(_np.uint8)
            raise ValueError("bad shape")

    monkeypatch.setattr(fc, "cv2", _CV2(), raising=False)
    img16 = (np.arange(100, dtype=np.uint16).reshape(10, 10) * 10).astype(np.uint16)
    # Provide camera with Bayer pattern
    camera = type("C", (), {"sensor_type": "RGGB"})()
    out = fc.convert_camera_data_to_opencv(img16, camera=camera, config=_Cfg())
    assert out is not None
    # After conversion and normalization, should be uint8
    assert out.dtype == np.uint8
    assert out.ndim == 3 and out.shape[2] == 3


def test_orientation_correction_transpose(monkeypatch):
    from processing import format_conversion as fc

    class _CV2:
        COLOR_GRAY2BGR = 5

        @staticmethod
        def cvtColor(arr, code):
            import numpy as _np

            # keep as uint16 to exercise normalize_to_uint8
            return _np.stack([arr, arr, arr], axis=2).astype(_np.uint8)

    monkeypatch.setattr(fc, "cv2", _CV2(), raising=False)
    # Tall image (h > w) triggers transpose
    img16 = (np.arange(60, dtype=np.uint16).reshape(20, 3) * 100).astype(np.uint16)
    out = fc.convert_camera_data_to_opencv(
        img16, camera=type("C", (), {"sensor_type": None})(), config=_Cfg()
    )
    assert out is not None
    # After transpose, width > height
    h, w = out.shape[:2]
    assert w > h
