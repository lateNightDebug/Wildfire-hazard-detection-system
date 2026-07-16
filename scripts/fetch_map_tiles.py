"""CLI: pre-download offline satellite tiles for the console map (ONLINE tool).

Run this once in the office for your operating area; the field laptop then has
a real zoomable satellite map with zero network use.

    python -m scripts.fetch_map_tiles --bbox 50.95 -115.55 51.25 -115.25 --zoom 10 16

Tiles come from Esri "World Imagery" (their tile service permits export for
offline/disconnected use, unlike Google/Bing whose ToS forbid tile caching).
Saved as map_tiles/{z}/{x}/{y}.jpg + attribution.txt. Existing tiles are
skipped, so re-running resumes an interrupted download.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TILE_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ATTRIBUTION = ("Imagery © Esri — Source: Esri, Maxar, Earthstar Geographics, "
               "and the GIS User Community")


def deg2num(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def main() -> int:
    ap = argparse.ArgumentParser(description="Download offline map tiles (Esri World Imagery).")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("LAT_MIN", "LON_MIN", "LAT_MAX", "LON_MAX"))
    ap.add_argument("--zoom", nargs=2, type=int, default=[10, 16], metavar=("MIN", "MAX"))
    ap.add_argument("--out", default="map_tiles")
    ap.add_argument("--delay", type=float, default=0.1, help="seconds between requests")
    args = ap.parse_args()

    lat_min, lon_min, lat_max, lon_max = args.bbox
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "attribution.txt").write_text(ATTRIBUTION, encoding="utf-8")

    total = skipped = fetched = failed = 0
    for z in range(args.zoom[0], args.zoom[1] + 1):
        x0, y1 = deg2num(lat_min, lon_min, z)  # note: y grows southward
        x1, y0 = deg2num(lat_max, lon_max, z)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                total += 1
                dest = out / str(z) / str(x) / f"{y}.jpg"
                if dest.exists():
                    skipped += 1
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    req = urllib.request.Request(
                        TILE_URL.format(z=z, y=y, x=x),
                        headers={"User-Agent": "wildfire-capstone-offline-map/1.0"})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        dest.write_bytes(r.read())
                    fetched += 1
                    time.sleep(args.delay)
                except Exception as e:
                    failed += 1
                    print(f"  failed z{z} {x}/{y}: {e}")
        print(f"zoom {z}: done (total so far {total}, fetched {fetched}, skipped {skipped})")

    print(f"\n{fetched} new tiles, {skipped} already cached, {failed} failed -> {out.resolve()}")
    print("The console map switches to real satellite tiles automatically.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
