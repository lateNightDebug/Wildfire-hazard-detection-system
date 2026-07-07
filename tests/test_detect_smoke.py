"""Integration smoke test for the SAHI+YOLO detection path.

Skips automatically when the heavy deps (ultralytics/sahi/torch) or any model
.pt is not present, so the fast unit tests can run on any machine.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("ultralytics")
pytest.importorskip("sahi")

from src.wildfire.config import load_settings  # noqa: E402
from src.wildfire.models import available_model_files  # noqa: E402
from src.wildfire.pipeline import process_image  # noqa: E402


@pytest.fixture(scope="module")
def detectors_and_settings():
    settings = load_settings()
    paths = available_model_files(settings)
    if not paths:
        pytest.skip("No model .pt downloaded (run scripts/download_model.py).")
    from src.wildfire.detect import build_yolo_detectors

    return build_yolo_detectors(paths, settings), settings


def _synthetic_image(path):
    img = np.full((640, 640, 3), 30, dtype=np.uint8)
    img[260:380, 260:380] = (200, 60, 20)  # a warm blob
    Image.fromarray(img).save(path)


def test_pipeline_runs_and_writes_outputs(tmp_path, detectors_and_settings):
    detectors, settings = detectors_and_settings
    img_path = tmp_path / "synthetic.png"
    _synthetic_image(img_path)

    result = process_image(img_path, detectors, settings, out_dir=tmp_path / "out")

    assert result.error is None
    assert isinstance(result.detections, list)  # may be empty on a synthetic image
    assert result.flagged == bool(result.detections)
    # annotated + grid map + original JPGs were written
    assert result.annotated_path and result.density_path and result.orig_display_path
