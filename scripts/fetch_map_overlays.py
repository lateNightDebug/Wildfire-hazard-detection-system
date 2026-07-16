"""CLI: download roads / rivers / lakes as GeoJSON for the offline map (ONLINE tool).

    python -m scripts.fetch_map_overlays --bbox 50.95 -115.55 51.25 -115.25

Queries OpenStreetMap's Overpass API for highways (classified), waterways and
water bodies inside the bbox and writes map/overlays.geojson, which the
console map renders on top of the satellite tiles — fully offline afterwards.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:90];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|residential|track|path"]({s},{w},{n},{e});
  way["waterway"~"river|stream|canal"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
);
out geom;
"""


def to_geojson(elements: list[dict]) -> dict:
    feats = []
    for el in elements:
        geom = el.get("geometry")
        if not geom or len(geom) < 2:
            continue
        coords = [[p["lon"], p["lat"]] for p in geom]
        tags = el.get("tags", {})
        closed = coords[0] == coords[-1] and (tags.get("natural") == "water")
        feats.append({
            "type": "Feature",
            "properties": {"highway": tags.get("highway"), "waterway": tags.get("waterway"),
                           "natural": tags.get("natural"), "name": tags.get("name")},
            "geometry": {"type": "Polygon" if closed else "LineString",
                         "coordinates": [coords] if closed else coords},
        })
    return {"type": "FeatureCollection", "features": feats}


def main() -> int:
    ap = argparse.ArgumentParser(description="Download OSM roads/water overlays as GeoJSON.")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("LAT_MIN", "LON_MIN", "LAT_MAX", "LON_MAX"))
    ap.add_argument("--out", default="map/overlays.geojson")
    args = ap.parse_args()

    s, w, n, e = args.bbox
    body = urllib.parse.urlencode({"data": QUERY.format(s=s, w=w, n=n, e=e)}).encode()
    req = urllib.request.Request(OVERPASS, data=body,
                                 headers={"User-Agent": "wildfire-capstone-offline-map/1.0"})
    print("querying Overpass (this can take a minute)...")
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))

    gj = to_geojson(data.get("elements", []))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gj), encoding="utf-8")
    print(f"{len(gj['features'])} features -> {out.resolve()} "
          "(roads/rivers/lakes render on the console map, offline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
