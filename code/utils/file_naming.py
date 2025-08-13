#!/usr/bin/env python3
"""
File naming helpers to standardize capture and master frame filenames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _fmt_exp(exp_s: float) -> str:
    return f"{float(exp_s):.3f}s"


def _opt(v) -> str:
    return "none" if v is None else str(int(v))


def build_live_basename(
    exposure_time_s: float,
    gain: Optional[float],
    offset: Optional[int],
    readout_mode: Optional[int],
    binning: Optional[int],
    timestamp: Optional[str] = None,
    capture_count: Optional[int] = None,
) -> str:
    parts = [
        "capture",
        _fmt_exp(exposure_time_s),
        f"g{_opt(gain)}",
        f"o{_opt(offset)}",
        f"r{_opt(readout_mode)}",
        f"b{_opt(binning)}",
    ]
    if timestamp:
        parts.insert(1, timestamp)
    if capture_count is not None:
        parts.append(f"{int(capture_count):04d}")
    return "_".join(parts)


def build_live_filename(base_dir: Path | str, basename: str, extension: str) -> Path:
    base = Path(base_dir)
    ext = extension.lower().lstrip(".")
    return base / f"{basename}.{ext}"


def build_master_dark_name(
    exposure_time_s: float,
    gain: Optional[float],
    offset: Optional[int],
    readout_mode: Optional[int],
    binning: Optional[int],
    timestamp: str,
) -> str:
    return (
        "master_dark_"
        f"{_fmt_exp(exposure_time_s)}_g{_opt(gain)}_o{_opt(offset)}_r{_opt(readout_mode)}"
        f"_b{_opt(binning)}_{timestamp}.fits"
    )


def build_master_flat_name(
    exposure_time_s: float,
    gain: Optional[float],
    offset: Optional[int],
    readout_mode: Optional[int],
    binning: Optional[int],
    timestamp: str,
) -> str:
    return (
        "master_flat_"
        f"{_fmt_exp(exposure_time_s)}_g{_opt(gain)}_o{_opt(offset)}_r{_opt(readout_mode)}"
        f"_b{_opt(binning)}_{timestamp}.fits"
    )


def build_master_bias_name(
    gain: Optional[float],
    offset: Optional[int],
    readout_mode: Optional[int],
    binning: Optional[int],
    timestamp: str,
) -> str:
    return (
        "master_bias_"
        f"g{_opt(gain)}_o{_opt(offset)}_r{_opt(readout_mode)}"
        f"_b{_opt(binning)}_{timestamp}.fits"
    )
