# Wildfire Hazard Detection System — User Manual

An offline desktop application that analyzes drone photos of forest, detects
**standing dead trees** (primary) and **flame / smoke** (secondary), lets a human
reviewer confirm every detection, and produces PDF field reports with an offline
satellite hazard map. After installation it runs **without any internet
connection** — designed for field laptops.

---

## 1. System requirements

| | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 10 64-bit (with [WebView2 runtime](https://developer.microsoft.com/microsoft-edge/webview2/)) | Windows 11 (WebView2 built in) |
| **CPU** | 4-core x86-64 | 8-core or better |
| **RAM** | 8 GB | 16 GB (32 GB if running LM Studio for AI report text) |
| **GPU** | none — runs on CPU, slow | NVIDIA GPU, ≥ 4 GB VRAM, driver supporting CUDA 12.x |
| **Disk** | 15 GB free | 30 GB+ free, SSD |
| **Display** | 1280 × 800 | 1920 × 1080 |
| **Python** | 3.13 (installed by you; venv created by `install.bat`) | — |
| **Internet** | install time only | also for model & map-tile downloads (one-time) |

Performance reference: one 5280 × 3956 drone photo takes **~13 s on an RTX-class
GPU** and **several minutes on CPU**. A 250-image flight ≈ 1 hour on GPU.
Analysis writes ~10–15 MB of imagery per photo into `outputs/` — budget disk
accordingly (a 250-image flight ≈ 3 GB; the output folder is configurable in
Settings).

macOS: the code supports Apple-Silicon (MPS) / CPU and has a
`requirements-mac.txt`, but the desktop shortcut installer is Windows-only and
macOS is **untested** — treat it as experimental.

## 2. Installation

1. Install **Python 3.13** from python.org — tick *“Add python.exe to PATH”*.
2. Unzip the release archive to a path **without spaces or non-ASCII characters**
   (e.g. `C:\Wildfire`).
3. Double-click **`install.bat`** — creates the environment, installs PyTorch
   (CUDA build, automatic CPU fallback) and all dependencies, and puts a
   **“Wildfire Hazard Detection”** shortcut on the Desktop and Start Menu.
   One-time, needs internet, ~4 GB download.
4. Launch from the desktop shortcut — a native window opens, no terminal.

Details and packaging instructions: see `INSTALL.md`.

## 3. First-time setup (once, while online)

1. **Detection models** — Settings → *Download missing models* (fire/smoke
   weights). The dead-tree DeepForest weights download automatically on the
   first detection run.
2. **Offline map** — Map → *⬇ Map data*: pick **Around my scanned area**
   (high-detail) and optionally **Alberta province base map**. Roads/rivers
   overlays: `python -m scripts.fetch_map_overlays --bbox <lat_min lon_min lat_max lon_max>`.
3. *(Optional)* **LM Studio** for AI-written report text: install LM Studio,
   load a Qwen-class model, start its server (localhost:1234), then verify with
   Settings → *Test connection*. Without it, reports simply omit the AI section.

After this, the machine can go fully offline.

## 4. Standard workflow

```
SD card in  →  Scans: Mission Folder →  flight card: Detect  →  Scan Detail:
Review boxes (confirm/draw/delete)  →  Generate Report (PDF)  →  Map / Reports
```

1. **Load the mission folder** — Scans page → paste the flight/SD-card path
   (e.g. `F:\DCIM`) → *Load folder*. Images are grouped by day and flight
   (a >45-min gap or a new day starts a new flight; huge continuous shoots are
   split into ~250-image parts). Telemetry sidecars are ignored automatically;
   DJI RTK `.MRK` files beside the photos are used for cm-grade GPS.
   Already-analyzed flights collapse into the **✓ ANALYZED** section.
2. **Detect** — *Detect all* on a flight card, or *Select images* to pick a
   subset in the full-screen chooser. Detection runs in a background
   low-priority process — keep using the app while it works; progress shows in
   the Recent Scans table.
3. **Review** (the human is the final classifier — detections are proposals):
   open the run → *✎ Review boxes* → wheel-zoom in, delete false boxes, draw
   missed hazards, set labels → *Save review*. Confirmed boxes become the
   training set (`labels.json`) and all counts/maps update.
4. **Report** — *Generate Report* on the detail page. Each PDF is timestamped,
   never overwritten; all PDFs are listed on the Reports page.
5. **Overview** — Dashboard (stats, map, review backlog, training-set size),
   Review page (day-by-day backlog), Map page (site markers: flame red, smoke
   orange, dead tree yellow; nearby images within 40 m merge into one site).

## 5. Where your data lives

```
outputs/<run>_<timestamp>/     one folder per analysis run
  originals/ annotated/ gridmaps/   imagery (raw / boxed / density)
  batch.json                        detections + GPS (machine-readable)
  labels.json                       your confirmed boxes = training data
  report_<timestamp>.pdf            reports (never overwritten)
models/                        detector weights (.pt / your dead_tree.onnx)
map/                           offline satellite tiles + road/water overlays
config/settings.json           all settings (editable in the Settings page)
```

Everything is local; nothing is uploaded anywhere.

## 6. Training your own dead-tree model (Phase 2)

1. Review runs in the app — every *Save review* grows the training set.
2. `python -m scripts.export_labels outputs/<run>` → Custom Vision dataset.
3. Upload & train on customvision.ai (Object Detection, **compact [S1]** domain);
   see README “Training your own model”.
4. Export as ONNX → drop `model.onnx` as `models/dead_tree.onnx` and
   `labels.txt` as `models/dead_tree.labels.txt` → the app uses it on the next
   run. If boxes come out empty/garbled, flip *Settings → Custom ONNX model →
   Normalize / Channel order*.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Window opens blank / never loads | Install the WebView2 runtime (Win 10), then relaunch |
| “Port 7861 is in use” | Another copy is already running — check the taskbar / Task Manager |
| Detection stuck at “loading detection models…” | First run downloads DeepForest weights — needs internet once; check `outputs/<run>/_worker.log` |
| Every image says *no detections* with your ONNX model | Flip `onnx_normalize` to `0-1` or channel order to `BGR` in Settings |
| Map is a stylized placeholder | No tiles cached for this area — Map → *⬇ Map data* |
| Report has no AI analysis section | LM Studio isn’t running — optional; start it and regenerate |
| GPS missing on the map | Photos lack EXIF GPS and no `.MRK` file sits beside them |
| App feels slow during detection | Expected on CPU-only machines; the UI stays usable — check progress in Scans |

## 8. Known limits (by design)

- Detections are **proposals**: RGB imagery physically cannot separate dead
  wood from bare ground reliably (the signal is in SWIR bands). The human
  review step is the accuracy guarantee, and it doubles as training-data
  collection for the custom model.
- The High/Medium/Low badge is a **display aid** derived from detection density
  and type (thresholds in Settings) — no formal risk score is stored.
- Overlapping flight photos re-shoot the same trees; the map merges images
  within 40 m into one *site*, but raw detection counts still contain overlap.
  Full de-duplication (orthomosaic pipeline) is on the roadmap.
