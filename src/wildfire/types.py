"""Plain data structures passed between Layer 1 modules.

Kept dependency-free (stdlib only) so any module can import them cheaply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Detection:
    """A single object detection from the SAHI + YOLO pipeline."""

    cls_name: str  # raw model class name, e.g. "fire" / "smoke" (casing varies)
    display: str  # human label: "Flame" / "Smoke" / raw name
    score: float  # confidence 0..1
    xyxy: tuple[float, float, float, float]  # (minx, miny, maxx, maxy), original-image pixels

    @property
    def area(self) -> float:
        minx, miny, maxx, maxy = self.xyxy
        return max(0.0, maxx - minx) * max(0.0, maxy - miny)

    def to_dict(self) -> dict:
        return {
            "cls_name": self.cls_name,
            "display": self.display,
            "score": round(float(self.score), 4),
            "xyxy": [round(float(v), 1) for v in self.xyxy],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Detection":
        return cls(
            cls_name=d["cls_name"], display=d["display"],
            score=float(d["score"]), xyxy=tuple(d["xyxy"]),
        )


@dataclass
class ImageResult:
    """Everything Layer 1 produces for one input image.

    No risk classification (per spec): detections are simply flagged with the
    image's GPS location. `flagged` is True when the image has any detection;
    the map places one pin per detection at this image's GPS coordinate.
    """

    path: str
    name: str
    width: int
    height: int
    detections: list[Detection] = field(default_factory=list)
    gps: Optional[tuple[float, float]] = None  # (lat, lon) decimal degrees
    altitude: Optional[float] = None  # meters
    timestamp: Optional[str] = None  # capture time if available
    camera: Optional[str] = None  # drone/camera model from EXIF (e.g. "DJI FC3582")
    flagged: bool = False  # has at least one detection (a hazard location)
    orig_display_path: Optional[str] = None
    annotated_path: Optional[str] = None
    density_path: Optional[str] = None  # grid density (hazard-count) map
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "detections": [d.to_dict() for d in self.detections],
            "gps": list(self.gps) if self.gps else None,
            "altitude": self.altitude,
            "timestamp": self.timestamp,
            "camera": self.camera,
            "flagged": self.flagged,
            "orig_display_path": self.orig_display_path,
            "annotated_path": self.annotated_path,
            "density_path": self.density_path,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ImageResult":
        gps = d.get("gps")
        return cls(
            path=d["path"], name=d["name"], width=d.get("width", 0), height=d.get("height", 0),
            detections=[Detection.from_dict(x) for x in d.get("detections", [])],
            gps=tuple(gps) if gps else None,
            altitude=d.get("altitude"), timestamp=d.get("timestamp"),
            camera=d.get("camera"),
            flagged=d.get("flagged", False),
            orig_display_path=d.get("orig_display_path"),
            annotated_path=d.get("annotated_path"),
            density_path=d.get("density_path"),
            error=d.get("error"),
        )


@dataclass
class BatchResult:
    """A whole batch of processed images plus aggregate statistics."""

    images: list[ImageResult] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    batch_info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "batch_info": self.batch_info,
            "stats": self.stats,
            "images": [im.to_dict() for im in self.images],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BatchResult":
        return cls(
            images=[ImageResult.from_dict(x) for x in d.get("images", [])],
            stats=d.get("stats", {}),
            batch_info=d.get("batch_info", {}),
        )

