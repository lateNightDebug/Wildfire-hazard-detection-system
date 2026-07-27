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

## Batch 14 - client review feedback (2026-07-23)

- [x] **Hazard-type palette reworked for accessibility**: smoke orange `#F0A500`
      and dead-tree yellow `#FFD700` were only 1.48:1 apart (WCAG 1.4.11 asks 3:1
      for graphical objects) and collapse to the same color under red-green
      colorblindness - the client could not tell them apart. Now flame red
      `#E05555` / smoke slate `#546E7A` / dead tree bone `#D9CDB0`, 3.42:1 on the
      pair that mattered. Rolled through all four definition sites (console.css
      `:root`, console.js `KIND`, annotate.py BGR, report.py RGB) plus the legacy
      Gradio annotator, and fixed a pre-existing drift where detail.html used
      different shades (`#E53935`/`#FB8C00`) than everything else
- [x] **Every hazard type now carries an icon** (flame / smoke puff / bare trunk)
      on map pins, legends and badges, so type survives greyscale printing and any
      color-vision deficiency - color is no longer the only channel (WCAG 1.4.1).
      Icon pins are DOM markers, capped at 300 sites before falling back to canvas
      circles so a huge flight cannot stall WebView2
- [x] **Bone needs an outline**: at 1.58:1 against white it disappears on cards and
      on paper, so thumbnails get an inset ring, map pins a white+dark double halo,
      and the PDF picks the pin ring by fill luminance
- [x] **Double-click a map pin to go fullscreen**: on the Map page the card fills
      the window zoomed to that site (Esc or double-click to exit); on the Dashboard,
      whose map is only 60% wide, it hands off to `/map?site=N&month=...` which opens
      there focused. Leaflet's own double-click-to-zoom is disabled so the two
      gestures stop fighting; a *Fullscreen* button makes the hidden gesture
      discoverable. Verified against the real 14-site May flight

## Batch 15 - report layout + scale (2026-07-23)

- [x] **Report reordered to conclusions-first**: cover -> batch summary ->
      full-page hazard map -> AI analysis -> imagery. Per-image material used to
      sit in the middle, so a reader had to page past 30 photos to reach the
      numbers and the map they opened the report for
- [x] **One page per image replaced with a three-tier layout**: full detail pages
      for the worst `report_detail_pages` (default 4), a gallery contact sheet at
      8 per page for the rest of the top `report_max_image_pages`, and an index
      table row for EVERY image. Measured on the real 58-image run: **33 pages ->
      15**, and it now documents all 58 images instead of only 30
- [x] **Hazard map promoted to its own landscape page** (9.4in wide). Squeezed
      under the stats table it had ~2.9in of height and was unreadable; alone it
      is the single most useful page for a crew deciding where to drive
- [x] **Marker icon limit raised to 500** after measuring: 500 DOM icon pins build
      in 24 ms and pan in 1 ms, and the canvas fallback still catches anything
      bigger. A month can hold 10k+ photos, so 300 was too tight

## Batch 16 - scale fix + the first frontend guard (2026-07-25)

- [x] **cluster_sites no longer freezes the window on a big month**: it compared
      every point against every existing site, which is fine for a 60-photo run
      and 7.5 s for a 10k-photo month - inside a web request. Sites are now
      indexed into a grid of radius-sized cells so each point only checks the 3x3
      cells that could hold a match. **7.47 s -> 0.045 s (166x)** at 10k points,
      20k in 0.08 s. Output is byte-identical: a test pins it against the old
      linear scan across seven geometries (dense overlap, nothing merging, all
      points identical, high latitude, across the equator, near the antimeridian)
- [x] **First test coverage of the frontend contract** (`test_frontend_contract.py`,
      16 tests). The console has no build step, so renaming a helper in console.js
      passed all 72 tests and broke the page at runtime. These parse each page's
      inline JS and assert every function it calls is defined somewhere - by the
      page, by console.js, or by the browser - plus that pages load console.js
      before their own script, and that no page reintroduces a retired hazard hex.
      Verified by mutation: renaming a helper, reintroducing #FFD700, and deleting
      a page each turn the suite red
- [x] **Caught a real leftover while writing it**: `detail.html` still fell back to
      the retired `#FFD700` for unknown labels; now falls back to `KIND.deadtree.color`
- [x] Suite: **72 -> 90 tests**, all green

## Batch 17 - merged Tessa; scoped cloud credentials (2026-07-26)

- [x] **Merged `Tessa`**: optional Azure Blob sync plus her console accessibility
      pass. Two strands of accessibility work met in console.css and both kept -
      hers raises text/severity contrast (`--muted-2/-3`, `--faint`, `--red`,
      `--amber`, `--green-2`, plus `label for=` and `img alt`), mine separates the
      hazard-TYPE palette and adds per-type icons. Six files conflicted; each was
      resolved as "both sides", not "pick a side"
- [x] **Fixed a silent conflict the merge exposed**: `applyBrandingColors()` writes
      `--green-2` from `branding/brand.json` at runtime, so it was overwriting her
      darkened green with the old lighter one - her contrast fix had no visible
      effect at all. brand.json now carries the darker value and the function says
      it wins over console.css
- [x] **Cloud credentials can now be scoped**: the app accepts a portal **Blob SAS
      URL** (container-level or account-level) as well as the original account-key
      connection string. A SAS reaches one container, can be issued per device,
      expires, and is revocable alone; the account key it replaces grants
      read/write/delete over the entire storage account forever. *Test connection*
      reports which kind is in use and warns on the account key
