"""Tests for class->display mapping, detection flagging, and batch statistics."""

from __future__ import annotations

from src.wildfire.models import display_for
from src.wildfire.risk import batch_stats, is_flagged
from src.wildfire.types import Detection, ImageResult


def deadtree(score, box=(0, 0, 10, 10)):
    return Detection("dead_tree", "Dead Tree", score, box)


def flame(score, box=(0, 0, 10, 10)):
    return Detection("fire", "Flame", score, box)


def smoke(score, box=(0, 0, 10, 10)):
    return Detection("smoke", "Smoke", score, box)


def test_display_for_maps_known_classes():
    assert display_for("dead_tree") == "Dead Tree"
    assert display_for("standing-dead") == "Dead Tree"
    assert display_for("snag") == "Dead Tree"
    assert display_for("fire") == "Flame"
    assert display_for("Smoke") == "Smoke"
    # unknown class is title-cased, not dropped
    assert display_for("power_line") == "Power Line"


def test_is_flagged():
    assert is_flagged([deadtree(0.5)]) is True
    assert is_flagged([]) is False


def test_batch_stats_counts():
    imgs = [
        ImageResult(path="a", name="a", width=100, height=100,
                    detections=[deadtree(0.6), smoke(0.5)], gps=(53.5, -113.5), flagged=True),
        ImageResult(path="b", name="b", width=100, height=100,
                    detections=[flame(0.7)], gps=None, flagged=True),
        ImageResult(path="c", name="c", width=100, height=100,
                    detections=[], gps=(1.0, 2.0), flagged=False),
    ]
    st = batch_stats(imgs)
    assert st["images_processed"] == 3
    assert st["flagged_images"] == 2
    assert st["total_detections"] == 3
    assert st["images_with_deadtree"] == 1
    assert st["images_with_flame"] == 1
    assert st["images_with_smoke"] == 1
    assert st["images_with_gps"] == 2
    assert st["detections_by_type"] == {"Dead Tree": 1, "Smoke": 1, "Flame": 1}
