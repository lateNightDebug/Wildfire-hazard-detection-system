"""CLI: download manager for the detection models, printing each model's classes.

Downloads every enabled model source that has a configured URL (fire/smoke by
default; dead-tree once its source is set), into models/. Usage (from project root):
    python -m scripts.download_model
    python scripts/download_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script (not just `python -m`).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Some deps (Lightning/rich) emit Unicode; avoid crashes on non-UTF-8 consoles.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.wildfire.config import load_settings  # noqa: E402
from src.wildfire.models import ensure_yolo_sources  # noqa: E402


def main() -> int:
    settings = load_settings()
    print(f"Models directory: {settings.models_path}\n")
    for src in settings.model_sources:
        if src.backend == "deepforest":
            state = "deepforest (auto-downloads its own weights on first run)"
        elif src.hf_repo_id or src.fallback_url:
            state = "yolo, configured"
        else:
            state = "yolo, NO SOURCE (bring your own .pt)"
        print(f"  - {src.key:10s} {src.filename:16s} [{state}]  {src.label}")
    print()

    paths = ensure_yolo_sources(settings, log=lambda m: print(f"  {m}"))

    print(f"\nAvailable YOLO models: {[p.name for p in paths]}")
    try:
        from ultralytics import YOLO

        for p in paths:
            print(f"  {p.name}: classes={YOLO(str(p)).names}")
    except Exception as e:
        print(f"(Could not read class names: {e})")

    # Report DeepForest availability for the dead-tree backend.
    if any(s.enabled and s.backend == "deepforest" for s in settings.model_sources):
        try:
            from src.wildfire.deepforest_detector import deepforest_available

            ok = deepforest_available()
        except Exception:
            ok = False
        print(f"\nDeepForest (dead-tree): {'installed' if ok else 'NOT installed (pip install deepforest)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
