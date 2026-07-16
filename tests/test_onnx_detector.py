"""Tests for the ONNX detector: tiling, NMS, output parsing, and the full
predict path via an injected fake session (no onnxruntime / model needed)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from src.wildfire.config import ModelSource, Settings
from src.wildfire.onnx_detector import (
    OnnxDetector, iter_tiles, load_labels, nms_xyxy, parse_outputs, resolve_labels_path,
)


class FakeSession:
    """Stands in for an onnxruntime.InferenceSession."""

    def __init__(self, outputs_fn, input_shape=(1, 3, 320, 320)):
        self._outputs_fn = outputs_fn
        self._input = SimpleNamespace(name="image", shape=list(input_shape),
                                      type="tensor(float)")
        self.seen_inputs: list[np.ndarray] = []

    def get_inputs(self):
        return [self._input]

    def run(self, _names, feeds):
        tensor = feeds[self._input.name]
        self.seen_inputs.append(tensor)
        return self._outputs_fn(tensor)


def _cv_outputs(boxes, scores, classes):
    """Build Custom Vision-style outputs: boxes (1,N,4), classes int64, scores float."""
    return [
        np.asarray([boxes], dtype=np.float32),
        np.asarray([classes], dtype=np.int64),
        np.asarray([scores], dtype=np.float32),
    ]


def _settings(**overrides) -> Settings:
    s = Settings(model_sources=[])
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


# ------------------------------------------------------------------ tiling
def test_iter_tiles_covers_drone_frame():
    tiles = iter_tiles(5280, 3956, 1024, 0.2)
    assert all(0 <= x0 < x1 <= 5280 and 0 <= y0 < y1 <= 3956 for x0, y0, x1, y1 in tiles)
    assert min(t[0] for t in tiles) == 0 and max(t[2] for t in tiles) == 5280
    assert min(t[1] for t in tiles) == 0 and max(t[3] for t in tiles) == 3956
    assert all(x1 - x0 == 1024 and y1 - y0 == 1024 for x0, y0, x1, y1 in tiles)
    xs = sorted({t[0] for t in tiles})
    assert all(b - a < 1024 for a, b in zip(xs, xs[1:]))  # overlap -> no gaps


def test_iter_tiles_small_image_single_window():
    assert iter_tiles(300, 200, 1024, 0.2) == [(0, 0, 300, 200)]


# ------------------------------------------------------------------ NMS
def test_nms_suppresses_overlaps():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    keep = nms_xyxy(boxes, scores, iou_thr=0.5)
    assert keep == [0, 2]


# ------------------------------------------------------------------ parsing
def test_parse_customvision_outputs_any_order():
    outputs = _cv_outputs([[0.1, 0.2, 0.3, 0.4]], [0.9], [1])
    for shuffled in (outputs, outputs[::-1]):
        boxes, scores, classes = parse_outputs(shuffled, num_classes=2, input_hw=(320, 320))
        assert boxes.shape == (1, 4)
        assert np.allclose(boxes[0], [0.1, 0.2, 0.3, 0.4])
        assert scores[0] == pytest.approx(0.9) and classes[0] == 1


def test_parse_customvision_pixel_boxes_autonormalized():
    outputs = _cv_outputs([[80, 80, 240, 240]], [0.9], [0])
    boxes, _, _ = parse_outputs(outputs, num_classes=1, input_hw=(320, 320))
    assert np.allclose(boxes[0], [0.25, 0.25, 0.75, 0.75])


def test_parse_yolo_single_output():
    # (1, 4+nc, N) with nc=2: candidates as columns (cx, cy, w, h, c1, c2).
    cands = np.array([[160, 160, 80, 80, 0.9, 0.1],
                      [80, 80, 40, 40, 0.2, 0.7]], dtype=np.float32).T[None]
    boxes, scores, classes = parse_outputs([cands], num_classes=2, input_hw=(320, 320))
    assert np.allclose(boxes[0], [120 / 320, 120 / 320, 200 / 320, 200 / 320])
    assert scores[0] == pytest.approx(0.9) and classes[0] == 0
    assert scores[1] == pytest.approx(0.7) and classes[1] == 1


# ------------------------------------------------------------------ labels
def test_load_and_resolve_labels(tmp_path):
    model = tmp_path / "dead_tree.onnx"
    model.write_bytes(b"fake")
    labels = tmp_path / "dead_tree.labels.txt"
    labels.write_text("dead_tree\nflame\n", encoding="utf-8")
    assert resolve_labels_path(model) == labels
    assert load_labels(labels) == ["dead_tree", "flame"]


# ------------------------------------------------------------------ preprocess
def test_preprocess_normalize_and_channel_order():
    session = FakeSession(lambda t: _cv_outputs([[0, 0, 1, 1]], [0.0], [0]))
    det = OnnxDetector("fake.onnx", _settings(onnx_normalize="0-1"),
                       labels=["dead_tree"], session=session)
    tile = np.zeros((320, 320, 3), np.uint8)
    tile[..., 0] = 255  # pure red
    x = det._preprocess(tile)
    assert x.shape == (1, 3, 320, 320) and x.dtype == np.float32
    assert x.max() == pytest.approx(1.0) and x[0, 0].max() == pytest.approx(1.0)

    det_bgr = OnnxDetector("fake.onnx", _settings(onnx_channel_order="BGR"),
                           labels=["dead_tree"], session=session)
    x = det_bgr._preprocess(tile)
    assert x[0, 2].max() == pytest.approx(255.0) and x[0, 0].max() == 0.0  # red -> last


# ------------------------------------------------------------------ full predict
def test_predict_single_window_maps_to_pixels():
    session = FakeSession(lambda t: _cv_outputs([[0.25, 0.25, 0.75, 0.75]], [0.9], [0]))
    det = OnnxDetector("dead_tree.onnx", _settings(slice_size=1024),
                       labels=["dead_tree"], session=session)
    dets = det.predict(np.zeros((320, 320, 3), np.uint8))
    assert len(dets) == 1
    d = dets[0]
    assert d.display == "Dead Tree" and d.score == pytest.approx(0.9)
    assert d.xyxy == pytest.approx((80.0, 80.0, 240.0, 240.0))


def test_predict_tiled_offsets_and_merge():
    session = FakeSession(lambda t: _cv_outputs([[0.25, 0.25, 0.5, 0.5]], [0.9], [0]))
    settings = _settings(slice_size=320, overlap_ratio=0.0, perform_standard_pred=False)
    det = OnnxDetector("dead_tree.onnx", settings, labels=["dead_tree"], session=session)
    dets = det.predict(np.zeros((320, 640, 3), np.uint8))  # H=320, W=640 -> 2 tiles
    assert len(session.seen_inputs) == 2
    got = sorted(d.xyxy for d in dets)
    assert got[0] == pytest.approx((80.0, 80.0, 160.0, 160.0))
    assert got[1] == pytest.approx((400.0, 80.0, 480.0, 160.0))


def test_predict_below_threshold_returns_nothing():
    session = FakeSession(lambda t: _cv_outputs([[0.25, 0.25, 0.75, 0.75]], [0.1], [0]))
    det = OnnxDetector("dead_tree.onnx", _settings(conf_threshold=0.3),
                       labels=["dead_tree"], session=session)
    assert det.predict(np.zeros((320, 320, 3), np.uint8)) == []


# ------------------------------------------------------------------ registry
def test_build_detectors_skips_missing_onnx_and_unknown_backend(tmp_path):
    from src.wildfire.detectors import build_detectors

    settings = Settings(
        models_dir=str(tmp_path / "models"), output_dir=str(tmp_path / "out"),
        model_sources=[
            ModelSource(key="deadtree_onnx", filename="missing.onnx", backend="onnx"),
            ModelSource(key="weird", filename="x", backend="alien"),
        ],
    )
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="No detectors"):
        build_detectors(settings, log=logs.append)
    assert any("skipped" in m for m in logs)  # onnx-missing and/or unknown backend
    assert any("alien" in m for m in logs)
