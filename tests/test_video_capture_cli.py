def test_import_videocapture_and_config():
    from capture.controller import VideoCapture  # noqa: F401
    from config_manager import ConfigManager  # noqa: F401

    # Just ensure they import under test environment
    assert True
