from __future__ import annotations


def test_defaults_without_config(tmp_path, monkeypatch):
    # Point to a non-existing config file
    cfg_path = tmp_path / "missing_config.yaml"
    monkeypatch.chdir(tmp_path)

    from config_manager import ConfigManager

    cm = ConfigManager(str(cfg_path))
    # Ensure defaults exist for key sections
    m = cm.get_mount_config()
    t = cm.get_telescope_config()
    cam = cm.get_camera_config()
    fp = cm.get_frame_processing_config()
    ovl = cm.get_overlay_config()

    assert isinstance(m, dict) and "driver_id" in m
    assert isinstance(t, dict) and "focal_length" in t
    assert isinstance(cam, dict) and "opencv" in cam
    assert isinstance(fp, dict) and "output_dir" in fp
    assert isinstance(ovl, dict) and "field_of_view" in ovl


def test_get_dot_path_and_reload(tmp_path):
    # Write a minimal config file overriding some defaults
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mount:
  driver_id: TEST.MOUNT
overlay:
  field_of_view: 2.5
        """,
        encoding="utf-8",
    )

    from config_manager import ConfigManager

    cm = ConfigManager(str(cfg))
    assert cm.get("mount.driver_id") == "TEST.MOUNT"
    assert cm.get_overlay_config()["field_of_view"] == 2.5

    # Modify on disk, then reload
    cfg.write_text(
        """
mount:
  driver_id: OTHER.MOUNT
overlay:
  field_of_view: 3.0
        """,
        encoding="utf-8",
    )
    cm.reload()
    assert cm.get("mount.driver_id") == "OTHER.MOUNT"
    assert cm.get_overlay_config()["field_of_view"] == 3.0


def test_missing_keys_and_safe_defaults(tmp_path):
    # Partially specified config
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        """
camera:
  ascom:
    ascom_driver: ASCOM.ZWOASI.Camera
        """,
        encoding="utf-8",
    )

    from config_manager import ConfigManager

    cm = ConfigManager(str(cfg))
    cam = cm.get_camera_config()
    # Ensure nested defaults merged
    assert cam["ascom"]["binning"] == 1
    assert cam["opencv"]["camera_index"] == 0
    # Safe get with default
    assert cm.get("does.not.exist", default=42) == 42
