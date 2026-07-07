"""Integration test for the DeepForest dead-tree detector.

Loads the crown detector + alive/dead classifier (weights cached after first run)
and runs them on DeepForest's bundled NEON forest sample. The sample is a healthy
stand, so the expected result is zero "Dead Tree" detections — the point is to
verify the adapter loads (incl. the CropModel weight repair) and runs without
crashing. Auto-skips if deepforest is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("deepforest")

from src.wildfire.config import load_settings  # noqa: E402
from src.wildfire.deepforest_detector import DeepForestDeadTreeDetector  # noqa: E402


def test_deepforest_dead_tree_runs_on_sample():
    from deepforest import get_data

    settings = load_settings()
    det = DeepForestDeadTreeDetector(settings)
    # The classifier must have loaded (CropModel repair worked).
    assert det._crop is not None

    dets = det.predict(get_data("OSBS_029.png"))
    assert isinstance(dets, list)
    for d in dets:
        assert d.display == "Dead Tree"
        assert 0.0 <= d.score <= 1.0
