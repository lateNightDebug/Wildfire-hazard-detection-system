"""ONNX detector (Azure Custom Vision export / generic YOLO export), implementing
the common `Detector.predict()` interface.

Designed for the Phase-2 custom dead-tree model: train an Object Detection
project on customvision.ai (COMPACT domain), export to ONNX (model.onnx +
labels.txt), drop both files into models/, and this detector runs it fully
offline through onnxruntime.

Pipeline per image:  manual tiling (drone frames are 5280x3956; trees are tiny)
-> preprocess each tile (resize to the model input, normalize, NCHW)
-> onnxruntime session.run -> parse boxes/scores/classes -> merge tiles back
into original-image coordinates -> class-aware NMS -> list[Detection].

Two output layouts are auto-detected in `parse_outputs`:
  - Azure Custom Vision (compact [S1]) export: three outputs — detected_boxes
    (1,N,4) normalized xyxy, detected_classes (1,N) int64, detected_scores (1,N).
  - Ultralytics YOLO ONNX export: one output (1, 4+nc, N) (or transposed, or
    the YOLOv5-style 5+nc with objectness), cx,cy,w,h in input pixels.

Tiling is done manually (not via SAHI) on purpose: SAHI's custom-DetectionModel
API is version-coupled and heavier to test; the tile/merge/NMS math here is a
few pure functions with unit tests. The ORT session is injectable so the whole
predict path is testable offline with a fake session (no real model needed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Sequence, Union

import cv2
import numpy as np

from .config import Settings
from .models import display_for
from .types import Detection

ImageInput = Union[str, Path, np.ndarray]
ProgressFn = Optional[Callable[[str], None]]

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def onnxruntime_available() -> bool:
    """True if the onnxruntime package can be imported."""
    try:
        import onnxruntime  # noqa: F401

        return True
    except Exception:
        return False


def load_labels(path: str | Path) -> list[str]:
    """Read a Custom Vision labels.txt: one class name per line, index = class id."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def resolve_labels_path(model_path: str | Path, labels_path: Optional[str | Path] = None) -> Optional[Path]:
    """Find the labels file for a model: explicit path, <stem>.labels.txt, or labels.txt."""
    if labels_path and Path(labels_path).exists():
        return Path(labels_path)
    model_path = Path(model_path)
    for cand in (model_path.with_suffix(".labels.txt"), model_path.parent / "labels.txt"):
        if cand.exists():
            return cand
    return None


# ------------------------------------------------------------------ tiling
def _starts(size: int, tile: int, stride: int) -> list[int]:
    if size <= tile:
        return [0]
    starts = list(range(0, size - tile + 1, stride))
    if starts[-1] != size - tile:
        starts.append(size - tile)  # final tile flush with the edge
    return starts


def iter_tiles(width: int, height: int, tile: int, overlap: float) -> list[tuple[int, int, int, int]]:
    """Overlapping tile windows (x0, y0, x1, y1) covering the full image.

    Behaves like SAHI slicing: fixed tile size, `overlap` fraction between
    neighbours, last row/column shifted inward so no pixels are missed.
    An image smaller than the tile yields a single full-image window.
    """
    tile = int(tile)
    if tile <= 0 or (width <= tile and height <= tile):
        return [(0, 0, width, height)]
    stride = max(1, int(tile * (1.0 - float(overlap))))
    return [
        (x, y, min(x + tile, width), min(y + tile, height))
        for y in _starts(height, tile, stride)
        for x in _starts(width, tile, stride)
    ]


# ------------------------------------------------------------------ NMS
def nms_xyxy(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
    """Greedy IoU NMS over xyxy boxes; returns kept indices, best score first."""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    scores = np.asarray(scores, dtype=np.float32).reshape(-1)
    if boxes.shape[0] == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = np.argsort(-scores)
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        if rest.size == 0:
            break
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-9)
        order = rest[iou <= iou_thr]
    return keep


def nms_per_class(boxes: np.ndarray, scores: np.ndarray, class_ids: np.ndarray, iou_thr: float) -> list[int]:
    """Class-aware NMS: boxes of different classes never suppress each other."""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    if boxes.shape[0] == 0:
        return []
    # Shift each class into its own coordinate region so one NMS pass suffices.
    span = float(boxes.max()) + 1.0 if boxes.size else 1.0
    offsets = np.asarray(class_ids, dtype=np.float32).reshape(-1, 1) * span
    return nms_xyxy(boxes + offsets, scores, iou_thr)


