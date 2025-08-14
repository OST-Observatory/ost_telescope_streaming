# Test Modernization and Coverage Plan

## Objectives
- Make tests fast, deterministic, and informative
- Reduce reliance on prints and manual steps
- Increase unit coverage on core logic; isolate hardware via mocks

## Modernization Checklist (apply broadly)
- Convert scripts to pytest-style tests (functions/classes with assertions)
- Replace `print` output with assertions and `capsys`/`caplog` where needed
- Use fixtures for:
  - Temporary dirs/files (`tmp_path`)
  - Config objects (factory fixture returns validated models)
  - Mock cameras/solvers (pytest-mock/fakes)
- Parametrize tests across camera types (opencv/ascom/alpaca) where logic is shared
- Markers: @pytest.mark.hardware, @pytest.mark.slow, @pytest.mark.integration
- Eliminate sys.exit(1) in tests; use assertions or pytest.skip/xfail
- Use caplog to validate logging instead of asserting on strings in code
- Adopt consistent naming: test_* files and functions, no main() in tests

## Targeted Refactors of Existing Tests
- tests/test_video_capture.py
  - Split into units: connection, cooling, save, cache, filter, debayer
  - Mock camera interface to avoid real hardware
  - Use fixtures for VideoCapture and configs; assert on returned Status
- tests/test_final_integration.py & tests/test_video_system.py
  - Move to tests/integration/; gate with @pytest.mark.integration
  - Remove hardcoded platform paths; use fixtures and skips
- tests/test_alpaca_* and tests/test_filter_wheel.py
  - Isolate to adapter logic via mocks; cover error cases (timeouts, attr errors)
- tests/test_calibration_workflow.py
  - Break into unit tests per step (cooling init, darks, flats, masters)
  - Mock cooling manager and VideoCapture; assert calls and decisions
- tests/test_fits_* and test_save_fits_unified.py
  - Use small synthetic FITS fixtures
  - Snapshot or header-assert tests for enrichment and save pipeline
- tests/test_generate_overlay.py, test_overlay_info.py, test_projection.py
  - Add property/param tests for coordinate conversions (e.g., round-trip within eps)
  - Visual/snapshot tests for overlays using deterministic input (PIL/pytest-regressions)
- tests/test_normalization.py
  - Property tests (Hypothesis) for dtype/shape invariants

## New Tests to Add (missing coverage)
- Status system
  - Unit tests for Status helpers and utils.status_utils.unwrap_status
  - Avoid nested Status pitfalls; validate data/details preservation
- Adapters
  - AscomCameraAdapter, AlpacaCameraAdapter: start/abort exposure, debayer, errors
  - Cooling API surfaces (create_cooling_manager, power/target set)
- Calibration
  - CalibrationApplier: apply dark/flat with small arrays; tolerance matching logic
  - master_frame_builder: directory scanning and naming behaviors (mock filesystem)
- Platesolve
  - PlateSolverFactory selection logic; solver unavailability handling
  - Parsing/normalization of plate-solve results (units, keys)
- Overlay
  - overlay.drawing primitives (title/info/ellipses) with snapshot diffs
  - overlay.generator: object filtering, FOV/PA/flip handling
- Config validation
  - Add tests for config model parsing (once models introduced) and defaults
- CLI
  - Smoke tests for key entry points via pytest’s pytester or subprocess with temp dirs

## Tooling and Infrastructure
- Add coverage reporting (coverage.py) with fail-under threshold (e.g., 70% initially)
- Optional: tox/nox sessions for matrix (py versions, minimal vs full deps)
- CI: separate jobs for unit vs integration (hardware-gated) tests

## Phased Execution
1. Foundation
   - Introduce fixtures, marks, and mock patterns in a couple of files (capture, calibration)
   - Replace prints with assertions/log captures
2. Core Coverage
   - Add unit tests for Status helpers, adapters, calibration applier
   - Property tests for projection/normalization
3. Integration
   - Move heavy tests under tests/integration/ and gate by markers
   - Make them opt-in on CI; document manual run instructions
4. Refinement
   - Add snapshots for overlays, header enrichment; tighten coverage thresholds

## Success Metrics
- All tests runnable via pytest -q with no hardware
- Integration tests runnable via -m integration with hardware or simulator
- Coverage baseline established and tracked in CI
