# Delivery Plan

Tracked against the original requirements table; each item ticked when done.
Repo rule: commits carry no AI signature lines.

## Batch 1

- [x] **Commit all existing work** (40+ files)
- [x] **Show the drone model in Scan Detail** (EXIF Make/Model, verified as DJI L2);
      the processing GPU demoted to a "Processed on" row (older runs lack the field
      and show "not in EXIF"; new runs carry it automatically)
- [x] **Photo thumbnails in map popups** (Dashboard + Map pages)
- [x] **GPS pin map on the PDF summary page** (colored by detection type, with legend)
- [x] **Settings completed**: report/output folder (applies after restart) + a
      "download missing models" button
- [x] **Generic hardware support audit**: the code was already generic
      (any CUDA -> Apple MPS -> CPU); only comments hard-coded an RTX 4090, now fixed
- [x] Full test suite green (61 tests), wrap-up commit

## Batch 2 (2026-07-16)

- [x] **MRK GPS parsing**: DJI RTK Timestamp.MRK (centimetre-grade) preferred over
      EXIF (metre-grade); photo sequence matched automatically; verified on real
      DJI L2 data. The .MRK must sit in the same folder as the photos (importing a
      mission folder as-is already satisfies this)
- [x] **Image pre-compression**: photos over `preprocess_max_mb` (default 2 MB) are
      re-encoded before detection (resolution preserved, quality ladder); adjustable
      in Settings, 0 disables
- [x] **Real satellite basemap (Leaflet + offline Esri tiles)**:
      `scripts/fetch_map_tiles.py --bbox ... --zoom 11 15` fetched once before going
      offline; the Map page switches to the real satellite view (zoom/pan) and falls
      back to the stylized canvas when tiles are missing. 480 tiles cached for the
      Canmore operating area
- [x] **Classified roads + rivers/lakes**: `scripts/fetch_map_overlays.py` pulls
      GeoJSON from OSM (highway classes, waterways, water bodies), rendered offline
      over the satellite map. 2,880 features cached for the area
- [x] **Detection dedup tier 1 (site clustering)**: flagged images cluster into
      "sites" within 40 m; the map marks sites (count badge + max severity + member
      images) and states "N images merged into M sites"

## Batch 3 - fixes from real-device feedback (2026-07-16)

- [x] **Leaflet freeze fixed**: root cause was 2,880 road/water features rendered as
      SVG paths freezing WebView2; switched to the canvas renderer (preferCanvas) -
      SVG path count now zero and navigating away from the map works
- [x] **Dashboard map synced with the Map page**: both use the same site data
      (/api/map-data) and the same Leaflet component, and both switch to real
      satellite imagery when tiles exist
- [x] **Second-level filtering for large scans**: day groups collapse (newest day
      open); continuous flights over 250 images auto-split into part 1/N
      (1,558 images -> 7 parts); each part offers "Select images" to detect a subset
- [x] **In-app area map download**: banner button on the Map page when tiles are
      missing, plus an Offline map card in Settings; bbox inferred from all scan GPS,
      background download with progress
