#!/usr/bin/env python3
"""
Shared constants for the telescope streaming system.
"""

from __future__ import annotations

from typing import Final, Set

# FITS header keys (a subset, centralized to avoid typos)
class FitsHeaderKeys:
    EXPTIME: Final[str] = 'EXPTIME'
    GAIN: Final[str] = 'GAIN'
    OFFSET: Final[str] = 'OFFSET'
    READOUT: Final[str] = 'READOUT'
    XPIXSZ: Final[str] = 'XPIXSZ'
    YPIXSZ: Final[str] = 'YPIXSZ'
    SENSWID: Final[str] = 'SENSWID'
    SENSHGT: Final[str] = 'SENSHGT'
    FOCALLEN: Final[str] = 'FOCALLEN'
    PIXSCALE: Final[str] = 'PIXSCALE'
    XBAYROFF: Final[str] = 'XBAYROFF'
    YBAYROFF: Final[str] = 'YBAYROFF'
    CCD_TEMP: Final[str] = 'CCD-TEMP'
    CCD_TSET: Final[str] = 'CCD-TSET'
    COOLPOW: Final[str] = 'COOLPOW'
    COOLERON: Final[str] = 'COOLERON'
    DARKCOR: Final[str] = 'DARKCOR'
    FLATCOR: Final[str] = 'FLATCOR'
    CALSTAT: Final[str] = 'CALSTAT'
    MSTDARK: Final[str] = 'MSTDARK'
    MSTFLAT: Final[str] = 'MSTFLAT'
    CAMERA: Final[str] = 'CAMERA'
    CAMNAME: Final[str] = 'CAMNAME'
    DATE_OBS: Final[str] = 'DATE-OBS'

# Supported Bayer patterns (common)
BAYER_PATTERNS: Set[str] = {'RGGB', 'GRBG', 'GBRG', 'BGGR'}

# Default directories
DEFAULT_MASTER_DIR: Final[str] = 'master_frames'
DEFAULT_PLATE_SOLVE_DIR: Final[str] = 'plate_solve_frames'
DEFAULT_CAPTURED_DIR: Final[str] = 'captured_frames'

# Default file formats
DISPLAY_EXTENSIONS: Final[set[str]] = {'.png', '.jpg', '.jpeg'}
FITS_EXTENSIONS: Final[set[str]] = {'.fit', '.fits'}
