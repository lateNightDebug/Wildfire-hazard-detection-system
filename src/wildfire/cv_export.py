"""Export human-review labels (a run's labels.json) into an Azure Custom Vision-
ready dataset: images + normalized regions (left/top/width/height, 0..1) — the
exact box format the Custom Vision Training SDK expects.

Why tiles: Custom Vision resizes uploads internally and caps files at ~6MB, so a
full 5280x3956 drone frame would shrink until individual trees are a few pixels.
Training on tiles of the same size the OnnxDetector slices at inference keeps the
train/infer distributions matched. `--no-tile` keeps whole frames (re-encoded
under the size cap) for coarse/large-object experiments.

Output layout (everything under one export dir):
    images/<nnn>_<stem>_x<X>_y<Y>.jpg    positive (and optional negative) tiles
    annotations.json                     manifest consumed by
                                         scripts/upload_to_custom_vision.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from .imageio_utils import load_rgb_uint8
from .onnx_detector import iter_tiles

LogFn = Optional[Callable[[str], None]]

MAX_UPLOAD_BYTES = 6_000_000  # Custom Vision training-image size limit (6MB)


def _say(log: LogFn, msg: str) -> None:
    if callable(log):
        log(msg)


def load_label_records(labels_json: str | Path) -> dict[str, list[dict]]:
    """Read a review labels.json and group its records by image path.

    Accepts both the annotator format ({"image", "xyxy", "class"}) and the older
    accept/reject format ({"image", "xyxy", "proposed_class", "confirmed"}),
    keeping only confirmed boxes in the latter.
    """
    data = json.loads(Path(labels_json).read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for rec in data.get("labels", []):
        if not isinstance(rec, dict) or "image" not in rec or "xyxy" not in rec:
            continue
        if "confirmed" in rec and not rec["confirmed"]:
            continue
        tag = rec.get("class") or rec.get("proposed_class") or "Dead Tree"
        xyxy = [float(v) for v in rec["xyxy"]]
        if len(xyxy) != 4 or xyxy[2] <= xyxy[0] or xyxy[3] <= xyxy[1]:
            continue
        grouped.setdefault(str(rec["image"]), []).append({"xyxy": xyxy, "tag": str(tag)})
    return grouped


def clip_box_to_window(
    xyxy: list[float], window: tuple[int, int, int, int], min_visibility: float
) -> Optional[tuple[float, float, float, float]]:
    """Clip a box to a tile window; return window-local xyxy, or None if the
    visible fraction of the box (intersection/box area) is below `min_visibility`."""
    x1, y1, x2, y2 = xyxy
    wx0, wy0, wx1, wy1 = window
    ix1, iy1 = max(x1, wx0), max(y1, wy0)
    ix2, iy2 = min(x2, wx1), min(y2, wy1)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    box_area = max(1e-9, (x2 - x1) * (y2 - y1))
    if inter / box_area < min_visibility:
        return None
    return (ix1 - wx0, iy1 - wy0, ix2 - wx0, iy2 - wy0)


def region_from_xyxy(xyxy: tuple[float, float, float, float], width: int, height: int, tag: str) -> dict:
    """Window-local pixel xyxy -> Custom Vision normalized region dict."""
    x1, y1, x2, y2 = xyxy
    return {
        "tag": tag,
        "left": round(x1 / width, 6),
        "top": round(y1 / height, 6),
        "width": round((x2 - x1) / width, 6),
        "height": round((y2 - y1) / height, 6),
    }


def _write_jpeg_under(path: Path, rgb: np.ndarray, max_dim: int, max_bytes: int) -> tuple[int, int]:
    """Write RGB as JPEG, downscaling to max_dim and lowering quality to fit
    max_bytes. Returns the (width, height) actually written."""
    h, w = rgb.shape[:2]
    scale = max(h, w) / float(max_dim)
    if scale > 1:
        rgb = cv2.resize(rgb, (int(w / scale), int(h / scale)), interpolation=cv2.INTER_AREA)
        h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for quality in (92, 85, 78, 70, 62):
        ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok and buf.nbytes <= max_bytes:
            path.write_bytes(buf.tobytes())
            return (w, h)
    # Still too big at the lowest quality: halve until it fits.
    while ok and buf.nbytes > max_bytes and max(h, w) > 512:
        h, w = h // 2, w // 2
        bgr = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 62])
    path.write_bytes(buf.tobytes())
    return (w, h)


def export_dataset(
    labels_json: str | Path,
    out_dir: str | Path,
    tile: int = 1024,
    overlap: float = 0.2,
    min_visibility: float = 0.3,
    negatives_per_image: int = 0,
    no_tile: bool = False,
    max_dim: int = 4096,
    max_bytes: int = MAX_UPLOAD_BYTES,
    log: LogFn = None,
) -> dict:
    """Build the Custom Vision dataset from a labels.json; returns the manifest."""
    out_dir = Path(out_dir)
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    grouped = load_label_records(labels_json)
    manifest_images: list[dict] = []
    tags: set[str] = set()
    skipped: list[str] = []

    for idx, (image_path, records) in enumerate(sorted(grouped.items())):
        try:
            rgb = load_rgb_uint8(image_path)
        except Exception as e:
            skipped.append(image_path)
            _say(log, f"[export] cannot read {image_path} ({e}) — skipped.")
            continue
        img_h, img_w = rgb.shape[:2]
        stem = Path(image_path).stem

        if no_tile:
            dest = images_dir / f"{idx:03d}_{stem}.jpg"
            w, h = _write_jpeg_under(dest, rgb, max_dim=max_dim, max_bytes=max_bytes)
            regions = [
                region_from_xyxy(tuple(r["xyxy"]), img_w, img_h, r["tag"]) for r in records
            ]  # normalized coords are scale-invariant, so resizing needs no box math
            for r in records:
                tags.add(r["tag"])
            manifest_images.append(
                {"file": f"images/{dest.name}", "width": w, "height": h, "regions": regions}
            )
            continue

        empty_windows: list[tuple[int, int, int, int]] = []
        for window in iter_tiles(img_w, img_h, tile, overlap):
            wx0, wy0, wx1, wy1 = window
            regions: list[dict] = []
            for r in records:
                clipped = clip_box_to_window(r["xyxy"], window, min_visibility)
                if clipped is not None:
                    regions.append(region_from_xyxy(clipped, wx1 - wx0, wy1 - wy0, r["tag"]))
                    tags.add(r["tag"])
            if not regions:
                empty_windows.append(window)
                continue
            dest = images_dir / f"{idx:03d}_{stem}_x{wx0}_y{wy0}.jpg"
            w, h = _write_jpeg_under(dest, rgb[wy0:wy1, wx0:wx1], max_dim=max_dim, max_bytes=max_bytes)
            manifest_images.append(
                {"file": f"images/{dest.name}", "width": w, "height": h, "regions": regions}
            )

        # Optional pure-negative tiles (deterministic, evenly spaced picks).
        if negatives_per_image > 0 and empty_windows:
            step = max(1, len(empty_windows) // negatives_per_image)
            for wx0, wy0, wx1, wy1 in empty_windows[::step][:negatives_per_image]:
                dest = images_dir / f"{idx:03d}_{stem}_x{wx0}_y{wy0}_neg.jpg"
                w, h = _write_jpeg_under(dest, rgb[wy0:wy1, wx0:wx1], max_dim=max_dim, max_bytes=max_bytes)
                manifest_images.append(
                    {"file": f"images/{dest.name}", "width": w, "height": h, "regions": []}
                )

    manifest = {
        "format": "customvision-regions-v1",
        "source_labels": str(Path(labels_json).resolve()),
        "tiling": None if no_tile else {
            "tile": tile, "overlap": overlap, "min_visibility": min_visibility,
            "negatives_per_image": negatives_per_image,
        },
        "tags": sorted(tags),
        "images": manifest_images,
        "skipped_source_images": skipped,
    }
    (out_dir / "annotations.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    n_regions = sum(len(im["regions"]) for im in manifest_images)
    _say(log, f"[export] {len(manifest_images)} images, {n_regions} regions, "
              f"tags={sorted(tags)} -> {out_dir / 'annotations.json'}")
    return manifest
