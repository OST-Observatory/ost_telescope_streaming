#!/usr/bin/env python3
"""
Dataclass representing a captured frame with metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class Frame:
    data: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None  # e.g., 'alpaca', 'ascom', 'opencv'
    green_channel: Optional[np.ndarray] = None  # debayered green channel for solving/stacking
    # Original undebayered (mono Bayer) data after calibration; used for RAW FITS archival
    raw_data: Optional[np.ndarray] = None
