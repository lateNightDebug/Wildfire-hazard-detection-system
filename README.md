# Wildfire Hazardous Tree Mapping System

A fully-offline, AI-powered desktop tool that analyzes drone photos of forest to detect
**hazardous standing dead trees** (primary) plus **flame and smoke** (secondary), lets a
human reviewer confirm every detection, and produces PDF field reports with an offline
satellite hazard map.

> **End users:** see **[MANUAL.md](MANUAL.md)** for system requirements, installation,
> the standard field workflow, troubleshooting and known limits.
> Packaging/distribution: **[INSTALL.md](INSTALL.md)**. Delivery progress: **[PLAN.md](PLAN.md)**.

## How it works

- **Layer 1 — Detection**: drone images → optional pre-compression
  (`preprocess_max_mb`, resolution kept) → SAHI slicing (5280×3956 frames) →
  YOLO11 flame/smoke + DeepForest dead-tree proposals → annotated images
  (dead tree = yellow, flame = red, smoke = orange) + grid density maps + GPS
  (DJI RTK **.MRK** beside the photos preferred — cm-grade — falling back to EXIF).
  Detection runs in a **low-priority worker process**, so the UI never blocks.
  No formal risk classification — detections are flagged with their GPS location.
- **Layer 1.5 — Review** (the accuracy guarantee): detections are **proposals**, a human
  confirms them in the console's built-in box editor (zoom, draw, delete, relabel).
  Confirmed boxes become the run's `labels.json` — simultaneously the report source
  and the **training set** for the custom model.
- **Layer 2 — Report**: survey facts (flight metadata, densities, ranked hotspots) →
  LM Studio local LLM (graceful fallback when offline) → five-section professional
  analysis → ReportLab PDF: cover, per-image pages (capped at the top
  `report_max_image_pages` hazard images), and a summary page with a **real offline
  satellite hazard map** stitched from the tile cache.

> **Detection honesty:** RGB imagery physically cannot separate dead wood from bare
> brown ground reliably — that signal lives in SWIR bands RGB cameras don't capture
> (confirmed by literature + tests on real imagery). Hence review-first design; real
> autonomy comes from Phase-2 training on your confirmed labels.

Everything runs locally. Network is only needed for one-time setup downloads
(dependencies, model weights, map tiles) and the optional local LM Studio call.

## The operations console

The main interface — a FastAPI app at `http://127.0.0.1:7861`, installable as a
**desktop application** (native window, own icon, no terminal):

```bash
python -m scripts.install_desktop_app   # Desktop + Start Menu shortcuts
# alternatives: run_console.bat (browser mode) / python -m src.wildfire.console
```

| Page | What it does |
|------|--------------|
| **Dashboard** | Stat cards, hazard mini-map, detections by type, review backlog, training-set size |
| **Scans** | Mission-folder browser + upload + model status + run history |
| **Scan Detail** | Zoomable viewer (wheel/drag/dbl-click), click-to-locate detections, **box review editor**, report generation |
| **Review** | All runs grouped by day with needs-review/reviewed status — the backlog view |
| **Map** | Offline satellite map (Leaflet) with month/year filter and ≤40 m **site dedup**; in-UI tile download |
| **Reports** | Every generated PDF, newest first (timestamped, never overwritten) |
| **Settings** | Detection params, severity thresholds, model toggles, ONNX preprocessing, LM Studio test, map download |

Key behaviors:

- **Mission folder**: point it at a flight folder / SD-card dump (persisted, reloaded on
  startup). Only images are read — telemetry sidecars are ignored. Images are grouped by
  EXIF capture time into **flights** (>45 min gap or day change; continuous shoots split
  into ~100-image parts), each with a picker to detect a chosen subset. Fully analyzed
  flights collapse into an *Analyzed* section.
- **Severity badge** (display-only, no risk field in data): Flame → High;
  ≥`severity_deadtrees_high` (10) avg dead trees/image → High; Smoke → Medium;
  ≥`severity_deadtrees_medium` (3) → Medium; else Low.
- **Offline map data**: Map → *⬇ Map data* downloads Esri satellite tiles for the scanned
  area / whole Alberta / a custom rectangle (Esri permits offline export; Google/Bing do
  not). CLI equivalents: `scripts/fetch_map_tiles.py`, `scripts/fetch_map_overlays.py`
  (OSM roads/rivers/lakes).
- The legacy Gradio annotator (`run_app.bat`, port 7860) still works but is no longer
  needed — review happens inside the console.

## Requirements & setup

