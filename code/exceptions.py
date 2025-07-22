#!/usr/bin/env python3
"""
Exception hierarchy for the telescope streaming system.
Provides structured error handling across all modules.
"""

from typing import Optional, Any, Dict


class TelescopeStreamingError(Exception):
    """Base exception for all telescope streaming errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class ConfigurationError(TelescopeStreamingError):
    """Raised when configuration is invalid or missing."""
    pass


class HardwareError(TelescopeStreamingError):
    """Base exception for hardware-related errors."""
    pass


class MountError(HardwareError):
    """Raised when telescope mount operations fail."""
    pass


class CameraError(HardwareError):
    """Raised when camera operations fail."""
    pass


class PlateSolveError(TelescopeStreamingError):
    """Raised when plate-solving operations fail."""
    pass


class OverlayError(TelescopeStreamingError):
    """Raised when overlay generation fails."""
    pass


class VideoProcessingError(TelescopeStreamingError):
    """Raised when video processing operations fail."""
    pass


class SIMBADError(TelescopeStreamingError):
    """Raised when SIMBAD queries fail."""
    pass


class ValidationError(TelescopeStreamingError):
    """Raised when input validation fails."""
    pass


class TimeoutError(TelescopeStreamingError):
    """Raised when operations timeout."""
    pass


class ConnectionError(TelescopeStreamingError):
    """Raised when connection to external services fails."""
    pass


class FileError(TelescopeStreamingError):
    """Raised when file operations fail."""
    pass 