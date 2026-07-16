# Wildfire Hazardous Tree Mapping System

A fully-offline, AI-powered tool that analyzes drone-captured forest images to detect
**hazardous standing dead trees** (primary) plus **flame and smoke** (secondary), and
generates a detailed PDF report for field teams.

- **Layer 1 — Detection** *(implemented)*: drone images → SAHI slicing (handles 5280×3956
  images) → YOLO11 (dead-tree primary + flame/smoke secondary) → annotated images
  (dead tree = yellow, flame = red, smoke = orange; nearby boxes merged) + a grid
  density (hazard-count) map + GPS (DJI RTK **.MRK** beside the photos is preferred —
  cm-grade — falling back to EXIF). Oversized photos are re-encoded under
  `preprocess_max_mb` (default 2 MB, resolution kept) before detection for faster batches.
  No risk classification — detections are simply flagged with their GPS location.
- **Layer 2 — Report** *(implemented)*: detection results → LM Studio local API (Qwen 3.5 9B)
  → written analysis → ReportLab PDF (landscape: cover + per-image pages with
  original/highlight/grid + summary page). Degrades gracefully when LM Studio is off.
- **Layer 1.5 — Human review/annotation** *(implemented)*: a distinct stage between
  detection and reporting. A Gradio app loads detections as **editable boxes** — the
  reviewer **draws** missed hazards, **deletes** false proposals, and **sets each label**.
  Only confirmed boxes enter the report; all are saved as a Phase-2 label set. Uses the
  `gradio_image_annotation` widget. Run `python -m src.wildfire.app`.
- **Operations console** *(implemented)*: an offline app (FastAPI,
  `http://127.0.0.1:7861`) that is the main way to use the tool.
  **Install it as a desktop app** (native window, own icon, no terminal):

  ```bash
  python -m scripts.install_desktop_app
  # -> creates assets/wildfire.ico + "Wildfire Hazard Detection" shortcuts on the
  #    Desktop and Start Menu, launching pythonw -m src.wildfire.console --desktop
  ```

  Alternatives: `run_console.bat` (browser mode) or `python -m src.wildfire.console`.
  Views:
  - **Dashboard** — stat cards, hazard map with GPS pins, severity distribution.
  - **Scans** — model status, mission-folder browser, upload, run history.
  - **Scan Detail** — image viewer (annotated/original/grid) **with a built-in box
    editor**: click *Review boxes*, draw missed hazards, delete false ones, set labels,
    then *Save review* — confirmed boxes are written to the run's `labels.json`
    (the training set for the next model round) and the confirmed imagery is
    re-rendered. Reports generate from confirmed boxes when a review exists.
  - **Review** — all runs grouped by day with thumbnails and needs-review/reviewed
    status: the data overview for working through a backlog.
  - **Map** — full-screen hazard map. With offline tiles downloaded it is a real
    zoomable satellite map (Leaflet) with OSM roads/rivers/lakes overlays;
    otherwise it falls back to a stylized canvas. Flagged images are merged
    into **sites** (≤40 m clustering) so overlapping shots of the same trees
    appear once. Prepare an area before going offline:
    ```bash
    python -m scripts.fetch_map_tiles    --bbox 51.05 -115.48 51.17 -115.28 --zoom 11 16
    python -m scripts.fetch_map_overlays --bbox 51.05 -115.48 51.17 -115.28
    ```
    (Esri World Imagery permits offline export; Google/Bing tiles do not.)
  - **Reports** — every generated PDF across all runs, newest first.
  - **Settings** — edit detection parameters, severity thresholds, model on/off
    toggles, ONNX preprocessing and LM Studio connection (with a test button)
    right in the UI; saved to `config/settings.json`.
  - **Mission folder**: point the console at a flight folder / SD-card dump
    (persisted in `settings.json → source_dir`, reloaded on startup). Only images are
    read — telemetry sidecars (.SRT/.DAT/...) are ignored and counted. Images are
    sorted by EXIF capture time and grouped into **flights** (new session on a >45 min
    gap or day change), labeled by day + time of day (Morning/Midday/Afternoon/
    Evening/Night) with a thumbnail — one click detects a whole flight.
  - **Severity badge** (High/Medium/Low) is display-only and dead-tree-density driven:
    Flame → High; ≥`severity_deadtrees_high` (10) avg dead trees/image → High;
    Smoke → Medium; ≥`severity_deadtrees_medium` (3) → Medium; else Low. The
    underlying data keeps no risk field. Note: overlapping flight photos re-count the
    same trees, so raw counts are inflated until dedup (see roadmap).
  - The standalone Gradio annotator (`run_app.bat`, port 7860) still works but is no
    longer required — review now happens inside the console.
- **UI map** *(possible future addition)*: an offline satellite map with detection pins
  (the console map uses a stylized terrain canvas with real GPS positioning).

