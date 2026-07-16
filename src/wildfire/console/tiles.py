"""Offline map tile management: bbox math + Esri World Imagery downloader.

Used by scripts/fetch_map_tiles.py (CLI) and the console's in-UI "download map
for current area" button. Esri's World Imagery tile service permits offline
export; Google/Bing ToS forbid tile caching.
"""

from __future__ import annotations

import math
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

TILE_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ATTRIBUTION = ("Imagery © Esri — Source: Esri, Maxar, Earthstar Geographics, "
               "and the GIS User Community")
ProgressFn = Optional[Callable[[int, int, int], None]]  # (done, total, failed)


def deg2num(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def tile_list(bbox: tuple[float, float, float, float], zmin: int, zmax: int) -> list[tuple[int, int, int]]:
    lat_min, lon_min, lat_max, lon_max = bbox
    tiles = []
    for z in range(zmin, zmax + 1):
        x0, y1 = deg2num(lat_min, lon_min, z)
        x1, y0 = deg2num(lat_max, lon_max, z)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                tiles.append((z, x, y))
    return tiles


def download_tiles(
    bbox: tuple[float, float, float, float],
    zmin: int, zmax: int, dest: Path,
    progress: ProgressFn = None, delay: float = 0.05,
) -> dict:
    """Fetch missing tiles for bbox into dest/{z}/{x}/{y}.jpg. Returns counts."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "attribution.txt").write_text(ATTRIBUTION, encoding="utf-8")
    todo = tile_list(bbox, zmin, zmax)
    done = fetched = failed = 0
    for z, x, y in todo:
        tile = dest / str(z) / str(x) / f"{y}.jpg"
        if not tile.exists():
            tile.parent.mkdir(parents=True, exist_ok=True)
            try:
                req = urllib.request.Request(
                    TILE_URL.format(z=z, y=y, x=x),
                    headers={"User-Agent": "wildfire-capstone-offline-map/1.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    tile.write_bytes(r.read())
                fetched += 1
                time.sleep(delay)
            except Exception:
                failed += 1
        done += 1
        if progress:
            progress(done, len(todo), failed)
    return {"total": len(todo), "fetched": fetched, "failed": failed}


def bbox_from_points(points: list[tuple[float, float]], pad_deg: float = 0.04) -> Optional[tuple]:
    """Padded bbox around (lat, lon) points — the area worth caching."""
    if not points:
        return None
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return (min(lats) - pad_deg, min(lons) - pad_deg,
            max(lats) + pad_deg, max(lons) + pad_deg)
