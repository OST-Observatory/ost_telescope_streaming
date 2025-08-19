from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_parse_header_string_basic():
    # Dynamically load script module since 'tools' isn't on PYTHONPATH in tests
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "add_fits_headers.py"
    spec = importlib.util.spec_from_file_location("add_fits_headers", str(mod_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    assert mod is not None
    spec.loader.exec_module(mod)
    parse_header_string = mod.parse_header_string

    k, v, c = parse_header_string("EXPTIME=12")
    assert k == "EXPTIME" and v == 12 and c is None

    k, v, c = parse_header_string("GAIN=2.5")
    assert k == "GAIN" and abs(v - 2.5) < 1e-9 and c is None

    k, v, c = parse_header_string("BOOL=true,flag")
    assert k == "BOOL" and v is True and c == "flag"

    k, v, c = parse_header_string("NAME=ASI2600MC")
    assert k == "NAME" and v == "ASI2600MC" and c is None


def test_parse_header_string_invalid():
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "add_fits_headers.py"
    spec = importlib.util.spec_from_file_location("add_fits_headers", str(mod_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    assert mod is not None
    spec.loader.exec_module(mod)
    parse_header_string = mod.parse_header_string

    with pytest.raises(ValueError):
        parse_header_string("NOEQUALS")


def test_get_fits_files_missing_dir(tmp_path):
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "add_fits_headers.py"
    spec = importlib.util.spec_from_file_location("add_fits_headers", str(mod_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    assert mod is not None
    spec.loader.exec_module(mod)
    get_fits_files = mod.get_fits_files

    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        get_fits_files(str(missing))


def test_add_headers_to_fits_roundtrip(tmp_path):
    try:
        import astropy.io.fits as fits
    except Exception:
        pytest.skip("astropy not available")

    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "add_fits_headers.py"
    spec = importlib.util.spec_from_file_location("add_fits_headers", str(mod_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    assert mod is not None
    spec.loader.exec_module(mod)
    add_headers_to_fits = mod.add_headers_to_fits

    # Create a minimal FITS file
    f = tmp_path / "x.fits"
    import numpy as np

    fits.PrimaryHDU(np.zeros((4, 4), dtype=np.uint16)).writeto(f)

    ok = add_headers_to_fits(
        f,
        headers_to_add=[("TESTVAL", 123, "number"), ("FLAG", True, None)],
        headers_to_remove=[],
        backup=False,
        logger=None,
    )
    assert ok

    with fits.open(f) as hdul:
        hdr = hdul[0].header
        assert hdr["TESTVAL"] == 123
        assert hdr["FLAG"] is True
