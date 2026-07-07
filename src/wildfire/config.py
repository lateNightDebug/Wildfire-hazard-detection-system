"""Settings: load/save JSON config with sane defaults and resolved paths.

`config/settings.json` is created from `config/settings.example.json` on first
load. Unknown keys in the JSON are ignored so the file can carry extra notes.

Detection uses one or more models (primary dead-tree + secondary fire/smoke),
each described by a ModelSource entry so the in-app download manager knows where
to fetch it. Detections from all available models are merged.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

# config.py lives at src/wildfire/config.py -> project root is parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
EXAMPLE_PATH = CONFIG_DIR / "settings.example.json"
SETTINGS_PATH = CONFIG_DIR / "settings.json"


@dataclass
class ModelSource:
    """A downloadable detection model for the download manager.

    `hf_repo_id` + `hf_filename` is the primary (Hugging Face) source;
    `fallback_url` is a zero-auth direct download used if HF is unavailable.
    A source with no URLs is "bring your own": drop a .pt into models/ yourself.
    """

    key: str  # "deadtree" / "firesmoke"
    filename: str  # local filename under models/ (for backend="yolo")
    label: str = ""  # human label for the UI
    backend: str = "yolo"  # "yolo" (SAHI+ultralytics .pt) or "deepforest"
    hf_repo_id: str = ""
    hf_filename: str = ""
    fallback_url: str = ""
    enabled: bool = True


def _default_model_sources() -> list[ModelSource]:
    return [
        ModelSource(
            key="deadtree",
            filename="dead_tree.pt",
            label="Hazardous dead trees (primary)",
            backend="deepforest",  # weecology DeepForest crown detector + alive/dead classifier
        ),
        ModelSource(
            key="firesmoke",
            filename="fire_smoke.pt",
            label="Flame & smoke (secondary)",
            hf_repo_id="leeyunjai/yolo11-firedetect",
            hf_filename="firedetect-11s.pt",
            fallback_url=(
                "https://raw.githubusercontent.com/sayedgamal99/"
                "Real-Time-Smoke-Fire-Detection-YOLO11/main/models/best_nano_111.pt"
            ),
        ),
    ]


@dataclass
class Settings:
    # --- LM Studio (Layer 2) ---
    lmstudio_url: str = "http://localhost:1234"
    lmstudio_model: str = "qwen3.5-9b"

    # --- paths (relative paths are resolved against the project root) ---
    output_dir: str = "outputs"
    models_dir: str = "models"

    # --- report ---
    language: str = "English"

    # --- detection / SAHI ---
    conf_threshold: float = 0.30
    slice_size: int = 1024
    overlap_ratio: float = 0.20
    batch_size: int = 4
    perform_standard_pred: bool = True

    # --- grid density map (per-image hazard-count overlay) ---
    grid_rows: int = 6
    grid_cols: int = 8

    # --- DeepForest dead-tree detector (backend="deepforest") ---
    df_patch_size: int = 800  # DeepForest tile size for predict_tile
    df_patch_overlap: float = 0.25
    df_crown_model: str = "weecology/deepforest-tree"
    df_dead_model: str = "weecology/cropmodel-deadtrees"
    df_dead_label: str = "Dead"  # crop-model label to keep (alive/dead)

    # --- models (primary dead-tree + secondary fire/smoke) ---
    model_sources: list[ModelSource] = field(default_factory=_default_model_sources)

    # ------------------------------------------------------------------ paths
    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (PROJECT_ROOT / path)

    @property
    def output_path(self) -> Path:
        return self._resolve(self.output_dir)

    @property
    def models_path(self) -> Path:
        return self._resolve(self.models_dir)

    def model_path_for(self, filename: str) -> Path:
        return self.models_path / filename

    def ensure_dirs(self) -> None:
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)

    def save(self, path: Optional[Path] = None) -> None:
        path = path or SETTINGS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def _scalar_keys() -> set[str]:
    return {f.name for f in fields(Settings) if f.name != "model_sources"}


def _modelsource_keys() -> set[str]:
    return {f.name for f in fields(ModelSource)}


def load_settings(path: Optional[Path] = None) -> Settings:
    """Load Settings from JSON, creating settings.json from the example if absent."""
    path = path or SETTINGS_PATH
    if not path.exists():
        if EXAMPLE_PATH.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(EXAMPLE_PATH, path)
        else:
            s = Settings()
            s.ensure_dirs()
            return s

    data = json.loads(path.read_text(encoding="utf-8"))

    scalar_keys = _scalar_keys()
    kwargs = {k: v for k, v in data.items() if k in scalar_keys}

    if isinstance(data.get("model_sources"), list):
        ms_keys = _modelsource_keys()
        sources = []
        for entry in data["model_sources"]:
            if isinstance(entry, dict):
                sources.append(ModelSource(**{k: v for k, v in entry.items() if k in ms_keys}))
        if sources:
            kwargs["model_sources"] = sources

    settings = Settings(**kwargs)
    settings.ensure_dirs()
    return settings
