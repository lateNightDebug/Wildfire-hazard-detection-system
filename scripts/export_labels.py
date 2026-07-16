"""CLI: export a review run's labels.json into an Azure Custom Vision dataset.

The review app saves every confirmed box to outputs/<run>/labels.json. This tool
turns that file into training tiles + normalized regions ready to upload:

    python -m scripts.export_labels outputs/review_20260710_120000
    python -m scripts.export_labels outputs/review_.../labels.json --out cv_dataset

    # whole frames instead of tiles (auto re-encoded under the 6MB upload cap):
    python -m scripts.export_labels outputs/review_... --no-tile

Then upload (online, needs your Azure Custom Vision key):
    python -m scripts.upload_to_custom_vision cv_dataset --endpoint ... --key ... --project-id ...
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Allow running as a plain script (not just `python -m`).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.wildfire.cv_export import export_dataset  # noqa: E402


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export review labels.json to a Custom Vision-ready dataset."
    )
    ap.add_argument("labels", help="A labels.json file, or a run folder containing one.")
    ap.add_argument("--out", default=None,
                    help="Export folder (default: cv_export_<timestamp> next to the labels).")
    ap.add_argument("--tile", type=int, default=1024,
                    help="Tile size in px (default 1024 — match the inference slice size).")
    ap.add_argument("--overlap", type=float, default=0.2, help="Tile overlap fraction.")
    ap.add_argument("--min-vis", type=float, default=0.3,
                    help="Keep a clipped box only if >= this fraction is inside the tile.")
    ap.add_argument("--negatives", type=int, default=0,
                    help="Empty (no-box) tiles to keep per image (default 0).")
    ap.add_argument("--no-tile", action="store_true",
                    help="Export whole frames instead of tiles.")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    labels_path = Path(args.labels)
    if labels_path.is_dir():
        labels_path = labels_path / "labels.json"
    if not labels_path.exists():
        print(f"labels file not found: {labels_path}")
        return 2

    out_dir = Path(args.out) if args.out else (
        labels_path.parent / f"cv_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    manifest = export_dataset(
        labels_path, out_dir,
        tile=args.tile, overlap=args.overlap, min_visibility=args.min_vis,
        negatives_per_image=args.negatives, no_tile=args.no_tile, log=print,
    )
    if not manifest["images"]:
        print("No images exported — is the labels.json empty, or are the source images missing?")
        return 1

    print(f"\nDataset ready: {out_dir}")
    print("Next steps (Azure Custom Vision):")
    print("  1. On https://www.customvision.ai create an Object Detection project")
    print("     with a *compact* domain (General (compact) [S1]) so it can export ONNX.")
    print("  2. Upload with regions:  python -m scripts.upload_to_custom_vision "
          f"\"{out_dir}\" --endpoint <endpoint> --key <training-key> --project-id <id>")
    print("  3. Train, then Export -> ONNX. Put model.onnx as models/dead_tree.onnx and")
    print("     labels.txt as models/dead_tree.labels.txt — the app picks them up automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
