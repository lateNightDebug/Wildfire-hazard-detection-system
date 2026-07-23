# AGENTS.md — Context for AI coding sessions

Read this first in any new session, then read `TEAM_GUIDE.md` for depth.
This file is the fast path: what the project is, the rules that must not be
broken, how to run and verify things, and the mistakes already made.

---

## 1. What this project is

A **fully-offline Windows desktop application** that turns drone photos of
forest into a reviewed, GPS-accurate map of wildfire hazards and a PDF field
report. Users are forestry / fire crews working **without internet**.

Three layers:
1. **Detection** — SAHI tiled inference + YOLO11 (flame/smoke) + DeepForest
   (dead-tree candidates) + optional custom ONNX model, on the local GPU.
2. **Human review** — detections are *proposals*; the operator confirms,
   corrects, and draws missed boxes in the console. Confirmed boxes are both
   the report data **and** the training set.
3. **Report** — statistics + local LLM analysis + offline satellite map → PDF.

Cloud is used **only** for model training (Azure Custom Vision) and one-time
map tile downloads (Esri). The app itself never needs the network.

---

## 2. Hard rules (violating these breaks the project or the team's agreements)

1. **No Chinese (CJK) characters anywhere in tracked files** — code, comments,
   docs, tests. Use ASCII escapes if a test needs a non-Latin-1 char.
2. **Commit messages must not contain AI signatures** (no `Co-Authored-By`,
   no "Generated with ..."). The team works with several AI tools and per-model
   footers pollute the history.
3. **Do not touch the `UI/` directory** — that is a teammate's separate Tkinter
   prototype (mock data, its own login screens). It is unrelated to the real
   product in `src/wildfire/console/`. Leave it alone unless asked.
4. **Always use the project venv**: `.venv\Scripts\python.exe`. The system
   Python has none of the dependencies.
5. **Restart the app/server after code changes.** Pages (HTML/JS) are read from
   disk per request, but Python is loaded at startup. Mixing a new page with an
   old server produces confusing errors ("Cannot read properties of undefined").
6. **Never run heavy work inside a web request.** Detection runs in a
   subprocess; report generation runs in a background thread. Both were moved
   there *because* they froze the desktop window. Follow that pattern.
7. **No account system.** This is a single-operator offline tool. There is an
   optional `operator_name` setting for attribution only — no login, password,
   or permissions. (A teammate's prototype has login screens; that is not the
   product direction.)
8. **Do not add cloud dependencies to the runtime.** Offline-first is a client
   requirement, not an implementation detail.

---

## 3. Environment and commands

```powershell
# Run the app (desktop window)
.venv\Scripts\python.exe -m src.wildfire.console --desktop

# Run a dev instance while the desktop app holds port 7861
.venv\Scripts\python.exe -m src.wildfire.console --no-browser --port 7871
#   ...and kill it when done (it is a background python.exe on that port)

# Tests (must stay green)
.venv\Scripts\python.exe -m pytest -q

# Headless detection + report
.venv\Scripts\python.exe -m scripts.run_detection <folder> --pdf
```

Real data to test against:
- `outputs/console_20260716_201807` — 6 real DJI L2 images, 384 dead trees +
  flames, already reviewed (has `labels.json`).
- Mission folder with 1,558 real photos: `F:\Raw\2025\May` (drive may be absent).

---

## 4. Code map

```
src/wildfire/
  config.py       Settings dataclass + settings.json load/save  <- add settings here
  types.py        Detection / ImageResult / BatchResult
  pipeline.py     run_batch(): per image -> detect -> annotate -> ImageResult
  detect.py       SAHI + YOLO detector
  deepforest_detector.py / onnx_detector.py   other detector backends
  detectors.py    backend registry (yolo | deepforest | onnx)
  gps.py          EXIF GPS, DJI RTK .MRK parsing, camera model
  annotate.py     draw_boxes(), grid_density_map()
  llm.py          LM Studio call + report system prompt
  report.py       PDF: cover, per-image pages, summary + offline satellite map
  cv_export.py    labels.json -> Azure Custom Vision dataset
  app.py          legacy Gradio review UI (superseded by the console, still runs)

src/wildfire/console/          <- the actual product UI
  server.py       FastAPI: every route and JSON API          <- main file
  data.py         reads outputs/ -> dashboard/scan/detail payloads
  ingest.py       mission-folder scan, flight grouping by capture time
  jobs.py         starts/monitors detection jobs (subprocess)
  worker.py       the detection subprocess entry point
  tiles.py        offline map tile download (Esri)
  desktop.py      pywebview native window
  pages/*.html    one file per page (HTML + its own inline JS)
  static/console.css   design tokens in :root + components
  static/console.js    shared JS: nav, branding, map helpers

scripts/          run_detection, generate_report, export_labels,
                  upload_to_custom_vision, fetch_map_tiles,
                  fetch_map_overlays, install_desktop_app
branding/         logo + brand.json (UI and PDF read this)
models/ map/ outputs/    weights, offline tiles, run results (all gitignored)
```

## 5. Data flow

