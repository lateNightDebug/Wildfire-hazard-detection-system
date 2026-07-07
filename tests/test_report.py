"""Test the ReportLab PDF builder produces a valid PDF (Layer 2)."""

from __future__ import annotations

import pytest

pytest.importorskip("reportlab")

from src.wildfire.report import build_report, build_summary_text  # noqa: E402
from src.wildfire.types import BatchResult, Detection, ImageResult  # noqa: E402


def _sample_batch() -> BatchResult:
    img = ImageResult(
        path="DJI_x.JPG", name="DJI_x.JPG", width=5280, height=3956,
        detections=[Detection("dead_tree", "Dead Tree", 0.9, (10, 10, 60, 60))],
        gps=(51.11, -115.38), altitude=1357.0, timestamp="2025:05:02 13:10:14",
        flagged=True,
    )
    stats = {
        "images_processed": 1, "flagged_images": 1, "total_detections": 1,
        "mean_detections_per_image": 1.0, "detections_by_type": {"Dead Tree": 1},
        "images_with_deadtree": 1, "images_with_flame": 0, "images_with_smoke": 0,
        "images_with_gps": 1,
    }
    return BatchResult(images=[img], stats=stats,
                       batch_info={"batch_label": "sample", "generated_at": "2026-06-30 00:00:00"})


def test_build_summary_text_mentions_key_facts():
    txt = build_summary_text(_sample_batch())
    assert "Total detections" in txt and "Dead Tree" in txt and "51.11" in txt


def test_build_report_writes_pdf(tmp_path):
    out = build_report(_sample_batch(), tmp_path / "report.pdf", ai_text="Test analysis paragraph.")
    assert out.exists()
    data = out.read_bytes()
    assert data[:4] == b"%PDF" and len(data) > 1000


def test_build_report_without_ai_text(tmp_path):
    # Missing LLM text must still produce a valid PDF (graceful fallback).
    out = build_report(_sample_batch(), tmp_path / "r2.pdf", ai_text=None)
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