# ------------------------------------------------------------------ output parsing
def _parse_customvision(outputs: Sequence[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse the Custom Vision 3-output layout by shape/dtype (order-independent)."""
    boxes = scores = classes = None
    floats_1d: list[np.ndarray] = []
    for arr in outputs:
        a = np.asarray(arr)
        if a.ndim >= 2 and a.shape[-1] == 4:
            boxes = a.reshape(-1, 4).astype(np.float32)
        elif np.issubdtype(a.dtype, np.integer):
            classes = a.reshape(-1).astype(np.int64)
        else:
            floats_1d.append(a.reshape(-1).astype(np.float32))
    if boxes is None:
        raise ValueError("Custom Vision output layout: no (N,4) boxes tensor found.")
    # Scores = the float 1-D output; if classes came back float, tell them apart:
    # class ids are integral, scores generally are not.
    if classes is None and len(floats_1d) == 2:
        integral = [np.allclose(f, np.round(f)) for f in floats_1d]
        if integral[0] != integral[1]:
            classes = floats_1d.pop(integral.index(True)).astype(np.int64)
    if not floats_1d:
        raise ValueError("Custom Vision output layout: no scores tensor found.")
    scores = floats_1d[0]
    if classes is None:
        classes = np.zeros(scores.shape[0], dtype=np.int64)
    return boxes, scores, classes


def _parse_yolo(output: np.ndarray, num_classes: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse a single-tensor YOLO ONNX export into (boxes_cxcywh_px, scores, class_ids)."""
    a = np.asarray(output, dtype=np.float32)
    if a.ndim == 3:
        a = a[0]
    if a.ndim != 2:
        raise ValueError(f"Unexpected YOLO output shape {a.shape}.")
    # Orient to (N, C): C is 4+nc (v8/v11) or 5+nc (v5, with objectness).
    channel_counts = {num_classes + 4, num_classes + 5}
    if a.shape[0] in channel_counts and a.shape[1] not in channel_counts:
        a = a.T
    if a.shape[1] == num_classes + 5:
        boxes, cls_scores = a[:, :4], a[:, 4:5] * a[:, 5:]
    elif a.shape[1] == num_classes + 4:
        boxes, cls_scores = a[:, :4], a[:, 4:]
    else:
        raise ValueError(
            f"YOLO output has {a.shape[1]} channels; expected {num_classes + 4} or {num_classes + 5} "
            f"for {num_classes} classes (check labels.txt)."
        )
    class_ids = cls_scores.argmax(axis=1).astype(np.int64)
    scores = cls_scores.max(axis=1).astype(np.float32)
    return boxes, scores, class_ids


def parse_outputs(
    outputs: Sequence[np.ndarray], num_classes: int, input_hw: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Normalize any supported ONNX output layout to (boxes01_xyxy, scores, class_ids).

    Boxes are returned normalized to 0..1 relative to the model input, so the
    caller can scale them straight onto the tile that produced them.
    """
    in_h, in_w = input_hw
    if len(outputs) >= 3:
        boxes, scores, class_ids = _parse_customvision(outputs)
        # Custom Vision boxes are already normalized xyxy; auto-detect pixel-space
        # exports (values clearly beyond 0..1) and normalize them.
        if boxes.size and float(np.abs(boxes).max()) > 2.0:
            boxes = boxes / np.array([in_w, in_h, in_w, in_h], dtype=np.float32)
        return boxes, scores, class_ids

    boxes_cxcywh, scores, class_ids = _parse_yolo(outputs[0], num_classes)
    cx, cy, w, h = boxes_cxcywh.T
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    if boxes.size and float(np.abs(boxes).max()) > 2.0:  # pixel-space (usual for YOLO)
        boxes = boxes / np.array([in_w, in_h, in_w, in_h], dtype=np.float32)
    return boxes, scores, class_ids


# ------------------------------------------------------------------ detector
class OnnxDetector:
    """Tiled onnxruntime inference behind the common `.predict()` interface."""

    def __init__(
        self,
        model_path: str | Path,
        settings: Settings,
        labels: Optional[Sequence[str]] = None,
        labels_path: Optional[str | Path] = None,
        device: str | None = None,
        log: ProgressFn = None,
        session=None,  # injectable for offline tests (any object with get_inputs/run)
    ):
        self.name = Path(model_path).stem + "-onnx"
        self.settings = settings
        self._log = log

        if labels is not None:
            self.labels = list(labels)
        else:
            found = resolve_labels_path(model_path, labels_path)
            self.labels = load_labels(found) if found else []
            if not self.labels:
                self._say(
                    f"[{self.name}] no labels file found (looked for "
                    f"{Path(model_path).stem}.labels.txt / labels.txt); class ids will be used."
                )

        self.session = session if session is not None else self._make_session(model_path, device)

        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.input_hw = self._input_hw(inp.shape)

    def _say(self, msg: str) -> None:
        if callable(self._log):
            self._log(msg)

    def _make_session(self, model_path: str | Path, device: str | None):
        import onnxruntime as ort

        available = ort.get_available_providers()
        preferred = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device and not str(device).startswith("cuda"):
            preferred = ["CPUExecutionProvider"]
        providers = [p for p in preferred if p in available] or available
        self._say(f"[{Path(model_path).stem}] onnxruntime providers: {providers}")
        return ort.InferenceSession(str(model_path), providers=providers)

    def _input_hw(self, shape) -> tuple[int, int]:
        """Model input (H, W) from the ONNX graph; falls back to settings for dynamic axes."""
        h = shape[2] if len(shape) == 4 else None
        w = shape[3] if len(shape) == 4 else None
        fallback = int(self.settings.onnx_input_size)
        h = int(h) if isinstance(h, int) and h > 0 else fallback
        w = int(w) if isinstance(w, int) and w > 0 else fallback
        return (h, w)

    # ------------------------------------------------------------- preprocess
    def _preprocess(self, tile_rgb: np.ndarray) -> np.ndarray:
        """RGB uint8 tile -> (1, 3, H, W) float32 tensor per the configured normalization."""
        in_h, in_w = self.input_hw
        img = tile_rgb
        if img.shape[0] != in_h or img.shape[1] != in_w:
            img = cv2.resize(img, (in_w, in_h), interpolation=cv2.INTER_LINEAR)
        x = img.astype(np.float32)
        if self.settings.onnx_channel_order.upper() == "BGR":
            x = x[..., ::-1]
        mode = self.settings.onnx_normalize
        if mode == "0-1":
            x = x / 255.0
        elif mode == "imagenet":
            x = (x / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
        # "0-255": raw float pixels (what Custom Vision compact exports expect).
        return np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None])

    # ------------------------------------------------------------- predict
    def _class_name(self, class_id: int) -> str:
        if 0 <= class_id < len(self.labels):
            return self.labels[class_id]
        return f"class_{class_id}"

    def predict(self, image: ImageInput) -> list[Detection]:
        if isinstance(image, np.ndarray):
            rgb = image
        else:
            from .imageio_utils import load_rgb_uint8

            rgb = load_rgb_uint8(image)
        img_h, img_w = rgb.shape[:2]
        s = self.settings

        windows = iter_tiles(img_w, img_h, s.slice_size, s.overlap_ratio)
        if s.perform_standard_pred and len(windows) > 1:
            windows.append((0, 0, img_w, img_h))  # full-frame pass catches large objects

        all_boxes: list[np.ndarray] = []
        all_scores: list[np.ndarray] = []
        all_ids: list[np.ndarray] = []
        num_classes = max(1, len(self.labels))
        for x0, y0, x1, y1 in windows:
            tensor = self._preprocess(rgb[y0:y1, x0:x1])
            outputs = self.session.run(None, {self.input_name: tensor})
            boxes01, scores, class_ids = parse_outputs(outputs, num_classes, self.input_hw)
            m = scores >= s.conf_threshold
            if not np.any(m):
                continue
            boxes01, scores, class_ids = boxes01[m], scores[m], class_ids[m]
            tw, th = float(x1 - x0), float(y1 - y0)
            boxes = boxes01 * np.array([tw, th, tw, th], dtype=np.float32)
            boxes += np.array([x0, y0, x0, y0], dtype=np.float32)
            all_boxes.append(boxes)
            all_scores.append(scores)
            all_ids.append(class_ids)

        if not all_boxes:
            return []
        boxes = np.clip(np.concatenate(all_boxes), 0, [img_w, img_h, img_w, img_h])
        scores = np.concatenate(all_scores)
        class_ids = np.concatenate(all_ids)
        keep = nms_per_class(boxes, scores, class_ids, s.onnx_nms_iou)

        detections: list[Detection] = []
        for i in keep:
            name = self._class_name(int(class_ids[i]))
            detections.append(
                Detection(
                    cls_name=str(name),
                    display=display_for(name),
                    score=float(scores[i]),
                    xyxy=tuple(float(v) for v in boxes[i]),
                )
            )
        return detections
