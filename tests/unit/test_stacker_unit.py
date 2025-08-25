import os
from pathlib import Path

import numpy as np
from processing.stacker import FrameStacker


def test_median_stacking_basic():
    s = FrameStacker(output_dir=Path("unused"), method="median", sigma_clip_enabled=False)
    a = np.full((10, 12), 10, dtype=np.uint8)
    b = np.full((10, 12), 20, dtype=np.uint8)
    c = np.full((10, 12), 30, dtype=np.uint8)
    s.add_frame(a)
    s.add_frame(b)
    s.add_frame(c)
    snap = s.get_snapshot()
    assert snap is not None
    assert snap.image_uint8 is not None
    # median of [10,20,30] is 20
    assert snap.image_uint8.shape == (10, 12)
    assert int(np.median(snap.image_uint8)) == 20


def test_mean_stacking_basic():
    s = FrameStacker(output_dir=Path("unused"), method="mean", sigma_clip_enabled=False)
    a = np.full((6, 8), 10, dtype=np.uint8)
    b = np.full((6, 8), 20, dtype=np.uint8)
    s.add_frame(a)
    s.add_frame(b)
    snap = s.get_snapshot()
    assert snap is not None
    # mean of [10,20] is 15
    assert int(np.median(snap.image_uint8)) == 15


def test_sigma_clipping_reduces_outlier():
    s = FrameStacker(output_dir=Path("unused"), method="median", sigma_clip_enabled=True, sigma=2.0)
    base = np.full((5, 5), 100, dtype=np.uint8)
    outlier = np.full((5, 5), 255, dtype=np.uint8)
    s.add_frame(base)
    s.add_frame(base)
    s.add_frame(outlier)
    snap = s.get_snapshot()
    assert snap is not None
    # With sigma clipping, the outlier should be largely rejected; median ~100
    assert int(np.median(snap.image_uint8)) == 100


def test_write_snapshot_creates_files(tmp_path: Path):
    s = FrameStacker(output_dir=tmp_path, method="median", sigma_clip_enabled=False)
    a = np.full((4, 4), 42, dtype=np.uint8)
    s.add_frame(a)
    snap = s.write_snapshot("stack_test", write_png=True, write_fits=True)
    assert snap is not None
    if snap.output_path_png:
        assert os.path.exists(snap.output_path_png)
    # FITS depends on astropy availability; tolerate missing
    if snap.output_path_fits:
        assert os.path.exists(snap.output_path_fits)