> **Detection honesty:** detecting standing dead trees from RGB drone photos cannot be done
> reliably/autonomously — the signal that separates dead wood from bare brown ground is in the
> SWIR band, which RGB cameras don't capture (confirmed by literature + tests on real imagery).
> So detections are **proposals**; a human confirms them. Real accuracy comes from Phase-2
> (a model trained on your labeled images) and, if you supply the full overlapping flight, a
> photogrammetry height model (CHM) that uses height to separate trees from same-colored ground.

Everything runs locally; the only network call is to a local LM Studio server for the report text.

## Requirements

- Python 3.13
- Windows + NVIDIA GPU (RTX 4090) for CUDA acceleration, **or** macOS (CPU / Apple-Silicon MPS).
- ~3 GB disk for PyTorch + the YOLO models.

## Setup

### Windows (NVIDIA RTX 4090)

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip

# 1) CUDA-enabled PyTorch FIRST (so pip doesn't pull CPU-only torch as a dependency)
pip install -r requirements-win-cuda.txt          # cu128; switch to cu130/cu126 if needed

# 2) then the core dependencies
pip install -r requirements.txt

# 3) dead-tree detection backend (DeepForest — heavy; optional but recommended)
pip install -r requirements-deadtree.txt

# verify the GPU is visible
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# expect: 2.x+cu128  True  NVIDIA GeForce RTX 4090
```

### macOS (CPU / MPS)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements-mac.txt    # plain torch wheels (CPU + MPS), no CUDA
pip install -r requirements.txt
```

> `rasterio` is optional — only needed if your drone images are GeoTIFF orthomosaics
> (location stored in geo-transform tags instead of EXIF). Uncomment it in `requirements.txt`.

## Usage (Layer 1, headless)

All commands run from the project root.

```bash
# 1) Download/locate the detection models (manager). Fire/smoke auto-downloads;
#    the dead-tree model is "bring your own" until its source is configured.
python -m scripts.download_model

# 2) Run detection on a folder of drone images
python -m scripts.run_detection sample_data

# optional overrides
python -m scripts.run_detection sample_data --out outputs --conf 0.25 --slice 1024

# 3) (Layer 2) detect AND build a PDF report in one go
python -m scripts.run_detection sample_data --pdf
# ...or build the PDF later from an existing batch.json:
python -m scripts.generate_report                  # outputs/batch.json -> outputs/report.pdf
```

### The review app (recommended way to use the tool)

Make sure the **venv is active** first (or use the venv's Python directly — the system
`python` does not have the dependencies):

```bash
# Windows: activate the venv, then run
.venv\Scripts\activate
python -m src.wildfire.app          # opens http://127.0.0.1:7860 in your browser

# ...or without activating, call the venv Python directly:
.venv\Scripts\python.exe -m src.wildfire.app
```

1. Upload drone images → **Run detection** (proposals load as editable boxes).
2. **Review/annotate** (Layer 1.5): on each image, **draw** boxes for missed dead trees /
   fallen logs / flame / smoke, **delete** false proposals, and **set the label** per box.
   Switch images with the dropdown.
3. **Generate PDF** → only the confirmed boxes go into the report; all are saved to
   `outputs/labels.json` (your Phase-2 training set).

