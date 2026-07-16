"""Assemble the heterogeneous detector list the pipeline runs per image.

Backend registry: each detector backend ("yolo", "deepforest", "onnx", ...)
registers a builder with @register_backend. `build_detectors` looks at the
enabled `model_sources` in settings and calls the matching builders, so adding
a new kind of detector is: write a class with `.predict(image) -> list[Detection]`,
register a builder here, add a ModelSource entry in config — the pipeline,
review UI and report never change.

Current backends:
  - "yolo":       SAHI+YOLO for every .pt in models/ (fire/smoke + any you drop in).
                  Always runs (it also sweeps loose .pt files with no config entry).
  - "deepforest": DeepForest dead-tree detector (crown + alive/dead classifier).
  - "onnx":       onnxruntime models (Azure Custom Vision export / YOLO export);
                  skipped gracefully until models/<filename> exists.
"""

from __future__ import annotations

from typing import Callable, Optional

from .config import ModelSource, Settings
from .detect import build_yolo_detectors
from .device import pick_device
from .models import ensure_yolo_sources

ProgressFn = Optional[Callable[[str], None]]
BackendBuilder = Callable[[Settings, list[ModelSource], str, ProgressFn], list]

_BACKEND_BUILDERS: dict[str, BackendBuilder] = {}


def register_backend(name: str):
    """Register a builder: (settings, sources, device, log) -> list of detectors."""

    def deco(fn: BackendBuilder) -> BackendBuilder:
        _BACKEND_BUILDERS[name] = fn
        return fn

    return deco


def _say(log: ProgressFn, msg: str) -> None:
    if callable(log):
        log(msg)


# ------------------------------------------------------------------ backends
@register_backend("yolo")
def _build_yolo(settings: Settings, sources: list[ModelSource], device: str, log: ProgressFn) -> list:
    paths = ensure_yolo_sources(settings, log)  # downloads enabled sources, returns all .pt
    detectors = build_yolo_detectors(paths, settings, device)
    if detectors:
        _say(log, f"YOLO detectors: {[d.name for d in detectors]}")
    return detectors


@register_backend("deepforest")
def _build_deepforest(settings: Settings, sources: list[ModelSource], device: str, log: ProgressFn) -> list:
    from .deepforest_detector import DeepForestDeadTreeDetector, deepforest_available

    if not deepforest_available():
        _say(log, "[deadtree] deepforest not installed; dead-tree detection disabled "
                  "(pip install deepforest).")
        return []
    return [DeepForestDeadTreeDetector(settings, device, log)]


@register_backend("onnx")
def _build_onnx(settings: Settings, sources: list[ModelSource], device: str, log: ProgressFn) -> list:
    from .onnx_detector import OnnxDetector, onnxruntime_available

    if not onnxruntime_available():
        _say(log, "[onnx] onnxruntime not installed; ONNX detectors disabled "
                  "(pip install onnxruntime).")
        return []
    detectors: list = []
    for source in sources:
        model_path = settings.model_path_for(source.filename)
        if not model_path.exists():
            _say(log, f"[{source.key}] {model_path.name} not in models/ — skipped "
                      "(drop in your Custom Vision ONNX export to enable it).")
            continue
        labels_path = (
            settings.model_path_for(source.labels_filename) if source.labels_filename else None
        )
        try:
            detectors.append(
                OnnxDetector(model_path, settings, labels_path=labels_path, device=device, log=log)
            )
            _say(log, f"[{source.key}] ONNX detector ready: {model_path.name}")
        except Exception as e:
            _say(log, f"[{source.key}] failed to load {model_path.name}: {e}")
    return detectors


# ------------------------------------------------------------------ assembly
def build_detectors(settings: Settings, log: ProgressFn = None) -> list:
    """Build every available detector from the enabled model sources.

    Raises RuntimeError if no detector can be built at all.
    """
    device = pick_device()

    # "yolo" always runs (it also picks up loose .pt files); other backends run
    # only when an enabled source asks for them. Order: yolo first, then by config.
    backends: list[str] = ["yolo"]
    for source in settings.model_sources:
        if source.enabled and source.backend not in backends:
            backends.append(source.backend)

    detectors: list = []
    for backend in backends:
        builder = _BACKEND_BUILDERS.get(backend)
        if builder is None:
            _say(log, f"[config] unknown backend '{backend}' — skipped.")
            continue
        sources = [s for s in settings.model_sources if s.enabled and s.backend == backend]
        detectors.extend(builder(settings, sources, device, log) or [])

    if not detectors:
        raise RuntimeError(
            "No detectors available. Install deepforest for dead-tree detection, "
            f"or place/download a YOLO .pt or ONNX model in {settings.models_path}."
        )
    return detectors