- [x] `_ensure_container()` tolerates a scoped token that can neither probe nor
      create the container - that is the intended setup, not a failure
- [x] **Confirmed no account system is needed** even though sync spans machines:
      Azure Storage is the identity layer. Recorded in AGENTS.md hard rule 7
- [x] Suite **90 -> 102** tests. Verified the app still starts and serves all 44
      routes with `azure-storage-blob` absent, so offline installs are unaffected

## Batch 18 - results-only cloud sync (2026-07-26)

- [x] **Cloud sync now shares findings, not imagery.** `cloud_upload_mode`
      defaults to `"results"`: one gzipped JSON per run holding detections, GPS,
      statistics and confirmed labels. Measured across the five real runs,
      **2,056 MB on disk becomes 48 KB uploaded** - about 12 bytes per detection,
      so the 1,558-image May mission is roughly 1 MB. PDFs are excluded (55.8 MB
      for one run on its own). Full-folder upload is kept as an opt-in backup mode
- [x] **Round trip verified on real data**: exported all five runs, imported them
      into a separate output root as a second machine, and the map came back
      identical - 67 flagged images to 14 sites on both sides, dashboard totals
      matching, zero broken image URLs
- [x] **No local paths leave the machine**: `results_payload()` strips absolute
      paths and sends each image's file name only, so `_rel_url()` returns None
      and the UI's existing "no image" path takes over
- [x] **Imported runs are marked results-only**: the Scan Detail page names the
      machine it came from, explains that the photos stayed there, replaces the
      thumbnail strip with labelled chips (no 404 image icons), and hides review,
      re-upload and mark-reviewed, which all need a frame
- [x] **Reports adapt**: `has_imagery()` drops the per-image pages and gallery when
      a run has no frames, so an imported run produces a 7-page report (cover,
      summary, hazard map, AI analysis, full index) instead of 15 with 8 pages of
      placeholder dashes. Also covers runs whose folders were deleted to free disk
- [x] **Ownership instead of conflict resolution**: `source.machine` is the host
      name, not the compute device - `batch_info["device"]` is the GPU and two
      laptops can share one. Imports are read-only and never overwrite a local run
      without an explicit flag
- [x] Scans page gained a **Cloud** card listing container contents with one-click
      import; hidden entirely when cloud sync is off
- [x] Suite **102 -> 111** tests

## Batch 19 - severity honesty, upload and layout fixes (2026-07-27)

- [x] **Severity thresholds recalibrated against real imagery**: frames hold
      27..102 dead trees (median 60) but High started at 10, so all 67 frames,
      5 runs and 14 sites graded High and the badge meant nothing. Now 80 / 45
      (~p85 / ~p22): the same data gives 1 High + 4 Medium runs and sites split
      6 / 6 / 2. The ladder test now passes thresholds explicitly instead of
      asserting the constants
- [x] **A run badge is the worst image, and now says so**: `severity_mix` and
      `flame_images` ride alongside it, with a stacked bar on the Scans table and
      Dashboard. The 58-image run reads "flame in 6 images - 14 high, 28 medium,
      16 low" instead of a bare HIGH implying 58 bad frames
- [x] **Duplicate site coordinates were a display bug, not clustering**: the
      pairs are 49 m and 77 m apart, correctly separated by the 40 m dedup, but
      printed at 3 decimals (~111 m lat / ~70 m lon here). Now 5 decimals
- [x] **Upload could only ever take one image**: each visit to the file dialog
      replaced the selection, and the dropzone hid once anything was picked so
      there was no way back. Picking now accumulates and de-duplicates; the whole
      page accepts a drop; Mission Folder carries the upload button
- [x] **Mission-folder scan shows real progress**: 12.2 s of silence for 21,200
      images, since every image costs an EXIF read. `scan_source()` reports
      progress and the page polls it beside the blocking request
- [x] **GPU model no longer presented as identity**: `batch_info["machine"]`
      records the host name; reports and "Processed on" use it, and the graphics
      card is gone from the PDF entirely
- [x] Layout: detector status shrunk from the top card to one line; Settings
      moved from a fixed 2-column grid (which left half the page empty) to
      balanced CSS columns; Scan Detail's overloaded header split in two
- [x] Docstrings trimmed 109 lines -> 62, none now longer than its own function
- [x] Suite **112 -> 113** tests

## Batch 20 - open a site, not a run (2026-07-27)

- [x] **Map sites open their own images**: a hazard site is a physical location,
      but clicking one opened the entire flight that happened to include it. The
      popup now links to `?images=a|b|c`, which narrows the viewer, thumbnails
      and detection table to the frames taken there, with a banner and a "show
      the whole run" way back. Review is disabled while filtered, since saving
      would write labels for only the visible subset
- [x] **Scan Detail sidebar leads with the current image**: it described the run
      while the operator flipped through 58 frames one at a time, so the column
      they were watching never moved. "This image" now shows that frame's own
      severity, review state, per-type counts, GPS, altitude and capture time,
      and it redraws with the viewer. Run-level facts moved into a collapsed
      "Whole run" fold whose header still carries the badge and mix bar
- [x] Per-frame grading uses thresholds sent by the server, so it cannot drift
      from Settings the way a hardcoded copy would
- [x] **Mission folder day groups start collapsed**: the newest group auto-opened
      and unrolled 108 flights on load
- [x] Dashboard Recent Scans rows restructured into three tiers (when + verdict,
      what was found, then the id) instead of one wrapping line

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
