#!/usr/bin/env python3
"""
Image orientation helpers.
"""

from __future__ import annotations

from typing import Tuple
import numpy as np


def needs_rotation(shape: Tuple[int, ...]) -> bool:
    if len(shape) < 2:
        return False
    height, width = shape[0], shape[1]
    return height > width


def enforce_long_side_horizontal(image: np.ndarray) -> tuple[np.ndarray, bool]:
    """Ensure the long side is horizontal; returns possibly transposed image and whether rotated."""
    if needs_rotation(image.shape):
        if image.ndim == 2:
            return np.transpose(image, (1, 0)), True
        elif image.ndim == 3:
            return np.transpose(image, (1, 0, 2)), True
    return image, False
