# Contributors

Who built what. Recorded by **contribution**, not by line count — line counts
reward whoever refactored a file last, which is the opposite of what this file
is for.

Everything here is checkable with `git log` and `git blame`. Where the git
record is misleading, that is called out rather than glossed over.

---

## Tessa Rae Feyres — `Tizzerai` / `TessaFey`

**Cloud sync (`src/wildfire/cloud_sync.py`, `tests/test_cloud_sync.py`)**

Designed and implemented the original module: the Azure client bootstrap, the
sync marker, the upload exclusion rules, and the whole-folder upload path. Also
wrote the test suite's `FakeContainer` double and the upload/exclusion/
incremental tests.

Three of those decisions carried the whole feature afterwards:

- **Lazy import.** `azure-storage-blob` is imported inside the functions that
  need it, so the application serves all its routes with the package absent —
  the offline-first requirement survives an optional cloud feature. The project
  venv still does not have the SDK installed and the suite passes.
- **The `FakeContainer` seam.** Faking the container rather than the SDK is why
  the cloud tests run with no network and no credentials, and why every test
  added later could reuse the same doubles.
- **The `size:mtime` marker.** Re-syncing a run after a review pass uploads only
  the files that changed, rather than the folder again.

Her functions, still hers today — the file carries section banners marking the
boundaries:

    CloudSyncError, SyncResult, _require_azure, _load_marker, _save_marker,
    sync_status, _iter_run_files, upload_run, _content_type

`_read_credential`, `_container_client` and `test_connection` began as hers and
were extended for SAS credentials. The results-only sync added later is built on
top of her client and marker, not in place of them.

**Console accessibility.** A contrast pass across the interface — `--muted-2`,
`--muted-3`, `--faint`, `--red` and `--amber` all darkened for readability, plus
`for=` on form labels and `alt` text on thumbnails. Those values are still the
ones in `console.css` today.

**`UI Skeleton`** (`60102ca`) — an early Tkinter interface prototype. Removed
later by team decision when the project settled on a single web console; the
commit remains in history.

---

## Luna McCormick — `lateNightDebug`

**Repository initial commit** (`7c101db`).

**Brand identity** — the SAIT logo (`branding/logo.png`) and the brand blue
`#0072BC`, which the console, the PDF header and the application icon are all
drawn from.

> **Correction to the git record.** The logo was brought onto `main` with
> `git checkout <branch> -- branding/logo.png` rather than a merge, so `git log`
> credits the commit author instead of Luna. The asset is hers. The same applies
> to the brand colour, which arrived as a value edit rather than a merge.

---

## Tianao — `Tianao0110`

Detection pipeline (SAHI tiling, YOLO11 and DeepForest backends, ONNX plugin),
the operations console, GPS and RTK `.MRK` handling, the PDF report builder,
offline map tiles, the results-only cloud sync and SAS credential support,
macOS support, and the test suite.

---

## Notes for anyone joining

- **Attribution survives a rewrite.** `git blame` shows who wrote each line
  today; `git log --follow` shows who wrote it first. Both matter, and they
  disagree on any file that has been extended.
- **Cherry-picking a file loses its author.** Use `git merge`, or record the
  attribution here, as above.
- **If your email is not on your GitHub account**, your commits show a plain
  name with no avatar and do not count toward your contribution graph. Add the
  address you commit with under GitHub → Settings → Emails; existing commits are
  credited retroactively.