```
SD card photos
  -> ingest.scan_source()      images only; capture time; ignores telemetry files
  -> jobs.start_detection()    writes job spec, spawns worker.py (low priority)
  -> pipeline.run_batch()      pre-compress -> SAHI tiles -> detectors -> NMS
                               -> annotate + grid map; GPS from .MRK (preferred) or EXIF
  -> outputs/<run>/batch.json + originals/ annotated/ gridmaps/
  -> console review            -> labels.json (training set) + reviewed_images.json
  -> report.build_report()     stats + LLM analysis + satellite map -> report_<ts>.pdf
  -> scripts/export_labels.py  -> Custom Vision dataset -> cloud training -> ONNX
                               -> drop into models/ -> used offline next run
```

Per-run output layout:
```
outputs/<run>_<timestamp>/
  originals/ annotated/ gridmaps/     three image renditions (+ *_confirmed.jpg)
  batch.json            detections, GPS, stats, batch_info (device, operator...)
  labels.json           reviewer-confirmed boxes = training set
  reviewed_images.json  which images the operator explicitly ticked
  report_<timestamp>.pdf  never overwritten
```

---

## 6. Design decisions that must not be "optimized away"

- **Detections are proposals, review is the accuracy guarantee.** RGB imagery
  physically cannot separate dead wood from bare ground (the signal is in SWIR).
  Do not present AI output as ground truth, and do not remove the review step.
- **Severity (High/Medium/Low) is display-only**, derived from detection type
  and dead-tree density (thresholds in settings). It is never stored in
  batch.json/labels.json and never appears as a data field.
- **Map/box colors encode hazard TYPE**: flame red, smoke orange, dead tree
  yellow. Severity badges are a separate axis; do not merge the two color systems.
- **Detection in a subprocess, reports in a background thread** — see rule 6.
- **Confirmed imagery is rendered once at Save-review**, and report generation
  reuses it (`_confirmed_batch(force_render=False)`). Re-rendering 100 full-res
  frames during a report took 32 s and froze the window.
- **Offline tiles come from Esri** (their terms permit offline export);
  Google/Bing forbid tile caching. Do not switch providers casually.
- **Report image pages are capped** (`report_max_image_pages`, default 30,
  hazard-densest first) so a 100-image flight does not produce a 100-page PDF.
- **LLM input is bounded**: aggregate stats + top-15 hotspots, independent of
  flight size. Do not feed per-image data for every image.

---

## 7. Gotchas already hit (do not repeat)

1. **PDF fonts are Latin-1 only.** Smart quotes/dashes and any CJK become black
   boxes. `report.py` has `_pdf_safe()`; keep new report strings ASCII.
2. **Leaflet with thousands of vector features freezes WebView2.** The map uses
   `preferCanvas: true`. Keep it.
3. **Nav bar vs Leaflet z-index**: the top nav sits above Leaflet panes and
   `.map-wrap` has `isolation: isolate`. Do not lower these.
4. **Grid columns need `min-width: 0`** or a long thumbnail strip stretches the
   page infinitely instead of scrolling inside its card.
5. **`requestAnimationFrame` does not fire in background tabs** — use
   `setTimeout` for layout work that must run regardless of focus.
6. **DeepForest import takes ~10 s.** Use `importlib.util.find_spec` to test
   availability; never import it just to check.
7. **`config/settings.json` is gitignored.** When changing a default, update
   `config/settings.example.json` too.
8. **File-name collisions in caches**: `_display_copy` keys include a hash of the
   full path because `annotated/x_confirmed.jpg` and `gridmaps/x_confirmed.jpg`
   share a stem and silently overwrote each other.
9. **Large flights expose everything.** 100+ images surfaces bugs that 6 images
   never will (thumbnail loads, report time, layout overflow). Test at scale.

---

## 8. Verification habits

- Run `pytest -q` before and after changes; the suite must stay green.
- For UI changes: start a dev instance on port 7871, open the page, and verify
  the actual behavior (the browser tools can execute JS to inspect state).
  Remember to restart after each code change.
- For PDF changes: generate a report from a real run and inspect it
  (`pypdf` is installed in the venv for text extraction).
- Clean up: kill dev servers on 7871, delete scratch folders created under
  `outputs/` (e.g. `_test*`), and reset any settings/branding you changed
  while testing.

---

## 9. Current state and open items

- **Tests**: 72 passing. Modules without coverage: `llm.py`, `jobs.py`,
  `worker.py`, `desktop.py`.
- **Known weak spots**: ~14 silent `except Exception: pass` handlers and no
  unified logging (only `print` + `outputs/<run>/_worker.log`); training-set
  export supports Azure Custom Vision only (no YOLO/COCO); no CI; review UI has
  almost no keyboard shortcuts; `outputs/` grows without an archive feature;
  macOS untested.
- **Waiting on external conditions**: the trained `dead_tree.onnx` from Azure
  (drop into `models/` with its labels file), and a full 100-200 image flight
  shakedown.
- **Deferred by decision**: LiDAR point-cloud processing (the drone produces
  ~2.4 GB `.LDR` files; valuable but weeks of work), dedup tiers 2/3
  (orthomosaic), Docker, cloud sync between users.

See `PLAN.md` for the full history of what was built, and `TEAM_GUIDE.md` for
the human-facing explanation of the project.
