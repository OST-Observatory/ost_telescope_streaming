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
- platesolve.solver: Plate-solving functionality
- platesolve.platesolve2: Automated plate-solving
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
    from .capture.controller import VideoCapture
    from .processing.processor import VideoProcessor
    # Updated locations after module reorg (maintain best-effort imports)
    from .platesolve.solver import PlateSolve2  # type: ignore
    from .platesolve.platesolve2 import PlateSolve2Automated  # type: ignore
    from .overlay_runner import OverlayRunner
    from .overlay.generator import OverlayGenerator  # type: ignore
    from .ascom_mount import ASCOMMount
    from .ascom_camera import ASCOMCamera
    from .exceptions import TelescopeStreamingError
    from .status import Status, CameraStatus, MountStatus
    
    # Create default config instance only when explicitly requested
    # This prevents automatic loading of config.yaml during import
    def get_default_config():
        """Get the default configuration instance."""
        from .config_manager import ConfigManager
        return ConfigManager()
    
    # Lazy config instance - only created when accessed
    _default_config = None
    def get_config():
        """Get the default configuration instance (lazy loading)."""
        global _default_config
        if _default_config is None:
            _default_config = get_default_config()
        return _default_config
    
except ImportError:
    # Allow partial imports for development
    pass 