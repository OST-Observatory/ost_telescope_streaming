#!/usr/bin/env python3
"""
OST Telescope Streaming System
==============================

A comprehensive system for telescope streaming with plate-solving,
overlay generation, and camera support.

Modules:
--------
- config_manager: Configuration management
- capture.controller: Video capture controller
- processing.processor: Video processing pipeline
- platesolve.solver: Plate-solving functionality
- platesolve.platesolve2: Automated plate-solving
- overlay.generator: Overlay creation utilities
- overlay.runner: Overlay orchestration
- drivers.ascom.mount: ASCOM mount control
- drivers.ascom.camera: ASCOM camera control
- drivers.alpaca.camera: Alpaca camera control
- services.cooling.service: Cooling service API
- services.cooling.backend: Cooling backend factory
- exceptions: Custom exception hierarchy
- status: Status object system
"""

__version__ = "1.0.0"
__author__ = "OST Telescope Streaming Team"

# Public API re-exports (stable entry points)
from .capture.controller import VideoCapture  # noqa: F401
from .processing.processor import VideoProcessor  # noqa: F401
from .platesolve.solver import PlateSolverFactory, PlateSolveResult  # noqa: F401
from .platesolve.platesolve2 import PlateSolve2Automated  # noqa: F401
from .overlay.generator import OverlayGenerator  # noqa: F401
from .overlay.runner import OverlayRunner  # noqa: F401
from .drivers.ascom.mount import ASCOMMount  # noqa: F401
from .drivers.ascom.camera import ASCOMCamera  # noqa: F401
from .drivers.alpaca.camera import AlpycaCameraWrapper  # noqa: F401
from .services.cooling.service import CoolingService  # noqa: F401
from .services.cooling.backend import create_cooling_manager  # noqa: F401
from .exceptions import TelescopeStreamingError  # noqa: F401
from .status import Status, CameraStatus, MountStatus  # noqa: F401


def get_default_config():
	"""Get a default configuration instance without auto-loading config.yaml."""
	from .config_manager import ConfigManager
	return ConfigManager()


_default_config = None


def get_config():
	"""Get a lazily created default configuration instance."""
	global _default_config
	if _default_config is None:
		_default_config = get_default_config()
	return _default_config