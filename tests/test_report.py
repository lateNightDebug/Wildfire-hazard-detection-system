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
    assert "Dead Tree" in txt and "51.11" in txt
    assert "HOTSPOTS" in txt and "UNREVIEWED" in txt  # structure + review status
    assert "2025:05:02" in txt  # capture time from EXIF, not just processing date


def test_report_skips_imagery_sections_when_there_are_no_frames(tmp_path):
    """A run synced as results-only (or one whose folders were deleted to free
    disk) has nothing to draw. Detail pages and the gallery must be dropped
    rather than emitted as pages of placeholder dashes."""
    from pypdf import PdfReader

    from src.wildfire.report import has_imagery

    batch = _sample_batch()
    assert has_imagery(batch.images) is False  # paths point nowhere

    out = build_report(batch, tmp_path / "no_imagery.pdf", ai_text="Analysis.")
    pages = PdfReader(str(out)).pages
    text = "\n".join(p.extract_text() or "" for p in pages)

    assert "Image Index" in text          # every image is still accounted for
    assert "DJI_x.JPG" in text
    assert "Batch Summary" in text
    assert "Hazard Image Gallery" not in text
    assert "Image: DJI_x.JPG" not in text  # no per-image detail page
    assert "No imagery is stored for this run" in text


def test_report_keeps_imagery_sections_when_frames_exist(tmp_path):
    """The counterpart: a run WITH frames must still get its detail pages."""
    from PIL import Image as PILImage
    from pypdf import PdfReader

    from src.wildfire.report import has_imagery

    frame = tmp_path / "DJI_x.JPG"
    PILImage.new("RGB", (240, 180), (40, 90, 40)).save(frame)
    batch = _sample_batch()
    batch.images[0].annotated_path = str(frame)
    batch.images[0].orig_display_path = str(frame)
    assert has_imagery(batch.images) is True

    out = build_report(batch, tmp_path / "with_imagery.pdf", ai_text="Analysis.")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(str(out)).pages)
    assert "Image: DJI_x.JPG" in text
    assert "No imagery is stored for this run" not in text


def test_display_copy_same_stem_different_dirs_no_collision(tmp_path):
    from PIL import Image as PILImage

    from src.wildfire.report import _display_copy

    for sub, color in (("annotated", (255, 0, 0)), ("gridmaps", (0, 0, 255))):
        (tmp_path / sub).mkdir()
        PILImage.new("RGB", (20, 20), color).save(tmp_path / sub / "x_confirmed.jpg")
    out_a = _display_copy(str(tmp_path / "annotated" / "x_confirmed.jpg"), tmp_path / "assets")
    out_g = _display_copy(str(tmp_path / "gridmaps" / "x_confirmed.jpg"), tmp_path / "assets")
    assert out_a != out_g  # used to collide -> grid overwrote the annotated copy
    with PILImage.open(out_a) as a, PILImage.open(out_g) as g:
        assert a.getpixel((5, 5))[0] > 200 and g.getpixel((5, 5))[2] > 200


def test_pdf_safe_replaces_non_latin1():
    from src.wildfire.report import _pdf_safe

    assert _pdf_safe("N—S – ‘q’ “w” … →") == "N-S - 'q' \"w\" ... ->"
    # any character outside Latin-1 is replaced, never a black box glyph
    assert "?" in _pdf_safe("\u6c49")  # a CJK character
    assert "?" in _pdf_safe("\u03c0")  # Greek pi


def test_review_badge_reflects_status():
    from src.wildfire.report import _review_badge

    assert "REVIEWED" in str(_review_badge(True)._cellvalues[0][0])
    assert "UNREVIEWED" in str(_review_badge(False)._cellvalues[0][0])


def test_review_badge_reflects_status():
    from src.wildfire.report import _review_badge

    assert "REVIEWED" in str(_review_badge(True)._cellvalues[0][0])
    assert "UNREVIEWED" in str(_review_badge(False)._cellvalues[0][0])


def test_build_report_writes_pdf(tmp_path):
    out = build_report(_sample_batch(), tmp_path / "report.pdf", ai_text="Test analysis paragraph.")
    assert out.exists()
    data = out.read_bytes()
    assert data[:4] == b"%PDF" and len(data) > 1000


def test_build_report_without_ai_text(tmp_path):
    # Missing LLM text must still produce a valid PDF (graceful fallback).
    out = build_report(_sample_batch(), tmp_path / "r2.pdf", ai_text=None)
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
