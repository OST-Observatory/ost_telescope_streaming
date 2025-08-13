## Refactor Plan: Camera capture, processing, and saving

### Goals
- Unify camera access behind `CameraInterface` (ASCOM, Alpaca, OpenCV) and collapse branching in `video_capture.py`.
- Standardize on returning `Frame` dataclass objects and preserve metadata end-to-end.
- Delegate all saving (FITS and display) to `FrameWriter`; remove saving/rotation code from `VideoCapture`.
- Simplify `VideoProcessor` into small composable steps; improve scheduling and metadata propagation.
- Centralize orientation, scaling, and header enrichment policies.

### Milestones
1) Adapters unification (done)
   - Implement `OpenCVCameraAdapter` to conform to `CameraInterface`.
   - In `video_capture.py`, replace `capture_single_frame_ascom/alpaca` with a single `capture_single_frame()` using the adapter API (start_exposure, wait, get_image_array).
   - Move exposure wait/polling into adapters when possible (add `wait_for_image_ready(timeout)` convenience).

2) Standardize returns and current frame (done)
   - Make `get_current_frame()` always return a `Status` with `data=Frame` (no raw ndarray returns). Keep a temporary compatibility gate if needed.
   - Ensure the capture loop (OpenCV only) stores `Frame` objects with full metadata.

3) Saving separation (done)
   - Inject a `FrameWriter` instance into `VideoCapture` upon construction.
   - Remove `_save_fits_unified`, `_save_image_file`, and `_needs_rotation` from `VideoCapture` and route all saves via `FrameWriter`.
   - Make FITS scaling policy configurable in config (`fits.scaling: auto|none|normalize`), implemented in `FrameWriter`.

4) Config and settings consolidation (done)
   - Create `CameraSettings` dataclass (exposure_time_s, gain, offset, readout_mode, binning, dimensions) and a builder from config+camera state.
   - Attach `CameraSettings` (as dict) into `Frame.metadata` for each capture.

5) Processing loop improvements (done)
   - Long-exposure cameras (ASCOM/Alpaca) use explicit one-shot captures scheduled by `VideoProcessor` (done).
   - Keep OpenCV live-view loop only (done); switch scheduling to `time.monotonic()` and use a `Condition` to wake on new frames.

6) Cooling orchestration (done)
   - Extract a `CoolingService` with a narrow API (init, status, warmup) used by both capture and processor.
   - Ensure SIGINT handling is centralized and non-blocking.

7) Orientation policy (done)
   - Only `FrameWriter` (and optionally a processing policy) applies orientation normalization using `processing.orientation`.
   - Remove ad-hoc transposes from capture; keep calibration orientation safeguards in `CalibrationApplier`.

8) Logging/telemetry (partially done)
   - Added structured logging (capture_id, exposure, gain) and adapter timings; FITS telemetry (CAPTURE, CAPSTRT, CAPEND, SAVEMS) in place.
   - TODO: add full exposure latency and solve timing aggregation in processor logs.

9) Config and docs (done)
10) Module renames and structure (planned)
   - Move calibration helpers into `code/calibration/`:
     - `code/dark_capture.py` → `code/calibration/dark_capture.py`
     - `code/flat_capture.py` → `code/calibration/flat_capture.py`
     - `code/master_frame_creator.py` → `code/calibration/master_frame_builder.py`
   - Group overlay generation under `code/overlay/`:
     - `code/generate_overlay.py` → `code/overlay/generator.py`
   - Group plate solving under `code/platesolve/`:
     - `code/plate_solver.py` → `code/platesolve/solver.py`
     - `code/platesolve2_automated.py` → `code/platesolve/platesolve2.py`
   - Clarify cooling backend naming:
     - `code/cooling_manager.py` → `code/services/cooling_backend.py`
   - Update imports across code, calibration scripts, tests, and docs.

   - `overlay.info_panel.show_cooling_info` documented in README.
   - Orientation/scaling config flags added and documented under frame_processing.

### Risk mitigation
- Keep `return_frame_objects` flag for staged rollout.
- Legacy shims removed; tests and docs updated to use new APIs where applicable.
- Incrementally refactor with tests green between steps.

### Acceptance
- All tests pass; saving paths use `FrameWriter`; `VideoCapture` has no direct FITS/image writes.
- Camera-specific code is limited to adapters; `VideoCapture` is camera-agnostic.
- Processing loop uses `time.monotonic()` + `Condition`; files carry telemetry and structured logs include `capture_id`.


