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
