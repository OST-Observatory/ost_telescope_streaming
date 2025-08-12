#!/usr/bin/env python3
"""
Camera settings dataclass to standardize capture metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Union


@dataclass
class CameraSettings:
    exposure_time_s: Optional[float] = None
    gain: Optional[float] = None
    offset: Optional[int] = None
    readout_mode: Optional[int] = None
    binning: Optional[Union[int, list[int]]] = None
    dimensions: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        # Convert dataclass to dict and drop None values
        raw = asdict(self)
        return {k: v for k, v in raw.items() if v is not None}


