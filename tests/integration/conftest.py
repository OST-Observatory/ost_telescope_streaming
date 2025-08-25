import pytest


def _try_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    # Skip tests that require optional hardware libs if not present
    alpaca_missing = not _try_import("alpaca.camera") and not _try_import("drivers.alpaca.camera")
    ascom_missing = not _try_import("ascom_camera")
    video_capture_missing = not _try_import("video_capture") and not _try_import(
        "capture.controller"
    )
    skip_alpaca = pytest.mark.skip(reason="alpaca not installed")
    skip_ascom = pytest.mark.skip(reason="ascom not installed")
    skip_vc = pytest.mark.skip(reason="video capture module missing")
    for item in items:
        name = item.nodeid.lower()
        if alpaca_missing and ("alpaca" in name):
            item.add_marker(skip_alpaca)
        if ascom_missing and ("ascom" in name):
            item.add_marker(skip_ascom)
        if video_capture_missing and ("image_orientation" in name or "video_capture" in name):
            item.add_marker(skip_vc)


def pytest_ignore_collect(collection_path, config):  # noqa: D401
    """Ignore collecting certain integration tests if optional deps are missing."""
    p = str(collection_path)
    try:

        def _has(mod: str) -> bool:
            try:
                __import__(mod)
                return True
            except Exception:
                return False

        if ("alpaca" in p) and not (_has("alpaca.camera") or _has("drivers.alpaca.camera")):
            return True
        if ("ascom" in p) and not _has("ascom_camera"):
            return True
        if ("image_orientation" in p or "video_capture" in p) and not (
            _has("video_capture") or _has("capture.controller")
        ):
            return True
    except Exception:
        return False
    return False
