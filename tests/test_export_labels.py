"""Tests for the Custom Vision dataset export (labels.json -> tiles + regions)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from src.wildfire.cv_export import (
    clip_box_to_window, export_dataset, load_label_records, region_from_xyxy,
)


def _make_labels(tmp_path, xyxy=(20, 10, 60, 50), cls="Dead Tree"):
    img = np.full((100, 200, 3), 128, np.uint8)  # H=100, W=200
    p = tmp_path / "scene.jpg"
    Image.fromarray(img).save(p)
    lp = tmp_path / "labels.json"
    lp.write_text(json.dumps(
        {"labels": [{"image": str(p), "xyxy": list(xyxy), "class": cls}]}
    ), encoding="utf-8")
    return lp


def _manifest(out_dir):
    return json.loads((out_dir / "annotations.json").read_text(encoding="utf-8"))


def test_load_label_records_skips_unconfirmed(tmp_path):
    lp = tmp_path / "labels.json"
    lp.write_text(json.dumps({"labels": [
        {"image": "a.jpg", "xyxy": [0, 0, 10, 10], "proposed_class": "Dead Tree", "confirmed": True},
        {"image": "a.jpg", "xyxy": [5, 5, 20, 20], "proposed_class": "Flame", "confirmed": False},
        {"image": "a.jpg", "xyxy": [9, 9, 3, 3], "class": "Dead Tree"},  # degenerate box
    ]}), encoding="utf-8")
    grouped = load_label_records(lp)
    assert list(grouped) == ["a.jpg"] and len(grouped["a.jpg"]) == 1
    assert grouped["a.jpg"][0]["tag"] == "Dead Tree"


def test_region_normalization():
    r = region_from_xyxy((20, 10, 60, 50), width=200, height=100, tag="Dead Tree")
    assert r == {"tag": "Dead Tree", "left": 0.1, "top": 0.1, "width": 0.2, "height": 0.4}


def test_clip_box_visibility():
    window = (0, 0, 100, 100)
    assert clip_box_to_window([80, 10, 120, 50], window, min_visibility=0.3) == (80, 10, 100, 50)
    assert clip_box_to_window([80, 10, 120, 50], window, min_visibility=0.6) is None


def test_export_no_tile(tmp_path):
    lp = _make_labels(tmp_path)
    manifest = export_dataset(lp, tmp_path / "out", no_tile=True)
    assert manifest["tags"] == ["Dead Tree"] and manifest["tiling"] is None
    assert len(manifest["images"]) == 1
    im = manifest["images"][0]
    assert (tmp_path / "out" / im["file"]).exists()
    r = im["regions"][0]
    assert (r["left"], r["top"], r["width"], r["height"]) == (0.1, 0.1, 0.2, 0.4)


def test_export_tiles_only_positive_kept(tmp_path):
    lp = _make_labels(tmp_path)  # box (20,10,60,50) lives in the left 100px tile
    manifest = export_dataset(lp, tmp_path / "out", tile=100, overlap=0.0)
    assert len(manifest["images"]) == 1  # right tile is empty -> dropped
    im = manifest["images"][0]
    assert im["width"] == 100 and im["height"] == 100
    r = im["regions"][0]
    assert (r["left"], r["top"], r["width"], r["height"]) == (0.2, 0.1, 0.4, 0.4)


def test_export_tiles_with_negatives(tmp_path):
    lp = _make_labels(tmp_path)
    manifest = export_dataset(lp, tmp_path / "out", tile=100, overlap=0.0,
                              negatives_per_image=1)
    assert len(manifest["images"]) == 2
    negs = [im for im in manifest["images"] if not im["regions"]]
    assert len(negs) == 1 and negs[0]["file"].endswith("_neg.jpg")


def test_export_boundary_box_clipped_into_both_tiles(tmp_path):
    lp = _make_labels(tmp_path, xyxy=(80, 10, 120, 50))  # straddles the tile edge
    manifest = export_dataset(lp, tmp_path / "out", tile=100, overlap=0.0,
                              min_visibility=0.3)
    assert len(manifest["images"]) == 2
    lefts = sorted(im["regions"][0]["left"] for im in manifest["images"])
    assert lefts == [pytest.approx(0.0), pytest.approx(0.8)]


def test_export_missing_source_image_skipped(tmp_path):
    lp = tmp_path / "labels.json"
    lp.write_text(json.dumps({"labels": [
        {"image": str(tmp_path / "gone.jpg"), "xyxy": [0, 0, 10, 10], "class": "Dead Tree"},
    ]}), encoding="utf-8")
    manifest = export_dataset(lp, tmp_path / "out")
    assert manifest["images"] == []
    assert manifest["skipped_source_images"] == [str(tmp_path / "gone.jpg")]
