"""Tests for the human-review helpers (candidate crops, confirmed rebuild, labels)."""

from __future__ import annotations

import json

import numpy as np
from PIL import Image

from src.wildfire.review import (
    build_confirmed_batch, build_confirmed_from_annotations, detections_from_boxes,
    make_candidate_crops, save_labels, to_annotator,
)
from src.wildfire.types import BatchResult, Detection, ImageResult


def _batch(tmp_path):
    p = tmp_path / "img.jpg"
    Image.fromarray((np.random.rand(300, 300, 3) * 255).astype("uint8")).save(p)
    im = ImageResult(
        path=str(p), name="img.jpg", width=300, height=300,
        detections=[
            Detection("dead_tree", "Dead Tree", 0.9, (20, 20, 70, 110)),
            Detection("dead_tree", "Dead Tree", 0.8, (150, 150, 200, 230)),
        ],
        flagged=True,
    )
    return BatchResult(images=[im], stats={}, batch_info={"batch_label": "t"})


def test_make_candidate_crops(tmp_path):
    crops, meta = make_candidate_crops(_batch(tmp_path))
    assert len(crops) == 2 and len(meta) == 2
    assert meta[0]["det_index"] == 0 and meta[0]["display"] == "Dead Tree"
    assert crops[0].ndim == 3 and crops[0].shape[2] == 3


def test_build_confirmed_batch_filters(tmp_path):
    batch = _batch(tmp_path)
    confirmed = build_confirmed_batch(batch, {(0, 0)}, tmp_path / "out")  # keep only first
    assert confirmed.stats["total_detections"] == 1
    assert len(confirmed.images[0].detections) == 1


def test_save_labels(tmp_path):
    batch = _batch(tmp_path)
    lp = save_labels(batch, {(0, 0)}, tmp_path / "labels.json")
    data = json.loads(lp.read_text(encoding="utf-8"))["labels"]
    assert len(data) == 2
    assert data[0]["confirmed"] is True and data[1]["confirmed"] is False


def test_to_annotator_roundtrip(tmp_path):
    batch = _batch(tmp_path)
    disp, boxes, scale = to_annotator(batch.images[0], disp_max=150)  # force downscale
    assert len(boxes) == 2 and scale > 1.0
    assert disp.shape[1] <= 150 and disp.shape[0] <= 150
    dets = detections_from_boxes(boxes, scale)
    assert len(dets) == 2
    x1, y1, x2, y2 = dets[0].xyxy
    assert abs(x1 - 20) <= scale + 1 and abs(y2 - 110) <= scale + 1  # approx round-trip


def test_build_confirmed_from_annotations_adds_manual(tmp_path):
    batch = _batch(tmp_path)
    _, boxes, scale = to_annotator(batch.images[0])
    # keep 1 proposal + add a manual Flame box
    ann = {0: {"boxes": boxes[:1] + [{"xmin": 10, "ymin": 10, "xmax": 40, "ymax": 60, "label": "Flame"}],
               "scale": scale}}
    cb = build_confirmed_from_annotations(batch, ann, tmp_path / "out")
    assert cb.stats["total_detections"] == 2
    assert "Flame" in cb.stats["detections_by_type"] and "Dead Tree" in cb.stats["detections_by_type"]