> Detections are **proposals**, not verdicts — you are the final classifier. (RGB alone
> can't reliably separate dead wood from bare ground; see "Detection honesty" above.)

> The PDF's "AI Analysis" section is written by a local LLM. Start the **LM Studio**
> server (Developer tab → Start) with a model loaded (e.g. Qwen) so the app can reach
> `http://localhost:1234`. If it's offline, the PDF is still produced with a fallback note.

Each run gets its own folder under `outputs/<name>_<timestamp>/`, with artifacts
sorted by kind (a 200-image flight stays navigable):

```
outputs/<run>/
  originals/<image>.jpg             full-res copy of each input
  annotated/<image>.jpg             detection boxes drawn (dead tree = yellow,
                                    flame = red, smoke = orange)
  annotated/<image>_confirmed.jpg   re-rendered from human-confirmed boxes
  gridmaps/<image>.jpg              per-cell hazard-count map (+ _confirmed variant)
  batch.json                        per-image detections, GPS, batch statistics
  labels.json                       reviewer-confirmed boxes (the training set)
  report_<timestamp>.pdf            each generation gets a new file — never overwritten
```

## Detection models

The pipeline runs **two kinds of detector** and merges their detections, mapping each
class to a display label + color (Dead Tree = yellow / Flame = red / Smoke = orange).
Configure them in `config/settings.json` → `model_sources` (each has a `backend`):

- **Dead trees (primary, `backend: "deepforest"`):** [DeepForest](https://deepforest.readthedocs.io)
  crown detector (`weecology/deepforest-tree`) + alive/dead classifier
  (`weecology/cropmodel-deadtrees`). No turnkey YOLO11 dead-tree model exists, so this is
  the zero-training Phase-1 path; both weights auto-download once and are cached for offline
  use. It is torchvision (not YOLO/SAHI) and runs alongside the YOLO detector. Install via
  `requirements-deadtree.txt`. Phase 2 swaps in a model trained on client drone images.
- **Flame & smoke (secondary, `backend: "yolo"`):** auto-downloads `firedetect-11s.pt`
  (`leeyunjai/yolo11-firedetect`, Hugging Face), with the Flare Guard `best_nano_111.pt`
  GitHub raw file as a zero-auth fallback. Verified real YOLO11 fire/smoke models, run
  through SAHI slicing. Any extra YOLO `.pt` you drop into `models/` is also run.
- **Custom dead-tree model (Phase 2, `backend: "onnx"`):** an onnxruntime detector for
  a model you train yourself (see *Training your own model* below). Drop the exported
  `model.onnx` into `models/` as `dead_tree.onnx` and its `labels.txt` as
  `dead_tree.labels.txt` — the app picks them up automatically (until then this source
  is skipped with a log note). Runs fully offline with manual tiling + NMS, so tiny
  trees in 5280×3956 frames are still found. Supports both Azure Custom Vision exports
  and Ultralytics YOLO ONNX exports; preprocessing is tunable via the `onnx_*` settings.

Detector backends are a small registry in `src/wildfire/detectors.py` — adding another
kind of model is: write a class with `.predict(image) -> list[Detection]`, register a
builder, add a `model_sources` entry. The pipeline, review UI and report don't change.

> Stock YOLO11 weights only detect COCO's 80 everyday classes — not dead trees, fire, or smoke.

## Training your own model (Azure Custom Vision → ONNX)

Every review session saves the human-confirmed boxes to `outputs/<run>/labels.json` —
that is your training set. The loop:

```bash
# 1) Export the labels as Custom Vision-ready tiles + normalized regions.
#    Tiling matches inference (1024px slices) so small trees survive Custom Vision's
#    internal resizing; use --no-tile to upload whole frames instead.
python -m scripts.export_labels outputs/review_<timestamp>

# 2) On https://www.customvision.ai create an Object Detection project with a
#    *compact* domain — "General (compact) [S1]" — compact is what allows ONNX export.

# 3) Upload the dataset with its boxes (the only online step; needs the optional SDK:
#    pip install azure-cognitiveservices-vision-customvision):
python -m scripts.upload_to_custom_vision outputs/review_<timestamp>/cv_export_<ts> \
    --endpoint https://<resource>.cognitiveservices.azure.com/ \
    --key <training-key> --project-id <project-guid>

# 4) Train in the portal, then Performance -> Export -> ONNX. Unzip and copy:
#      model.onnx  -> models/dead_tree.onnx
#      labels.txt  -> models/dead_tree.labels.txt
#    Done — the next detection run uses your model, fully offline.
```

Tune the ONNX runtime behavior in `config/settings.json` if needed: `onnx_input_size`
(fallback for dynamic inputs), `onnx_normalize` (`"0-255"` for Custom Vision exports,
`"0-1"`/`"imagenet"` for others), `onnx_channel_order`, `onnx_nms_iou`. The default
`onnxruntime` package is CPU; installing `onnxruntime-gpu` instead enables CUDA
automatically.

## Configuration

`config/settings.json` is created from `config/settings.example.json` on first run. Tune
detection confidence, SAHI slice size, model sources, LM Studio URL/model, and output folder there.

## Tests

```bash
pytest -q
```

Unit tests (GPS conversion, image IO, stats/mapping) run anywhere. The detection
integration test auto-skips unless the heavy deps and at least one model are present.

## Project layout

```
src/wildfire/   Layer 1: config, device, models, detect (SAHI/YOLO), deepforest_detector,
                onnx_detector (custom ONNX models), detectors (backend registry),
                imageio_utils, gps, annotate, risk, pipeline, types
                Layer 2: llm (LM Studio/Qwen), report (ReportLab PDF)
                UI: app (Gradio human-review), review (candidate crops + confirm + labels)
                console/ (FastAPI operations console: dashboard/scans/detail pages,
                JSON API, mission-folder ingest, background detection jobs,
                review-app auto-start, vendored IBM Plex fonts)
                Phase 2: cv_export (labels.json -> Custom Vision dataset)
scripts/        download_model.py, run_detection.py (--pdf), generate_report.py,
                export_labels.py, upload_to_custom_vision.py, install_desktop_app.py
tests/          unit + integration tests (59)
config/         settings.example.json
models/         downloaded weights (gitignored)
outputs/        *_original/_annotated/_gridmap.jpg, batch.json, report.pdf (gitignored)
```
