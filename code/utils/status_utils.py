"""Utilities for working with nested Status objects.

This module provides helpers to consistently unwrap Status-like objects that may
contain nested `data` fields and optional `details` dictionaries.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def unwrap_status(value: Any, max_depth: int = 5) -> Tuple[Any, Dict[str, Any]]:
    """Unwrap nested Status-like objects into (data, merged_details).

    This function follows `.data` attributes up to max_depth, and merges any
    `.details` dicts encountered along the way. If `value` is a list, it will
    be returned as-is (caller can convert to ndarray if needed).

    Args:
        value: The potential Status-like object or raw data
        max_depth: Maximum levels of nested `.data` to follow

    Returns:
        (leaf_data, merged_details)
    """
    merged_details: Dict[str, Any] = {}
    current = value
    depth = 0

    # Pull top-level details/metadata if present
    details = getattr(current, 'details', None)
    if isinstance(details, dict):
        merged_details.update(details)
    metadata = getattr(current, 'metadata', None)
    if isinstance(metadata, dict):
        merged_details.update(metadata)

    while depth < max_depth and hasattr(current, 'data'):
        parent = current
        current = getattr(current, 'data')
        depth += 1
        # Merge details/metadata at this level if any
        details = getattr(parent, 'details', None)
        if isinstance(details, dict):
            merged_details.update(details)
        metadata = getattr(parent, 'metadata', None)
        if isinstance(metadata, dict):
            merged_details.update(metadata)

    return current, merged_details


def is_success_status(obj: Any) -> bool:
    """Best-effort check if an object looks like a successful Status."""
    return hasattr(obj, 'is_success') and bool(getattr(obj, 'is_success'))


