"""Batch orchestration for Layer 1: image -> detections -> annotated/grid-map -> ImageResult.

Runs every available detector (dead-tree primary + fire/smoke secondary) on each
image and merges their detections. Reports progress via a callback so both `tqdm`
and `gr.Progress` work. No risk classification — detections are flagged with the
image's GPS location.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

import cv2
import numpy as np

from .annotate import draw_boxes, grid_density_map
from .config import Settings
from .device import device_label
from .gps import extract_altitude, extract_timestamp, get_location
from .imageio_utils import PASSTHROUGH_EXTS, load_rgb_uint8
from .risk import batch_stats
from .types import BatchResult, Detection, ImageResult

# progress(current, total, name)
ProgressFn = Optional[Callable[[int, int, str], None]]

JPEG_QUALITY = 88


def _detection_source(path: Path, rgb: np.ndarray, cache_dir: Path) -> str:
    """Path to feed SAHI: original for common formats, else a normalized PNG."""
    if path.suffix.lower() in PASSTHROUGH_EXTS:
        return str(path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{path.stem}_det.png"
    cv2.imwrite(str(out), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return str(out)


def _save_jpg(path: Path, bgr: np.ndarray) -> str:
    cv2.imwrite(str(path), bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return str(path)


def _run_detectors(detectors: Sequence, image_src: str) -> list[Detection]:
    """Run every detector on the image and concatenate detections."""
    merged: list[Detection] = []
    for det in detectors:
        merged.extend(det.predict(image_src))
    return merged


def process_image(
    path: str | Path,
    detectors: Sequence,
    settings: Settings,
    out_dir: Path,
) -> ImageResult:
    """Process a single image end-to-end into an ImageResult (never raises)."""
    path = Path(path)
    name = path.name
    try:
        rgb = load_rgb_uint8(path)
        H, W = rgb.shape[:2]
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        det_src = _detection_source(path, rgb, out_dir / "_cache")
        detections = _run_detectors(detectors, det_src)

        # One subfolder per artifact kind — a 200-image flight would otherwise
        # dump 600 mixed files (original/annotated/gridmap) into the run root.
        stem = path.stem
        for sub in ("originals", "annotated", "gridmaps"):
            (out_dir / sub).mkdir(parents=True, exist_ok=True)
        orig_path = _save_jpg(out_dir / "originals" / f"{stem}.jpg", bgr)
        annotated_path = _save_jpg(out_dir / "annotated" / f"{stem}.jpg",
                                   draw_boxes(bgr, detections))
        density_path = _save_jpg(
            out_dir / "gridmaps" / f"{stem}.jpg",
            grid_density_map(bgr, detections, rows=settings.grid_rows, cols=settings.grid_cols),
        )

        return ImageResult(
            path=str(path), name=name, width=W, height=H,
            detections=detections,
            gps=get_location(path), altitude=extract_altitude(path), timestamp=extract_timestamp(path),
            flagged=bool(detections),
            orig_display_path=orig_path, annotated_path=annotated_path, density_path=density_path,
        )
    except Exception as e:  # one bad image must not sink the batch
        return ImageResult(
            path=str(path), name=name, width=0, height=0,
            flagged=False, error=f"{type(e).__name__}: {e}",
        )


def run_batch(
    paths: Sequence[str | Path],
    detectors: Sequence,
    settings: Settings,
    progress: ProgressFn = None,
    out_dir: str | Path | None = None,
    batch_label: str = "",
) -> BatchResult:
    """Process a batch of images and return a BatchResult with aggregate stats."""
    out = Path(out_dir) if out_dir else settings.output_path
    out.mkdir(parents=True, exist_ok=True)

    total = len(paths)
    results: list[ImageResult] = []
    for i, p in enumerate(paths):
        res = process_image(p, detectors, settings, out)
        results.append(res)
        if progress:
            progress(i + 1, total, res.name)

    batch_info = {
        "batch_label": batch_label or out.name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device": device_label(),
        "model_count": len(detectors),
        "conf_threshold": settings.conf_threshold,
        "slice_size": settings.slice_size,
        "image_count": total,
        "output_dir": str(out),
    }
    return BatchResult(images=results, stats=batch_stats(results), batch_info=batch_info)
