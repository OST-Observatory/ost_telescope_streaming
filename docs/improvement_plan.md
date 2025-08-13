# Codebase Improvement Plan

This document summarizes potential improvements identified during the linting/type-checking cleanup.

## Linting and Configuration
- Modernize Ruff configuration
  - Move deprecated keys to new sections:
    - `[tool.ruff]` -> `[tool.ruff.lint]`
    - `[tool.ruff.isort]` -> `[tool.ruff.lint.isort]`
  - Keep line-length at 100 for consistency.

## Type Checking (Mypy)
- Incrementally strengthen checks
  - Enable `check_untyped_defs` module-by-module for core areas (e.g., `code/platesolve`, `code/capture`).
  - Replace global `disable_error_code = ["import-untyped"]` with targeted per-file ignores if/when needed.
- Introduce stronger typing in frequently used helpers (e.g., `Status[T]` generics, `unwrap_status`).

## Configuration Modeling
- Add data models for configuration (e.g., via `pydantic` or `attrs`)
  - Define models for camera, telescope, platesolve, cooling.
  - Validate required fields and normalize units at boundaries (temperatures in °C, angles in degrees, lengths in mm).
  - Centralize config access to reduce repeated dictionary lookups.

## Status System Consolidation
- Standardize on a single `Status[T]` with consistent `data` and `details` structure.
- Provide helper functions to:
  - Build status objects with common metadata.
  - Avoid nested `Status` wrapping/unwrapping patterns.

## Logging Improvements
- Adopt structured logging for key workflows
  - Add contextual fields (e.g., capture ID, device ID) using `extra` or JSON logging.
  - Ensure consistent log levels and parameterized messages.
- Add concise, high-signal logs for hot loops; keep verbose dumps behind `DEBUG`.

## Resource and Lifecycle Management
- Wrap camera and solver lifecycles with context managers
  - Connect on enter; flush/stop/disconnect on exit.
- Threading
  - Ensure threads are named, joined with timeouts, and errors are surfaced.
  - Provide graceful shutdown hooks for long-running tasks.

## Test Suite Enhancements
- Replace `print` with assertions and `caplog`/`capsys` where feasible.
- Parametrize repetitive tests; use fixtures for common setup.
- Avoid `sys.exit(1)` in tests in favor of assertions or pytest markers.
- Replace hardcoded platform-specific paths with fixtures and `pytest.mark.skipif` when needed.

## CLI and Developer UX
- Convert runner scripts to proper console entry points.
- Centralize common CLI options and logging setup.
- Add short developer guide:
  - Environment setup, pre-commit hooks, how to run tests, and troubleshooting notes.

## Performance and Robustness
- Cache repeated config lookups in hot paths.
- Add retries/backoff for flaky external IO (plate solving, device API calls).
- Minimize repeated string formatting in tight loops; gate expensive logs behind `DEBUG`.

## Documentation
- Small architecture overview of the capture → process → platesolve → overlay pipeline.
- Cooling workflow diagram and expected device behaviors/limitations.
