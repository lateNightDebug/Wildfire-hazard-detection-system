# Wildfire Hazardous Tree Mapping System

A fully-offline, AI-powered tool that analyzes drone-captured forest images to detect
**hazardous standing dead trees** (primary) plus **flame and smoke** (secondary), and
generates a detailed PDF report for field teams.

- **Layer 1 — Detection** *(implemented)*: drone images → SAHI slicing (handles 5280×3956
  images) → YOLO11 (dead-tree primary + flame/smoke secondary) → annotated images
  (dead tree = yellow, flame = red, smoke = orange; nearby boxes merged) + a grid
  density (hazard-count) map + EXIF GPS.
  No risk classification — detections are simply flagged with their GPS location.
- **Layer 2 — Report** *(implemented)*: detection results → LM Studio local API (Qwen 3.5 9B)
  → written analysis → ReportLab PDF (landscape: cover + per-image pages with
  original/highlight/grid + summary page). Degrades gracefully when LM Studio is off.
- **Layer 1.5 — Human review/annotation** *(implemented)*: a distinct stage between
  detection and reporting. A Gradio app loads detections as **editable boxes** — the
  reviewer **draws** missed hazards, **deletes** false proposals, and **sets each label**.
  Only confirmed boxes enter the report; all are saved as a Phase-2 label set. Uses the
  `gradio_image_annotation` widget. Run `python -m src.wildfire.app`.
- **UI map** *(possible future addition)*: an offline satellite map with detection pins.

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

Outputs land in `outputs/`:
- `<image>_original.jpg`, `<image>_annotated.jpg` (dead tree = yellow, flame = red,
  smoke = orange; nearby detections merged + labeled), `<image>_gridmap.jpg` (per-cell hazard count)
- `batch.json` — per-image detections, GPS, flagged status, and batch statistics by type.

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

> Stock YOLO11 weights only detect COCO's 80 everyday classes — not dead trees, fire, or smoke.

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
                detectors (assembly), imageio_utils, gps, annotate, risk, pipeline, types
                Layer 2: llm (LM Studio/Qwen), report (ReportLab PDF)
                UI: app (Gradio human-review), review (candidate crops + confirm + labels)
scripts/        download_model.py, run_detection.py (--pdf), generate_report.py
tests/          unit + integration tests (22)
config/         settings.example.json
models/         downloaded weights (gitignored)
outputs/        *_original/_annotated/_gridmap.jpg, batch.json, report.pdf (gitignored)
```
