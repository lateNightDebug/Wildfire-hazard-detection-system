"""SAHI (Slicing Aided Hyper Inference) + Ultralytics YOLO11 detector.

Wraps an ultralytics .pt (e.g. the fire/smoke model) behind the common detector
interface used by the pipeline: a `.predict(image) -> list[Detection]` method.
The DeepForest dead-tree detector implements the same interface separately.

Verified against sahi 0.12.1: model_type="ultralytics", the get_sliced_prediction
signature, and result.object_prediction_list parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np

from .config import Settings
from .device import pick_device
from .models import display_for
from .types import Detection

ImageInput = Union[str, Path, np.ndarray]


class SahiYoloDetector:
    """SAHI sliced inference over an Ultralytics YOLO11 .pt model."""

    def __init__(self, model_path: str | Path, settings: Settings, device: str | None = None):
        from sahi import AutoDetectionModel

        self.name = Path(model_path).stem
        self.settings = settings
        self.model = AutoDetectionModel.from_pretrained(
            model_type="ultralytics",
            model_path=str(model_path),
            confidence_threshold=settings.conf_threshold,
            device=device or pick_device(),
        )

    def predict(self, image: ImageInput) -> list[Detection]:
        from sahi.predict import get_sliced_prediction

        img_arg: ImageInput = str(image) if isinstance(image, (str, Path)) else image
        s = self.settings
        result = get_sliced_prediction(
            image=img_arg,
            detection_model=self.model,
            slice_height=s.slice_size,
            slice_width=s.slice_size,
            overlap_height_ratio=s.overlap_ratio,
            overlap_width_ratio=s.overlap_ratio,
            perform_standard_pred=s.perform_standard_pred,
            postprocess_type="GREEDYNMM",
            postprocess_match_metric="IOS",
            postprocess_match_threshold=0.5,
            batch_size=s.batch_size,
            verbose=0,
        )
        detections: list[Detection] = []
        for pred in result.object_prediction_list:
            minx, miny, maxx, maxy = pred.bbox.to_xyxy()
            name = pred.category.name
            detections.append(
                Detection(
                    cls_name=str(name),
                    display=display_for(name),
                    score=float(pred.score.value),
                    xyxy=(float(minx), float(miny), float(maxx), float(maxy)),
                )
            )
        return detections


def build_yolo_detectors(model_paths: list, settings: Settings, device: str | None = None) -> list:
    """Build one SahiYoloDetector per .pt path."""
    dev = device or pick_device()
    return [SahiYoloDetector(p, settings, dev) for p in model_paths]
