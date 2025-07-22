#!/usr/bin/env python3
"""
OST Telescope Streaming System
==============================

A comprehensive system for telescope streaming with plate-solving,
overlay generation, and ASCOM camera support.

Modules:
--------
- config_manager: Configuration management
- video_capture: Video capture and ASCOM camera integration
- video_processor: Video processing pipeline
- plate_solver: Plate-solving functionality
- plate_solver_automated: Automated plate-solving
- overlay_runner: Overlay generation and management
- generate_overlay: Overlay creation utilities
- ascom_mount: ASCOM mount control
- ascom_camera: ASCOM camera control
- exceptions: Custom exception hierarchy
- status: Status object system
"""

__version__ = "1.0.0"
__author__ = "OST Telescope Streaming Team"

# Import main classes for easy access
try:
    from .config_manager import config
    from .video_capture import VideoCapture
    from .video_processor import VideoProcessor
    from .plate_solver import PlateSolve2
    from .plate_solver_automated import PlateSolve2Automated
    from .overlay_runner import OverlayRunner
    from .generate_overlay import OverlayGenerator
    from .ascom_mount import ASCOMMount
    from .ascom_camera import ASCOMCamera
    from .exceptions import TelescopeStreamingError
    from .status import Status, CameraStatus, MountStatus
except ImportError:
    # Allow partial imports for development
    pass 