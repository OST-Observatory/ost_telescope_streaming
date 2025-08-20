Legacy Tests (Deprecated)

This folder contains legacy or script-style tests that have been superseded by modern pytest unit/integration tests.

- These files are kept for historical context and potential manual reference.
- They are excluded from normal test runs and typical CI.
- Prefer tests under `tests/unit/` and `tests/integration/`.
- Some test utilities live here (e.g. `test_utils.py`) and may be imported by a few integration tests under `tests/integration/`.
