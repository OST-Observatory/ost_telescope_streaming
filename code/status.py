#!/usr/bin/env python3
"""
Status objects for the telescope streaming system.
Provides structured return values for operations.
"""

from typing import Optional, Any, Dict, Generic, TypeVar
from dataclasses import dataclass
from enum import Enum
import time


class StatusLevel(Enum):
    """Status levels for operations."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


T = TypeVar('T')


@dataclass
class Status(Generic[T]):
    """Generic status object for operation results."""
    
    level: StatusLevel
    message: str
    data: Optional[T] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()
    
    @property
    def is_success(self) -> bool:
        """Check if status indicates success."""
        return self.level == StatusLevel.SUCCESS
    
    @property
    def is_error(self) -> bool:
        """Check if status indicates an error."""
        return self.level in (StatusLevel.ERROR, StatusLevel.CRITICAL)
    
    @property
    def is_warning(self) -> bool:
        """Check if status indicates a warning."""
        return self.level == StatusLevel.WARNING
    
    def __str__(self) -> str:
        return f"{self.level.value.upper()}: {self.message}"


@dataclass
class MountStatus(Status[tuple[float, float]]):
    """Status object for mount operations."""
    
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    is_connected: bool = False
    
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.data and len(self.data) == 2:
            self.ra_deg, self.dec_deg = self.data


@dataclass
class CameraStatus(Status[Any]):
    """Status object for camera operations."""
    
    camera_index: Optional[int] = None
    frame_size: Optional[tuple[int, int]] = None
    fps: Optional[float] = None
    is_capturing: bool = False
    
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.details:
            self.camera_index = self.details.get('camera_index')
            self.frame_size = self.details.get('frame_size')
            self.fps = self.details.get('fps')
            self.is_capturing = self.details.get('is_capturing', False)


@dataclass
class PlateSolveStatus(Status[Dict[str, Any]]):
    """Status object for plate-solving operations."""
    
    ra_center: Optional[float] = None
    dec_center: Optional[float] = None
    fov_width: Optional[float] = None
    fov_height: Optional[float] = None
    confidence: Optional[float] = None
    stars_detected: Optional[int] = None
    solving_time: Optional[float] = None
    solver_used: Optional[str] = None
    
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.data:
            self.ra_center = self.data.get('ra_center')
            self.dec_center = self.data.get('dec_center')
            self.fov_width = self.data.get('fov_width')
            self.fov_height = self.data.get('fov_height')
            self.confidence = self.data.get('confidence')
            self.stars_detected = self.data.get('stars_detected')
            self.solving_time = self.data.get('solving_time')
            self.solver_used = self.data.get('solver_used')


@dataclass
class OverlayStatus(Status[str]):
    """Status object for overlay generation."""
    
    output_file: Optional[str] = None
    objects_drawn: Optional[int] = None
    fov_deg: Optional[float] = None
    magnitude_limit: Optional[float] = None
    
    def __post_init__(self) -> None:
        super().__post_init__()
        self.output_file = self.data
        if self.details:
            self.objects_drawn = self.details.get('objects_drawn')
            self.fov_deg = self.details.get('fov_deg')
            self.magnitude_limit = self.details.get('magnitude_limit')


@dataclass
class VideoProcessingStatus(Status[Dict[str, Any]]):
    """Status object for video processing operations."""
    
    capture_count: int = 0
    solve_count: int = 0
    successful_solves: int = 0
    is_running: bool = False
    last_solve_result: Optional[PlateSolveStatus] = None
    
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.data:
            self.capture_count = self.data.get('capture_count', 0)
            self.solve_count = self.data.get('solve_count', 0)
            self.successful_solves = self.data.get('successful_solves', 0)
            self.is_running = self.data.get('is_running', False)


# Factory functions for creating status objects
def success_status(message: str, data: Optional[T] = None, details: Optional[Dict[str, Any]] = None) -> Status[T]:
    """Create a success status."""
    return Status(StatusLevel.SUCCESS, message, data, details)


def warning_status(message: str, data: Optional[T] = None, details: Optional[Dict[str, Any]] = None) -> Status[T]:
    """Create a warning status."""
    return Status(StatusLevel.WARNING, message, data, details)


def error_status(message: str, data: Optional[T] = None, details: Optional[Dict[str, Any]] = None) -> Status[T]:
    """Create an error status."""
    return Status(StatusLevel.ERROR, message, data, details)


def critical_status(message: str, data: Optional[T] = None, details: Optional[Dict[str, Any]] = None) -> Status[T]:
    """Create a critical error status."""
    return Status(StatusLevel.CRITICAL, message, data, details) 