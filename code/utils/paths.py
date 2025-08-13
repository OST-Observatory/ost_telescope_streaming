#!/usr/bin/env python3
"""
Path utilities for common directories.
"""

from __future__ import annotations

from pathlib import Path

from .constants import (
    DEFAULT_CAPTURED_DIR,
    DEFAULT_MASTER_DIR,
    DEFAULT_PLATE_SOLVE_DIR,
)


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_master_frames_dir(config) -> Path:
    # Try to read from config, fallback to default
    try:
        calib_cfg = config.get_calibration_config()
        base = calib_cfg.get("master_dir", DEFAULT_MASTER_DIR)
        return Path(base)
    except Exception:
        return Path(DEFAULT_MASTER_DIR)


def get_plate_solve_dir(config) -> Path:
    try:
        frame_cfg = config.get_frame_processing_config()
        base = frame_cfg.get("plate_solve_dir", DEFAULT_PLATE_SOLVE_DIR)
        return Path(base)
    except Exception:
        return Path(DEFAULT_PLATE_SOLVE_DIR)


def get_captured_frames_dir(config) -> Path:
    try:
        frame_cfg = config.get_frame_processing_config()
        base = frame_cfg.get("output_dir", DEFAULT_CAPTURED_DIR)
        return Path(base)
    except Exception:
        return Path(DEFAULT_CAPTURED_DIR)
