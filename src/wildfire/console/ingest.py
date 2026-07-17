"""Mission-folder ingestion: point the console at a source folder (SD-card dump)
and it reads ONLY the drone images, sorts them by capture time, and groups them
into flight sessions the operator can browse and detect.

A mission folder mixes images with telemetry sidecars (.SRT/.DAT/.LRF/.GPX...).
Those are never opened — GPS and capture time come from each image's EXIF — they
are only counted so the UI can say "N other files ignored".

Grouping: images are bucketed by calendar day, then split into sessions whenever
the gap between consecutive shots exceeds `gap_minutes` (a new battery/flight).
Each session is labeled day + time-of-day: "Jul 08, 2026 · Morning · 06:24–06:58".
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..gps import extract_timestamp
from ..imageio_utils import SUPPORTED_EXTS

# (start hour incl., end hour excl., label); anything else is Night.
TIME_OF_DAY = [(5, 11, "Morning"), (11, 14, "Midday"), (14, 18, "Afternoon"), (18, 23, "Evening")]
SESSION_GAP_MINUTES = 45  # a longer pause between shots starts a new session
MAX_SESSION_IMAGES = 100  # bigger continuous shoots are split into parts —
# ~100 images is one review sitting; a 1500-image flight becomes 15 parts


def time_of_day(dt: datetime) -> str:
    for lo, hi, label in TIME_OF_DAY:
        if lo <= dt.hour < hi:
            return label
    return "Night"


def image_time(path: Path) -> datetime:
    """Capture time: EXIF DateTimeOriginal, falling back to the file mtime."""
    ts = extract_timestamp(path)
    if ts:
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
            try:
                return datetime.strptime(str(ts).strip(), fmt)
            except ValueError:
                continue
    return datetime.fromtimestamp(path.stat().st_mtime)


def folder_signature(folder: Path) -> tuple:
    """Cheap change signature (file count + newest mtime) to reuse scan results."""
    count, newest = 0, 0.0
    try:
        for root, _dirs, files in os.walk(folder):
            for f in files:
                count += 1
                try:
                    newest = max(newest, (Path(root) / f).stat().st_mtime)
                except OSError:
                    pass
    except OSError:
        pass
    return (count, newest)


def scan_source(folder: str | Path) -> dict:
    """Walk the folder; read images only. Returns images (time-sorted) + ignored count."""
    folder = Path(folder)
    images: list[dict] = []
    ignored = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            p = Path(root) / name
            if p.suffix.lower() in SUPPORTED_EXTS:
                images.append({"path": str(p), "name": name, "time": image_time(p)})
            else:
                ignored += 1
    images.sort(key=lambda im: im["time"])
    return {"folder": str(folder), "images": images, "ignored": ignored}


def group_sessions(images: list[dict], gap_minutes: int = SESSION_GAP_MINUTES,
                   max_images: int = MAX_SESSION_IMAGES) -> list[dict]:
    """Time-sorted images -> sessions (new day / >gap), big shoots split in parts."""
    sessions: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        if not current:
            return
        chunks = [current[i:i + max_images] for i in range(0, len(current), max_images)]
        for n, chunk in enumerate(chunks, start=1):
            start, end = chunk[0]["time"], chunk[-1]["time"]
            label = time_of_day(current[0]["time"])
            if len(chunks) > 1:
                label += f" · part {n}/{len(chunks)}"
            sessions.append({
                "id": start.strftime("%Y%m%d_%H%M%S"),
                "day": start.strftime("%b %d, %Y"),
                "day_key": start.strftime("%Y-%m-%d"),
                "part": label,
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "count": len(chunk),
                "paths": [im["path"] for im in chunk],
                "names": [im["name"] for im in chunk],
            })
        current.clear()

    prev: Optional[datetime] = None
    for im in images:
        t = im["time"]
        if prev is not None and (t.date() != prev.date()
                                 or (t - prev).total_seconds() > gap_minutes * 60):
            flush()
        current.append(im)
        prev = t
    flush()
    sessions.sort(key=lambda s: s["id"], reverse=True)  # newest first
    return sessions


def make_thumb(image_path: str | Path, cache_dir: Path, max_px: int = 360) -> Optional[Path]:
    """Small cached JPEG preview of an image (cache key = path + mtime)."""
    import cv2

    from ..imageio_utils import load_rgb_uint8

    image_path = Path(image_path)
    try:
        key = hashlib.sha1(
            f"{image_path}|{image_path.stat().st_mtime}|{max_px}".encode()
        ).hexdigest()[:20]
    except OSError:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{key}.jpg"
    if dest.exists():
        return dest
    try:
        rgb = load_rgb_uint8(image_path)
        h, w = rgb.shape[:2]
        scale = max(h, w) / float(max_px)
        if scale > 1:
            rgb = cv2.resize(rgb, (int(w / scale), int(h / scale)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(dest), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])
        return dest
    except Exception:
        return None
