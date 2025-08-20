Tests Layout

- tests/unit: Fast, isolated unit tests. Default target in CI/local runs.
- tests/integration: Integration/system tests; require `-m integration`.
- tests/legacy: Historical/script-style tests, excluded from standard runs.

Markers
- integration: `pytest -m integration` (or `-m "not integration"` for unit only)
- hardware: Tests that require real hardware

Commands
```bash
# Unit only
pytest -q -m "not integration"

# Integration (optional; may require hardware/tools)
pytest -q -m integration

# Image regression (optional)
OST_ENABLE_IMAGE_REGRESSIONS=1 pytest -q -k overlay_image_regression_unit
```

Notes
- Some integration tests use utilities from `tests/common/test_utils.py`.
- `tests/legacy/**` is not evaluated in CI and may fail without blocking builds.

## Tests README

This repo uses pytest with clear separation of unit and integration tests and a consistent set of utilities for configuration and logging.

### How to run tests

- Unit tests (default):
```bash
pytest -q
```

- Integration tests (hardware/network dependent):
```bash
pytest -q -m integration
```

### Markers

- `integration`: Tests that require hardware, external tools, or long-running IO. Excluded by default via `pytest.ini`.
- `hardware`: Optional marker for tests that specifically need real devices.
- `slow`: Optional marker for longer scenarios.

### Configuration and utilities

- Use `tests/common/test_utils.py` for:
  - `setup_logging(level)`: unified logging
  - `get_test_config(path)`: loads `ConfigManager`
  - `setup_test_environment(args)`: common CLI + config bootstrap for legacy/CLI-style tests

Prefer reading camera settings from `config.get_camera_config()` and processing settings from `config.get_frame_processing_config()`.

### CI

- GitHub Actions runs unit tests (excluding integration) on PRs and pushes.
- A separate workflow runs `-m integration`, and an optional hardware job runs `-m "integration and hardware"`.

### Best practices

- Write pytest-style tests with assertions; avoid returning booleans.
- Use fixtures (e.g., `tmp_path`, `caplog`, `monkeypatch`) and skip tests gracefully when env is missing (e.g., `pytest.skip`).
- Keep hardware-dependent logic behind `@pytest.mark.integration` and/or environment checks.

### Examples

Run unit suite only (default):
```bash
pytest -q
```

Run integration suite:
```bash
pytest -q -m integration
```

Run a single test module:
```bash
pytest tests/unit/test_video_capture_unit.py -q
```
