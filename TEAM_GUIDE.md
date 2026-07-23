# Team Guide — Understanding and Maintaining This Project

For everyone on the team. **Part 1 is for all members** (including those who
don't write code) — read it before any demo or review. **Part 2 is for anyone
who touches the code.**

Other docs: [README.md](README.md) (technical overview) ·
[MANUAL.md](MANUAL.md) (end-user manual) · [INSTALL.md](INSTALL.md) (packaging) ·
[PLAN.md](PLAN.md) (what was built, in order).

---

# PART 1 — Everyone

## 1. What this project is (in 60 seconds)

**The problem:** Alberta's forests are full of **standing dead trees** — dry fuel
that turns a spark into a crown fire. Today, crews find them by walking the
forest with binoculars: slow, subjective, and hard to map.

**Our solution:** a **fully-offline desktop application**. A drone flies the
forest; our app reads the photos, finds hazards with AI, lets a person confirm
each one, and produces a GPS-accurate hazard map and a PDF field report.

**Who uses it:** forestry / fire crews working in the field, **with no internet**.
That constraint drives the entire design.

**One sentence to memorize:**
> "It turns a drone flight into a reviewed, GPS-accurate hazardous-tree map and
> field report — completely offline."

## 2. The one idea you must understand

**AI detections are PROPOSALS, not answers. A human confirms them.**

Why? Because of physics, not laziness: with a normal RGB camera you **cannot**
reliably tell dead wood from bare brown ground — the wavelength that separates
them (SWIR) isn't captured by the camera. We tested this and confirmed it in
the literature.

So the design is deliberately:

```
AI finds candidates  →  a person confirms/corrects  →  confirmed boxes become
                                                        BOTH the report data
                                                        AND the training set
```

Every review makes the next model better. That loop is the heart of the product.
If someone asks "how accurate is your AI?", the honest answer is: *"The AI
proposes; the operator decides. The confirmed results feed training, so accuracy
improves with every mission."*

## 3. The three AI pieces

| # | What | Where it runs |
|---|------|---------------|
| 1 | **Detection** — YOLO11 (flame/smoke) + DeepForest (dead-tree candidates), with SAHI tiling so tiny trees in 21-megapixel photos are found | Field laptop GPU, ~13 s/photo, offline |
| 2 | **Report analysis** — a local LLM (LM Studio) writes a 5-section professional analysis grounded in the real numbers and GPS | Field laptop, offline |
| 3 | **Training loop** — confirmed boxes → Azure Custom Vision (cloud training) → ONNX model → runs offline | Cloud for training only |

## 4. Running it

```bash
# First time only (needs internet, ~4 GB):
install.bat

# Every day:
double-click "Wildfire Hazard Detection" on the Desktop
```

If the shortcut is missing: `.venv\Scripts\python.exe -m src.wildfire.console --desktop`

**Optional:** start LM Studio with a model loaded *before* generating a report,
or the report simply omits the AI analysis section (everything else still works).

## 5. The normal workflow (what a demo looks like)

1. **Scans page → Mission Folder** — paste the flight folder path (e.g. `F:\DCIM`),
   click *Load folder*.
   The app reads **only images**, sorts them by capture time, and groups them into
   **flights** (a >45 min gap or a new day starts a new flight; long shoots split
   into ~100-image parts). Telemetry files are ignored. DJI RTK `.MRK` files give
   centimetre-grade GPS.
2. **Detect** — click *Detect all* on a flight card (or *Select images* to pick a
   subset). Detection runs in a **separate background process** — you can keep
   using the app while it works.
3. **Review** — open the finished run → *✎ Review boxes*: zoom in, delete wrong
   boxes, draw missed ones, set labels → *Save review*. Use *Mark reviewed* per
   image to track progress (the green check on thumbnails).
4. **Report** — *Generate Report* → a timestamped PDF with a satellite hazard map,
   per-image pages, and the AI analysis.
5. **Overview** — Dashboard (stats + map), Review (backlog by day), Map (all sites),
   Reports (all PDFs).

## 6. Where everything lives

```
outputs/<run>_<timestamp>/     one folder per detection run
   originals/  annotated/  gridmaps/    the three image renditions
   batch.json          detections + GPS + stats (machine-readable)
   labels.json         confirmed boxes = the training set
   reviewed_images.json  which images the operator ticked off
   report_<time>.pdf   reports (a new file each time, never overwritten)
models/     detector weights (fire/smoke .pt, your trained dead_tree.onnx)
map/        offline satellite tiles + road/water overlays
branding/   logo + brand.json (see LOGO_GUIDE.txt inside)
config/settings.json    all settings (editable in the Settings page)
```

**Nothing is uploaded anywhere.** Everything stays on the machine.

## 7. Routine maintenance (no coding needed)

| Task | How |
|------|-----|
| **Change the logo / app name** | Drop `logo.png` into `branding/`, edit `branding/brand.json`, restart the app. Applies to the UI *and* the PDF. |
| **Tune detection** (confidence, tile size) | Settings page → Detection. Takes effect on the next run. |
| **Change severity thresholds** | Settings page → Display severity (dead trees per image). |
| **Set who produced a run** | Settings page → Operator name. Shows on reports. Optional; it is *not* a login. |
| **Add your trained model** | Put `dead_tree.onnx` + `dead_tree.labels.txt` into `models/`. The app picks it up automatically. If boxes look wrong, flip *Normalize* / *Channel order* in Settings. |
| **Download map for a new area** | Map page → *⬇ Map data* → pick "Around my scanned area" (needs internet once). |
| **Free up disk space** | Delete whole `outputs/<run>/` folders you no longer need. Each run is self-contained. Keep `labels.json` if you want to preserve training data. |
| **Check the AI report writer** | Settings → *Test connection* (LM Studio). |

## 8. When something goes wrong

| Symptom | Cause / Fix |
|---------|-------------|
| **Blank window on launch** | Windows 10 needs the WebView2 runtime — install it, relaunch. |
| **"Port 7861 is in use"** | The app is already running — check the taskbar / Task Manager. |
| **Page looks unstyled, "Failed to fetch"** | The app was updated while running. **Close the window and reopen.** (Pages reload from disk, but the Python service only loads at startup.) |
| **Detection stuck on "loading detection models…"** | First run downloads model weights — needs internet once. Check `outputs/<run>/_worker.log`. |
| **Report has no AI section** | LM Studio isn't running. Optional — start it and regenerate. |
| **Map is a stylized drawing, not satellite** | No tiles cached for that area — Map page → *⬇ Map data*. |
| **No GPS on the map** | Photos have no EXIF GPS and no `.MRK` file beside them. |
| **Every image shows "no detections" with a new ONNX model** | Wrong preprocessing — flip `onnx_normalize` (`0-255` ↔ `0-1`) or `onnx_channel_order` (RGB ↔ BGR) in Settings. |

**Golden rule: after any code update, restart the app.**

## 9. How to explain this project (every member should be able to)

Be ready to answer these in your own words:

- **What problem does it solve?** → Section 1.
- **What's the AI doing?** → Section 3 (three pieces: detect, analyse, learn).
- **Why is a human in the loop?** → Section 2 (RGB/SWIR physics — this is a
  *design decision*, not a weakness).
- **Where's the cloud?** → Training runs on Azure Custom Vision; map imagery comes
  from Esri and is cached. The app itself is deployed at the **edge** (the field
  laptop) because the client works without connectivity.
- **Is it microservices?** → Honestly, no — it's a **modular monolith**. Detection
  runs in a separate low-priority process (because heavy inference used to freeze
  the UI), the LLM is a separate service we call over HTTP, and Custom Vision is
  an external cloud service. For a single-operator offline tool, network
  microservices would add latency and failure modes with no benefit.
- **What are the limits?** → Detections are proposals; overlapping photos can
  count the same tree more than once (we merge sites within 40 m on the map);
  severity badges are a display aid, not a formal risk score.

Numbers worth remembering: **72 automated tests**, **~13 s per 21 MP photo on GPU**,
a real **1,558-image** DJI L2 mission processed, **centimetre-grade RTK GPS**.

---

# PART 2 — For anyone touching the code

## 10. Code map

```
src/wildfire/
  config.py         Settings dataclass + settings.json load/save  ← add new settings here
  types.py          Detection / ImageResult / BatchResult
  pipeline.py       run_batch(): per image → detect → annotate → ImageResult
  detect.py         SAHI + YOLO detector
  deepforest_detector.py   DeepForest dead-tree detector
  onnx_detector.py  ONNX detector (your trained model)
  detectors.py      backend registry — add a new model type here
  gps.py            EXIF GPS, DJI RTK .MRK parsing, camera model
  annotate.py       draw_boxes(), grid_density_map()
  llm.py            LM Studio call + the report prompt
  report.py         the PDF (cover, per-image pages, summary + satellite map)
  cv_export.py      labels.json → Custom Vision dataset

src/wildfire/console/     ← the app you see
  server.py         FastAPI: every page route and JSON API   ← the main file
  data.py           reads outputs/ and builds dashboard/scan/detail payloads
  ingest.py         mission-folder scan, flight grouping by capture time
  jobs.py           starts/monitors detection jobs
  worker.py         the detection subprocess itself
  tiles.py          offline map tile download
  desktop.py        the native window (pywebview)
  pages/*.html      one file per page (HTML + its own JS)
  static/console.css  design tokens (colors live in :root) + components
  static/console.js   shared JS: nav, branding, map helpers
```

## 11. How data flows (follow one photo)

```
photo on SD card
  → ingest.scan_source()        reads capture time, ignores non-images
  → jobs.start_detection()      writes a job spec, spawns worker.py
  → worker → pipeline.run_batch()
        → _detection_source()   pre-compress if over preprocess_max_mb
        → detectors             SAHI tiles → YOLO / DeepForest / ONNX → NMS
        → annotate              boxes + density grid images
        → gps                   .MRK (preferred) or EXIF
  → outputs/<run>/batch.json + originals/ annotated/ gridmaps/
  → console data.scan_detail()  → Scan Detail page
  → user reviews → POST /api/scans/{id}/labels → labels.json (+ confirmed images)
  → POST /api/scans/{id}/report → report.build_report() → PDF
  → scripts/export_labels.py → Custom Vision dataset → cloud training → ONNX
```

## 12. Making common changes

| I want to… | Do this |
|------------|---------|
| Change UI text on a page | Edit that page's HTML in `console/pages/` |
| Change colors globally | `console/static/console.css`, the `:root` variables |
| Add a new setting | Add the field to `Settings` in `config.py`, add it to both `config/settings*.json`, add it to `_EDITABLE_SETTINGS` in `server.py` and to the Settings page HTML + its `FIELDS` array |
| Add a new API endpoint | `console/server.py`, inside `create_app()` |
| Add a new detector type | Write a class with `.predict(image) -> list[Detection]`, register it in `detectors.py`, add a `model_sources` entry |
| Change the PDF | `report.py` (`_cover`, `_image_page`, `_summary_page`) |
| Change the AI report wording | `llm.py` → `SYSTEM_PROMPT` |

## 13. Testing and committing

```bash
.venv\Scripts\python.exe -m pytest -q        # 72 tests, must stay green
```

**Commit rules for this repo:**
- **No AI signatures / "Co-Authored-By" lines** in commit messages (we work with
  multiple AI tools; per-model footers make the history confusing).
- Write what changed and *why*, not just what.
- Keep tests green before pushing.

## 14. Gotchas (things that already bit us)

1. **Restart after code changes.** HTML/JS reload per request; Python doesn't.
   Mixing new pages with an old server causes confusing errors.
2. **Never do heavy work inside a request.** Detection runs in a subprocess and
   report generation in a background thread *because* both used to freeze the
   window. Follow that pattern for anything slow.
3. **PDF fonts are Latin-1 only.** Smart quotes/dashes/Chinese become black boxes.
   `report.py` has `_pdf_safe()` — use ASCII in new report strings.
4. **DeepForest takes ~10 s to import.** Use `find_spec` to check availability,
   don't import it just to test presence.
5. **`config/settings.json` is gitignored.** If you change a default, also update
   `config/settings.example.json`.
6. **Big flights are the real test.** 100+ images exposes performance bugs that
   6 images never will (thumbnail loading, report rendering, layout overflow).
7. **Don't add fake features.** We removed a fake "Operator/Admin" chip and an
   "Alerts" placeholder — an honest UI is easier to defend than a decorative one.
