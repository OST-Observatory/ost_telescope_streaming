# Drivers

This package contains hardware driver adapters used by the system.

- `drivers/ascom/camera.py`: Classic ASCOM camera adapter (Windows COM-based)
- `drivers/ascom/mount.py`: ASCOM mount adapter
- `drivers/alpaca/camera.py`: Alpaca (ASCOM over HTTP) camera adapter using Alpyca

Guidelines:
- Import drivers via `drivers.ascom.camera`, `drivers.alpaca.camera` in code and docs
- Keep public APIs stable; add docstrings for key methods and properties
- Avoid importing drivers at module top-level in code paths that run in non-driver environments (use lazy imports)
