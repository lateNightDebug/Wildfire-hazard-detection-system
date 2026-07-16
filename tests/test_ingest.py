"""Tests for mission-folder ingestion: image-only scanning, time grouping,
session labels, and the /api/source endpoints."""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pytest
from PIL import Image

from src.wildfire.console.ingest import (
    group_sessions, image_time, scan_source, time_of_day,
)


def _img(path, when: datetime):
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(path)
    ts = when.timestamp()
    os.utime(path, (ts, ts))  # no EXIF -> image_time falls back to mtime
    return path


def test_time_of_day_buckets():
    assert time_of_day(datetime(2026, 7, 8, 6)) == "Morning"
    assert time_of_day(datetime(2026, 7, 8, 12)) == "Midday"
    assert time_of_day(datetime(2026, 7, 8, 15)) == "Afternoon"
    assert time_of_day(datetime(2026, 7, 8, 20)) == "Evening"
    assert time_of_day(datetime(2026, 7, 8, 2)) == "Night"


def test_scan_source_images_only_and_sorted(tmp_path):
    _img(tmp_path / "b.jpg", datetime(2026, 7, 8, 9, 30))
    _img(tmp_path / "a.jpg", datetime(2026, 7, 8, 9, 0))
    (tmp_path / "flight.SRT").write_text("telemetry", encoding="utf-8")
    (tmp_path / "log.DAT").write_bytes(b"\x00")
    sub = tmp_path / "100MEDIA"
    sub.mkdir()
    _img(sub / "c.jpg", datetime(2026, 7, 8, 10, 0))

    result = scan_source(tmp_path)
    assert [im["name"] for im in result["images"]] == ["a.jpg", "b.jpg", "c.jpg"]
    assert result["ignored"] == 2  # sidecars counted, never opened


def test_group_sessions_by_gap_and_day(tmp_path):
    times = [
        datetime(2026, 7, 8, 6, 24), datetime(2026, 7, 8, 6, 40),   # morning flight
        datetime(2026, 7, 8, 14, 5), datetime(2026, 7, 8, 14, 20),  # afternoon flight (gap > 45m)
        datetime(2026, 7, 9, 9, 0),                                  # next day
    ]
    images = [{"path": f"p{i}.jpg", "name": f"p{i}.jpg", "time": t}
              for i, t in enumerate(times)]
    sessions = group_sessions(images, gap_minutes=45)
    assert len(sessions) == 3
    assert sessions[0]["day"] == "Jul 09, 2026" and sessions[0]["count"] == 1  # newest first
    assert sessions[1]["part"] == "Afternoon" and sessions[1]["count"] == 2
    assert sessions[2]["part"] == "Morning"
    assert sessions[2]["start"] == "06:24" and sessions[2]["end"] == "06:40"
    assert sessions[2]["paths"] == ["p0.jpg", "p1.jpg"]


def test_image_time_falls_back_to_mtime(tmp_path):
    when = datetime(2026, 7, 8, 6, 24, 30)
    p = _img(tmp_path / "x.jpg", when)
    assert abs((image_time(p) - when).total_seconds()) < 2


def test_source_api_roundtrip(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from src.wildfire.config import Settings
    from src.wildfire.console.server import create_app

    mission = tmp_path / "mission"
    mission.mkdir()
    _img(mission / "a.jpg", datetime(2026, 7, 8, 6, 24))
    _img(mission / "b.jpg", datetime(2026, 7, 8, 6, 40))
    (mission / "flight.SRT").write_text("x", encoding="utf-8")

    settings = Settings(output_dir=str(tmp_path / "outputs"),
                        models_dir=str(tmp_path / "models"), model_sources=[])
    client = TestClient(create_app(settings))

    assert client.get("/api/source").json()["sessions"] == []  # nothing configured

    r = client.post("/api/source", json={"folder": str(mission)})
    assert r.status_code == 200
    body = r.json()
    assert body["images"] == 2 and body["ignored"] == 1
    assert len(body["sessions"]) == 1
    s = body["sessions"][0]
    assert s["part"] == "Morning" and s["count"] == 2
    assert "paths" not in s  # absolute paths stay server-side
    assert settings.source_dir == str(mission)  # persisted on the settings object

    # bad folder -> 400; unknown session -> 404
    assert client.post("/api/source", json={"folder": str(tmp_path / "nope")}).status_code == 400
    assert client.post("/api/detect-session", json={"session": "junk"}).status_code == 404

    # review status endpoint answers (value depends on whether 7860 is in use)
    st = client.get("/api/review/status").json()
    assert "running" in st and st["url"].startswith("http://127.0.0.1")
