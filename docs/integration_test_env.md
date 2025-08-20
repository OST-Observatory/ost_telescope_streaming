Integration Test Environment Guide

This guide explains how to run the integration tests locally and in CI, including optional hardware-dependent tests.

Prerequisites
- Python 3.12 (or compatible)
- Dependencies from `requirements.txt` and `requirements-dev.txt`
- Optional: PlateSolve2 (Windows) or an alternative solver configured
- Optional: ASCOM Platform (Windows) / Alpaca environment for mounts/cameras

Environment Variables
- OST_CAMERA_CONNECTED: set to `1` when a real camera is connected; otherwise `0` (default)
- PLATESOLVE2_PATH or config `plate_solve.platesolve2_path`: path to PlateSolve2 executable

Example Config Snippets

Windows (ASCOM + PlateSolve2)
```yaml
camera:
  camera_type: "ascom"
  ascom:
    driver_id: "ASCOM.Camera.DriverID"
    exposure_time: 10.0
    gain: 100.0
    binning: 1

mount:
  driver_id: "ASCOM.Telescope.DriverID"
  slewing_detection:
    enabled: true
    check_before_capture: true
    wait_for_completion: false
    wait_timeout: 300.0
    check_interval: 1.0

plate_solve:
  default_solver: platesolve2
  auto_solve: true
  min_solve_interval: 30
  platesolve2_path: "C:/Program Files/PlateSolve2/PlateSolve2.exe"
```

Alpaca (Cross‑platform) + Optional Alternative Solver
```yaml
camera:
  camera_type: "alpaca"
  alpaca:
    host: "localhost"
    port: 11111
    device_id: 0
    exposure_time: 10.0
    gain: 100.0

mount:
  alpaca:
    host: "localhost"
    port: 11111
    device_id: 0
  slewing_detection:
    enabled: true

plate_solve:
  default_solver: platesolve2  # or a stub/alternative if configured
  auto_solve: true
  min_solve_interval: 30
  # platesolve2_path may be omitted on non‑Windows; tests will skip if unavailable
```

Running Tests
```bash
# Unit tests (default)
pytest -q -m "not integration"

# Integration tests (no hardware by default)
pytest -q -m integration

# Hardware-tagged integration tests only
pytest -q -m "integration and hardware"

# Enable image regression tests (requires baselines)
OST_ENABLE_IMAGE_REGRESSIONS=1 pytest -q -k overlay_image_regression_unit
```

Windows (ASCOM / PlateSolve2)
1) Install ASCOM Platform and drivers for your mount/camera
2) Install PlateSolve2 and set its path in your config or `PLATESOLVE2_PATH`
3) Set `OST_CAMERA_CONNECTED=1` if a real camera is available
4) Run: `pytest -q -m integration`

Linux/macOS (Alpaca / Alternative solver)
- Use Alpaca endpoints or a stubbed solver; some tests will skip when dependencies are missing
- Ensure OpenCV, Astropy, PIL, and optional astroquery are installed if needed by tests

CI Behavior
- The main CI runs unit tests and uploads coverage
- The Integration CI runs `-m integration` with `continue-on-error: true`
- A separate Hardware CI job runs `-m "integration and hardware"` (also non-blocking)

Tips
- If a test requires external tools (ASCOM/PlateSolve2) and they are not available, it should skip instead of failing
- For debugging, run individual tests with `-k name_of_test` and increase logging in your config
