"""CLI: upload an exported dataset (annotations.json) to Azure Custom Vision.

This is the ONE online step of the Phase-2 training loop (training happens in
Azure; detection stays offline). Requires the optional SDK:

    pip install azure-cognitiveservices-vision-customvision

Usage:
    python -m scripts.upload_to_custom_vision <export_dir> \
        --endpoint https://<resource>.cognitiveservices.azure.com/ \
        --key <training-key> --project-id <project-guid>

The project must be an Object Detection project on a *compact* domain
(General (compact) [S1]) so the trained model can be exported to ONNX.
Missing tags are created automatically; images upload in batches of 64
(the Custom Vision API limit).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Upload a cv_export dataset to Custom Vision.")
    ap.add_argument("dataset", help="Export folder (with annotations.json) or the file itself.")
    ap.add_argument("--endpoint", required=True, help="Custom Vision training endpoint URL.")
    ap.add_argument("--key", required=True, help="Custom Vision training key.")
    ap.add_argument("--project-id", required=True, help="Target project GUID (customvision.ai).")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    dataset = Path(args.dataset)
    manifest_path = dataset if dataset.is_file() else dataset / "annotations.json"
    if not manifest_path.exists():
        print(f"annotations.json not found: {manifest_path}")
        return 2
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    try:
        from azure.cognitiveservices.vision.customvision.training import (
            CustomVisionTrainingClient,
        )
        from azure.cognitiveservices.vision.customvision.training.models import (
            ImageFileCreateBatch, ImageFileCreateEntry, Region,
        )
        from msrest.authentication import ApiKeyCredentials
    except ImportError:
        print("The Azure Custom Vision SDK is not installed. Run:\n"
              "  pip install azure-cognitiveservices-vision-customvision")
        return 2

    credentials = ApiKeyCredentials(in_headers={"Training-key": args.key})
    trainer = CustomVisionTrainingClient(args.endpoint, credentials)

    # Ensure every tag exists in the project; map name -> tag id.
    existing = {t.name: t.id for t in trainer.get_tags(args.project_id)}
    tag_ids: dict[str, str] = {}
    for name in manifest.get("tags", []):
        if name not in existing:
            print(f"creating tag: {name}")
            existing[name] = trainer.create_tag(args.project_id, name).id
        tag_ids[name] = existing[name]

    entries: list = []
    for im in manifest.get("images", []):
        img_path = root / im["file"]
        if not img_path.exists():
            print(f"missing image, skipped: {img_path}")
            continue
        regions = [
            Region(tag_id=tag_ids[r["tag"]], left=r["left"], top=r["top"],
                   width=r["width"], height=r["height"])
            for r in im.get("regions", []) if r.get("tag") in tag_ids
        ]
        entries.append(ImageFileCreateEntry(
            name=img_path.name, contents=img_path.read_bytes(), regions=regions,
        ))

    if not entries:
        print("Nothing to upload.")
        return 1

    total_ok = 0
    for i in range(0, len(entries), 64):  # API limit: 64 images per batch
        batch = entries[i:i + 64]
        result = trainer.create_images_from_files(
            args.project_id, ImageFileCreateBatch(images=batch)
        )
        ok = sum(1 for r in result.images if r.status in ("OK", "OKDuplicate"))
        total_ok += ok
        bad = [(r.source_url or "?", r.status) for r in result.images
               if r.status not in ("OK", "OKDuplicate")]
        print(f"batch {i // 64 + 1}: {ok}/{len(batch)} uploaded")
        for name, status in bad:
            print(f"  failed: {name} ({status})")

    print(f"done: {total_ok}/{len(entries)} images uploaded. "
          "Now hit Train on customvision.ai, then Export -> ONNX.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
