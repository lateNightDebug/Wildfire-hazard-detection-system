"""Assemble the heterogeneous detector list the pipeline runs per image.

Combines:
  - SAHI+YOLO detectors for every .pt in models/ (fire/smoke, plus any you drop in)
  - the DeepForest dead-tree detector, if an enabled model source uses
    backend="deepforest" and the deepforest package is installed.

The pipeline calls each detector's `.predict(image) -> list[Detection]` and merges.
"""

from __future__ import annotations

from typing import Callable, Optional

from .config import Settings
from .detect import build_yolo_detectors
from .device import pick_device
from .models import available_model_files, ensure_yolo_sources

ProgressFn = Optional[Callable[[str], None]]


def _wants_deepforest(settings: Settings) -> bool:
    return any(s.enabled and s.backend == "deepforest" for s in settings.model_sources)


def build_detectors(settings: Settings, log: ProgressFn = None) -> list:
    """Build all available detectors (YOLO .pt models + DeepForest dead-tree).

    Raises RuntimeError if no detector can be built at all.
    """
    device = pick_device()

    # 1) YOLO detectors (download configured .pt sources first).
    yolo_paths = ensure_yolo_sources(settings, log)
    detectors: list = build_yolo_detectors(yolo_paths, settings, device)
    if log:
        log(f"YOLO detectors: {[d.name for d in detectors]}")

    # 2) DeepForest dead-tree detector (loads its own weights).
    if _wants_deepforest(settings):
        from .deepforest_detector import DeepForestDeadTreeDetector, deepforest_available

        if deepforest_available():
            detectors.append(DeepForestDeadTreeDetector(settings, device, log))
        elif log:
            log("[deadtree] deepforest not installed; dead-tree detection disabled "
                "(pip install deepforest).")

    if not detectors:
        raise RuntimeError(
            "No detectors available. Install deepforest for dead-tree detection, "
            f"or place/download a YOLO .pt in {settings.models_path}."
        )
    return detectors