- [x] **Tidy folders**: map_tiles/ -> **map/** (tiles + overlays.geojson);
      models/ = models; outputs/ = run results
- [x] **Removed the droplet-looking logo**

## Batch 4 (2026-07-16)

- [x] **Image zoom in Scan Detail**: cursor-anchored wheel zoom (up to 12x), drag
      pan, double-click reset; zoom keeps working in box-review mode
- [x] **Map markers use hazard-type colors**: flame = red, smoke = orange,
      **dead tree = yellow** (matching the boxes), legend updated; popups keep the
      severity badge alongside
- [x] **Packaging**: `install.bat` (one-click environment + desktop shortcut) +
      `INSTALL.md` (package with `git archive`; recipient installs Python, unzips,
      double-clicks install.bat)

## Batch 5 (2026-07-16)

- [x] **Map no longer paints over the nav bar**: nav z-index raised above Leaflet
      and the map container gets its own stacking context
- [x] **Severity Distribution replaced by Hazard Overview**: detections by type
      (type-colored bars) + review backlog (runs awaiting confirmation, one click to
      Review) + training-set size (confirmed boxes) - three "what to do next" signals
- [x] **Image picker became a full-screen modal**: large thumbnails (170 px grid),
      instant file list, thumbnails **generated per-image on demand + lazy-loaded**
      (no more bulk-generating 100 at once), Esc / backdrop to close

## Batch 6 (2026-07-16)

- [x] **UI freeze during detection fixed (architectural)**: detection moved to a
      separate low-priority subprocess (`console/worker.py`); the server only polls
      the progress file. Measured API responses of 75-187 ms during a live detection
      (previously "Failed to fetch")
- [x] **Mission folder split into analyzed / pending**: fully detected flights
      collapse into a "✓ ANALYZED" section (grayed cards + Re-detect); partially
      analyzed flights show an n/total badge; pending flights stay on top, grouped by day
- [x] **Removed the fake Operator account chip** (there is no account system;
      replaced by a plain Local · Offline indicator)

## Batch 7 (2026-07-16)

- [x] **Removed the Alerts placeholder** (never specified; no fake features)
- [x] **Offline map download dialog**: three modes - around the scanned area
      (z12-16, recommended) / whole Alberta basemap (z8-11, ~376 MB) / custom
      rectangle with zoom range; live tile-count and size estimate before starting,
      a 30,000-tile server-side cap, and progress inside the dialog

## Batch 8 (2026-07-17)

- [x] **User manual (MANUAL.md)**: minimum/recommended specs, installation,
      first-time online setup, standard workflow, data layout, the training loop,
      troubleshooting table, known limits
- [x] **Map time filter**: month / year / all-time dropdown, defaulting to the latest
      month; dates come from **EXIF capture time** (not analysis time); the dashboard
      mini-map follows the same default period

## Batch 9 (2026-07-17)

- [x] **Cleaned leftover test runs**: removed 3 synthetic-image runs
      (console_20260710_122252 / 20260714_145931 / 20260716_203851) and their
      _uploads staging, leaving only the 3 real DJI runs
- [x] **Click a detection to locate it**: clicking any row in the detection list
      zooms the preview onto that box (about 1/3 of the view, capped at 12x) and
      pulses a spotlight ring for 5 s; in review mode it also selects the box - no
      more hunting for a tiny flame by eye

## Batch 10 (2026-07-17)

- [x] **Wording**: "Human-reviewed" -> "Reviewed" across the UI
- [x] **Professional AI analysis**: the LLM input went from a few totals to full
      survey facts (aircraft / capture time / surveyed extent / density / confidence /
      review status / overlap-double-counting caveat / ranked hotspots); the output is
      forced into five sections (Executive Summary / Findings / Priority Locations /
      Recommended Actions / Data Quality & Limitations); the PDF renders section headings

## Batch 11 (2026-07-17)

- [x] **LLM prompt fix**: heading lines contain the title only and the content
      guidance is explicitly marked "never copy into the report" (the model used to
      paste the format instructions into the body)
- [x] **Report image-page cap**: `report_max_image_pages` (default 30), hazard-densest
      images first, with a "top N of M" note on the cover; a 250-image flight no
      longer produces 250 pages
- [x] **Confirmed the AI context does not grow**: the LLM always receives aggregate
      statistics + the top 15 hotspots, independent of flight size
- [x] **Scan Detail performance**: the film strip uses server-side thumbnails
      (~17 KB each, lazy-loaded) instead of full-size annotated JPEGs
- [x] **Flight parts 250 -> 100** (one part = one review sitting)

## Batch 12 (2026-07-17)

- [x] **Wrong image in the PDF's three columns**: `_display_copy` cache keys now hash
      the full path - annotated and gridmaps `_confirmed` files share a stem and were
      overwriting each other, so the "Detections" column showed the grid map
- [x] **Black rectangle instead of the PDF map**: the summary pin map switched to a
      print-friendly light theme (white canvas, light grid, dark-outlined dots)
- [x] **Black box glyphs**: 12 em-dashes in code strings changed to ASCII;
      `_pdf_safe()` maps the LLM's typographic punctuation to ASCII and strips
      anything outside Latin-1
- [x] Verified by regenerating a real report: zero mojibake, clean five-section
      analysis with no prompt leakage, 18 distinct image copies

## Batch 13 (2026-07-17)

- [x] **PDF map upgraded to real satellite imagery**: stitched directly from the
      offline tile cache (highest fully-cached zoom auto-selected), pins projected
      precisely, white chrome boxes keeping legend/attribution readable; falls back to
      the light schematic only where no tiles are cached (and says so). Verified on
      real data: zoom-16 imagery with visible forest, river and trails

## Waiting on external conditions

- [ ] **Plug in the trained dead_tree.onnx** (model still training on Azure; drop it
      into models/ and adjust the preprocessing switches in Settings)
- [ ] **Full-flight shakedown on 100-200 real images**

## Deliberately deferred (roadmap talking points)

- [ ] Detection dedup tiers 2/3 (geometric projection -> ODM orthomosaic)
- [ ] Slimmer reports for 200-image flights + GeoJSON export
- [ ] Pipeline parallelism (switching to the ONNX model is itself the biggest speedup)
- [ ] Verification on real Mac hardware (code already supports MPS/CPU, untested)
- [ ] The Alerts feature itself

## Completed (archive)

- [x] Layer 1 detection (SAHI + YOLO flame/smoke + DeepForest dead-tree proposals)
- [x] Layer 1.5 human review -> labels.json training set (box editor built into the console)
- [x] Layer 2 reporting (LM Studio with graceful fallback + ReportLab PDF,
      timestamped filenames that never overwrite)
- [x] ONNX detector plugin (adapts to Custom Vision / YOLO exports, drop-in)
- [x] Custom Vision dataset export + upload scripts (tiling matched to inference)
- [x] Six-page operations console: Dashboard / Scans / Review / Map / Reports / Settings
- [x] Mission-folder ingest (grouped by day/flight, telemetry files ignored)
- [x] Display-level severity (dead-tree density driven, configurable thresholds)
- [x] Sorted run outputs (originals / annotated / gridmaps)
- [x] Desktop application form (pywebview native window + icon + shortcuts)
- [x] Automated test suite
