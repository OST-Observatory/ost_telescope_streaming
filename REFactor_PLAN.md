## Refactor Plan: Camera capture, processing, and saving

### Goals
- Unify camera access behind `CameraInterface` (ASCOM, Alpaca, OpenCV) and collapse branching in `video_capture.py`.
- Standardize on returning `Frame` dataclass objects and preserve metadata end-to-end.
- Delegate all saving (FITS and display) to `FrameWriter`; remove saving/rotation code from `VideoCapture`.
- Simplify `VideoProcessor` into small composable steps; improve scheduling and metadata propagation.
- Centralize orientation, scaling, and header enrichment policies.

### Milestones
1) Adapters unification
   - Implement `OpenCVCameraAdapter` to conform to `CameraInterface`.
   - In `video_capture.py`, replace `capture_single_frame_ascom/alpaca` with a single `capture_single_frame()` using the adapter API (start_exposure, wait, get_image_array).
   - Move exposure wait/polling into adapters when possible (add `wait_for_image_ready(timeout)` convenience).

2) Standardize returns and current frame
   - Make `get_current_frame()` always return a `Status` with `data=Frame` (optionally gated by flag for backward compatibility).
   - Ensure the capture loop (if kept) stores `Frame` objects with full metadata.

3) Saving separation
   - Inject a `FrameWriter` instance into `VideoCapture` upon construction.
   - Remove `_save_fits_unified`, `_save_image_file`, and `_needs_rotation` from `VideoCapture` and route all saves via `FrameWriter`.
   - Make FITS scaling policy configurable in config (`fits.scaling: auto|none|normalize`), implemented in `FrameWriter`.

4) Config and settings consolidation
   - Create `CameraSettings` dataclass (exposure_time_s, gain, offset, readout_mode, binning, dimensions) and a builder from config+camera state.
   - Attach `CameraSettings` (as dict) into `Frame.metadata` for each capture.

5) Processing loop improvements
   - For long-exposure cameras (ASCOM/Alpaca), remove background loop and expose explicit one-shot captures scheduled by `VideoProcessor`.
   - Keep OpenCV live-view loop only.
   - Switch to `time.monotonic()` timers and optionally condition signaling instead of fixed sleeps.

6) Cooling orchestration
   - Extract a `CoolingService` with a narrow API (init, status, warmup) used by both capture and processor.
   - Ensure SIGINT handling is centralized and non-blocking.

7) Orientation policy
   - Only `FrameWriter` (and optionally a processing policy) applies orientation normalization using `processing.orientation`.
   - Remove ad-hoc transposes from capture; keep calibration orientation safeguards in `CalibrationApplier`.

8) Logging/telemetry
   - Add structured logging (capture_id, exposure, gain) and basic metrics (exposure latency, save time, solve time).

### Risk mitigation
- Keep `return_frame_objects` flag for staged rollout.
- Maintain legacy shims (`connect`, `get_camera_info`) for tests.
- Incrementally refactor with tests green between steps.

### Acceptance
- All tests pass; saving paths use `FrameWriter`; `VideoCapture` has no direct FITS/image writes.
- Camera-specific code is limited to adapters; `VideoCapture` is camera-agnostic.