Minimums (details in [MANUAL.md](MANUAL.md)): Windows 10/11 64-bit, Python 3.13, 8 GB RAM,
~15 GB disk; any NVIDIA GPU enables CUDA (CPU works, slower). macOS (MPS/CPU) is
code-compatible but untested.

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements-win-cuda.txt   # CUDA torch FIRST (mac: requirements-mac.txt)
pip install -r requirements.txt
pip install -r requirements-deadtree.txt   # DeepForest dead-tree proposer (heavy)
```

Or just run **`install.bat`** — it does all of the above plus the desktop shortcut.

## Headless CLI (optional)

```bash
python -m scripts.run_detection <folder> --pdf     # detect + report, no UI
python -m scripts.generate_report                  # PDF from an existing batch.json
```

## Run outputs

Each run gets its own folder; artifacts are sorted by kind so a 100-image flight stays
navigable:

```
outputs/<run>_<timestamp>/
  originals/<image>.jpg             full-res copy of each input
  annotated/<image>.jpg             detection boxes drawn
  annotated/<image>_confirmed.jpg   re-rendered from reviewer-confirmed boxes
  gridmaps/<image>.jpg              per-cell hazard-count map (+ _confirmed)
  batch.json                        per-image detections, GPS, statistics
  labels.json                       confirmed boxes — the training set
  report_<timestamp>.pdf            never overwritten
```

## Detection models

Detector backends are a small registry in `src/wildfire/detectors.py` — a new model is
one class + one builder + a `model_sources` entry in `config/settings.json`:

- **Dead trees (primary, `backend: "deepforest"`):** [DeepForest](https://deepforest.readthedocs.io)
  crown detector + alive/dead classifier (weights auto-download once, cached offline).
  Zero-training Phase-1 proposer; Phase 2 replaces it with your custom model.
- **Flame & smoke (`backend: "yolo"`):** auto-downloads `firedetect-11s.pt`
  (`leeyunjai/yolo11-firedetect`), GitHub fallback; runs through SAHI slicing. Any extra
  YOLO `.pt` dropped into `models/` is also run.
- **Custom dead-tree model (Phase 2, `backend: "onnx"`):** drop your trained export into
  `models/` as `dead_tree.onnx` + `dead_tree.labels.txt` — picked up automatically.
  Handles Azure Custom Vision and Ultralytics ONNX layouts, manual tiling + NMS,
  preprocessing tunable via the `onnx_*` settings (also in the Settings page).

## Training your own model (Azure Custom Vision → ONNX)

Every saved review grows `labels.json`. The loop:

```bash
# 1) Export as Custom Vision-ready tiles + normalized regions (tiling matches inference)
python -m scripts.export_labels outputs/<run>

# 2) customvision.ai: Object Detection project, compact domain "General (compact) [S1]"
#    (compact = ONNX-exportable)

# 3) Upload with boxes (the one online step; pip install azure-cognitiveservices-vision-customvision)
python -m scripts.upload_to_custom_vision <export_dir> --endpoint <url> --key <key> --project-id <guid>

# 4) Train → Export → ONNX → copy into models/ as dead_tree.onnx + dead_tree.labels.txt
```

If your model returns empty/garbled boxes, flip `onnx_normalize` (`0-255` ↔ `0-1`) or
`onnx_channel_order` (`RGB` ↔ `BGR`) in Settings — no code changes.

## Tests

```bash
pytest -q     # 70 tests; heavy integration tests auto-skip without models
```

## Project layout

```
src/wildfire/    Layer 1: config, device, models, detect (SAHI/YOLO), deepforest_detector,
                 onnx_detector, detectors (backend registry), imageio_utils, gps (EXIF+MRK),
                 annotate, risk, pipeline, types
                 Layer 2: llm (LM Studio), report (PDF + offline satellite map)
                 Phase 2: cv_export (labels.json -> Custom Vision dataset)
                 Legacy UI: app (Gradio), review
src/wildfire/console/
                 server (FastAPI + JSON API), data (runs/severity/sites), ingest
                 (mission folder), jobs + worker (subprocess detection), tiles
                 (offline map download), desktop (native window), pages/ + static/
scripts/         run_detection, generate_report, download_model, export_labels,
                 upload_to_custom_vision, fetch_map_tiles, fetch_map_overlays,
                 install_desktop_app
tests/           70 unit + integration tests
config/          settings.example.json (settings.json is created on first run)
models/          detector weights (gitignored)
map/             offline satellite tiles + overlays.geojson (gitignored)
outputs/         one folder per run (gitignored)
MANUAL.md        user manual · INSTALL.md packaging · PLAN.md delivery checklist
```
