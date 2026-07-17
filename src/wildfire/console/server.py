"""Operations console (FastAPI): dashboard / scans / scan detail, fully offline.

Serves the three console pages plus a small JSON API over the existing pipeline:
run folders under outputs/ are the source of truth (batch.json / labels.json /
report.pdf), uploads start real detection jobs in a background thread, and the
review step links out to the Gradio annotator (port 7860).

Run:  python -m src.wildfire.console    (opens http://127.0.0.1:7861)
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import PROJECT_ROOT, Settings, load_settings
from ..imageio_utils import SUPPORTED_EXTS
from ..types import BatchResult, Detection
from . import data, ingest
from .jobs import JobManager

PKG_DIR = Path(__file__).resolve().parent
PAGES = PKG_DIR / "pages"
REVIEW_APP_URL = "http://127.0.0.1:7860"  # the Gradio Layer-1.5 annotator
REVIEW_PORT = 7860


class SourceBody(BaseModel):
    folder: str


class SessionBody(BaseModel):
    session: str
    names: list[str] = []  # optional subset of image names within the session


class TilesBody(BaseModel):
    zmin: int = 12
    zmax: int = 16


class LabelsBody(BaseModel):
    # image NAME -> confirmed boxes [{"xyxy": [x1,y1,x2,y2], "class": "Dead Tree"}]
    labels: dict[str, list[dict]]


class SettingsBody(BaseModel):
    values: dict = {}  # whitelisted scalar settings
    model_enabled: dict[str, bool] = {}  # model_sources key -> enabled


# Settings the UI may edit, with a light validator each.
_EDITABLE_SETTINGS: dict = {
    "lmstudio_url": str,
    "lmstudio_model": str,
    "language": str,
    "source_dir": str,
    "output_dir": str,  # /outputs mount is bound at startup -> needs app restart
    "conf_threshold": lambda v: max(0.01, min(0.99, float(v))),
    "slice_size": lambda v: max(256, min(4096, int(v))),
    "preprocess_max_mb": lambda v: max(0.0, min(50.0, float(v))),
    "overlap_ratio": lambda v: max(0.0, min(0.9, float(v))),
    "perform_standard_pred": bool,
    "severity_deadtrees_high": lambda v: max(0.1, float(v)),
    "severity_deadtrees_medium": lambda v: max(0.1, float(v)),
    "onnx_input_size": lambda v: max(64, min(4096, int(v))),
    "onnx_normalize": lambda v: v if v in ("0-255", "0-1", "imagenet") else "0-255",
    "onnx_channel_order": lambda v: v if v in ("RGB", "BGR") else "RGB",
    "onnx_nms_iou": lambda v: max(0.05, min(0.95, float(v))),
}


def _review_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", REVIEW_PORT), timeout=0.3):
            return True
    except OSError:
        return False


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(name or "upload").name)


def _confirmed_batch(batch: BatchResult, labels: dict, out_dir: Path) -> BatchResult:
    """Rebuild a batch from human-confirmed labels.json boxes (original coords)."""
    from ..annotate import draw_boxes, grid_density_map
    from ..imageio_utils import load_rgb_uint8
    from ..risk import batch_stats

    by_image: dict[str, list[dict]] = {}
    for rec in labels.get("labels", []):
        if isinstance(rec, dict) and rec.get("confirmed") is not False and "xyxy" in rec:
            by_image.setdefault(str(rec.get("image")), []).append(rec)

    new_images = []
    for im in batch.images:
        dets = []
        for rec in by_image.get(im.path, []):
            cls = str(rec.get("class") or rec.get("proposed_class") or "Dead Tree")
            dets.append(Detection(cls_name=cls.lower().replace(" ", "_"), display=cls,
                                  score=1.0, xyxy=tuple(float(v) for v in rec["xyxy"])))
        annotated_path, density_path = im.annotated_path, im.density_path
        try:
            src = im.path if Path(im.path).exists() else (im.orig_display_path or im.path)
            bgr = cv2.cvtColor(load_rgb_uint8(src), cv2.COLOR_RGB2BGR)
            stem = Path(im.path).stem
            (out_dir / "annotated").mkdir(parents=True, exist_ok=True)
            (out_dir / "gridmaps").mkdir(parents=True, exist_ok=True)
            annotated_path = str(out_dir / "annotated" / f"{stem}_confirmed.jpg")
            cv2.imwrite(annotated_path, draw_boxes(bgr, dets), [cv2.IMWRITE_JPEG_QUALITY, 88])
            density_path = str(out_dir / "gridmaps" / f"{stem}_confirmed.jpg")
            cv2.imwrite(density_path, grid_density_map(bgr, dets), [cv2.IMWRITE_JPEG_QUALITY, 88])
        except Exception:
            pass
        new_images.append(replace(im, detections=dets, flagged=bool(dets),
                                  annotated_path=annotated_path, density_path=density_path))
    info = dict(batch.batch_info)
    info["review"] = "human-confirmed (labels.json)"
    return BatchResult(images=new_images, stats=batch_stats(new_images), batch_info=info)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Wildfire Hazard Detection Console", docs_url=None, redoc_url=None)
    # An injected Settings (tests) is never persisted to config/settings.json.
    app.state.persist_settings = settings is None
    app.state.settings = settings or load_settings()
    app.state.jobs = JobManager()
    app.state.settings.ensure_dirs()
    app.state.source_cache = {}  # folder -> (signature, scan result)
    app.state.review_proc = None

    def _scan_cached(folder: str) -> dict:
        """Scan the mission folder, reusing the result while nothing changed."""
        sig = ingest.folder_signature(Path(folder))
        cached = app.state.source_cache.get(folder)
        if cached and cached[0] == sig:
            return cached[1]
        result = ingest.scan_source(folder)
        app.state.source_cache[folder] = (sig, result)
        return result

    def _source_payload(folder: str) -> dict:
        result = _scan_cached(folder)
        sessions = ingest.group_sessions(result["images"])
        thumb_dir = app.state.settings.output_path / "_thumbs"
        done = data.detected_paths(app.state.settings)
        out_sessions = []
        for s in sessions:
            thumb = ingest.make_thumb(s["paths"][len(s["paths"]) // 2], thumb_dir)
            analyzed = sum(1 for p in s["paths"] if p in done)
            out_sessions.append({k: v for k, v in s.items() if k != "paths"} | {
                "thumb_url": f"/outputs/_thumbs/{thumb.name}" if thumb else None,
                "analyzed": analyzed,
            })
        return {"folder": folder, "exists": True, "images": len(result["images"]),
                "ignored": result["ignored"], "sessions": out_sessions}

    app.mount("/static", StaticFiles(directory=PKG_DIR / "static"), name="static")
    app.mount("/outputs", StaticFiles(directory=app.state.settings.output_path), name="outputs")

    # ------------------------------------------------------------- pages
    @app.get("/")
    def page_dashboard():
        return FileResponse(PAGES / "dashboard.html")

    @app.get("/scans")
    def page_scans():
        return FileResponse(PAGES / "scans.html")

    @app.get("/scans/{run_id}")
    def page_detail(run_id: str):
        return FileResponse(PAGES / "detail.html")

    @app.get("/review")
    def page_review():
        return FileResponse(PAGES / "review.html")

    @app.get("/map")
    def page_map():
        return FileResponse(PAGES / "map.html")

    @app.get("/reports")
    def page_reports():
        return FileResponse(PAGES / "reports.html")

    @app.get("/settings")
    def page_settings():
        return FileResponse(PAGES / "settings.html")

    # ------------------------------------------------------------- api
    @app.get("/api/summary")
    def api_summary():
        return data.dashboard_summary(app.state.settings)

    @app.get("/api/scans")
    def api_scans():
        scans = data.discover_scans(app.state.settings)
        jobs = {j.id: j for j in app.state.jobs.active()}
        done_ids = {s["id"] for s in scans}
        rows = []
        for j in app.state.jobs.all():  # queued/running/failed jobs first
            if j.id in done_ids:
                continue
            rows.append({"id": j.id, "status": "processing" if j.state in ("queued", "running") else "failed",
                         "job": j.to_dict(), "date": "", "time": "", "images": j.total,
                         "detections_by_type": {}, "total_detections": 0, "severity": None,
                         "reviewed": False, "has_report": False, "report_url": None, "gps": None,
                         "created": j.created})
        for s in scans:
            if s["id"] in jobs:  # run dir exists but job still writing
                s = {**s, "status": "processing", "job": jobs[s["id"]].to_dict()}
            rows.append(s)
        rows.sort(key=lambda s: s.get("created") or "", reverse=True)
        return {"scans": rows, "review_url": REVIEW_APP_URL}

    @app.get("/api/scans/{run_id}")
    def api_scan_detail(run_id: str):
        detail = data.scan_detail(run_id, app.state.settings)
        if detail is None:
            raise HTTPException(404, f"run '{run_id}' not found")
        detail["review_url"] = REVIEW_APP_URL
        return detail

    @app.get("/api/models")
    def api_models():
        return {"models": data.model_status(app.state.settings)}

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str):
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "unknown job")
        return job.to_dict()

    # ------------------------------------------------------- map
    def _tiles_root() -> Path:
        return app.state.settings._resolve(app.state.settings.map_tiles_dir)

    @app.get("/api/map-data")
    def api_map_data(radius: float = 40.0):
        return data.map_data(app.state.settings, radius_m=max(5.0, min(500.0, radius)))

    @app.get("/api/map-info")
    def api_map_info():
        root = _tiles_root()
        zooms = sorted(int(p.name) for p in root.glob("[0-9]*") if p.is_dir()) if root.is_dir() else []
        attribution = ""
        attr_file = root / "attribution.txt"
        if attr_file.exists():
            attribution = attr_file.read_text(encoding="utf-8").strip()
        overlays = root / "overlays.geojson"
        return {"tiles": bool(zooms), "min_zoom": zooms[0] if zooms else None,
                "max_zoom": zooms[-1] if zooms else None,
                "attribution": attribution or "Offline imagery tiles",
                "overlays": overlays.exists()}

    @app.get("/tiles/{z}/{x}/{y}")
    def api_tile(z: int, x: int, y: int):
        tile = _tiles_root() / str(z) / str(x) / f"{y}.jpg"
        if not tile.exists():
            raise HTTPException(404, "tile not cached")
        return FileResponse(tile, media_type="image/jpeg")

    @app.get("/map-overlays.geojson")
    def api_overlays():
        f = _tiles_root() / "overlays.geojson"
        if not f.exists():
            raise HTTPException(404, "no overlays downloaded")
        return FileResponse(f, media_type="application/geo+json")

    @app.post("/api/map/download")
    def api_map_download(body: TilesBody):
        """Download tiles for the area covered by all scans (internet required)."""
        from . import tiles as tiles_mod

        job = getattr(app.state, "tile_job", None)
        if job and job.get("state") == "running":
            return JSONResponse(job, status_code=409)
        pts = [tuple(s["gps"]) for s in data.discover_scans(app.state.settings) if s["gps"]]
        bbox = tiles_mod.bbox_from_points(pts)
        if bbox is None:
            raise HTTPException(400, "no GPS-tagged scans yet — cannot infer the area")
        zmin, zmax = max(3, body.zmin), min(17, max(body.zmin, body.zmax))
        job = {"state": "running", "done": 0, "total": len(tiles_mod.tile_list(bbox, zmin, zmax)),
               "failed": 0, "bbox": list(bbox)}
        app.state.tile_job = job

        def work() -> None:
            try:
                def cb(done: int, total: int, failed: int) -> None:
                    job.update(done=done, total=total, failed=failed)

                result = tiles_mod.download_tiles(bbox, zmin, zmax, _tiles_root(), progress=cb)
                job.update(state="done", **result)
            except Exception as e:
                job.update(state="error", error=f"{type(e).__name__}: {e}")

        import threading

        threading.Thread(target=work, name="tile-download", daemon=True).start()
        return JSONResponse(job, status_code=202)

    @app.get("/api/map/download/status")
    def api_map_download_status():
        return getattr(app.state, "tile_job", None) or {"state": "idle"}

    # ------------------------------------------------------- reports
    @app.get("/api/reports")
    def api_reports():
        settings: Settings = app.state.settings
        by_run = {s["id"]: s for s in data.discover_scans(settings)}
        reports = []
        for run_id, s in by_run.items():
            run_dir = settings.output_path / run_id
            for pdf in run_dir.glob("report*.pdf"):
                st = pdf.stat()
                reports.append({
                    "run_id": run_id, "file": pdf.name,
                    "url": data._rel_url(str(pdf), settings.output_path),
                    "size_kb": st.st_size // 1024,
                    "created": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "severity": s["severity"], "reviewed": s["reviewed"],
                    "detections_by_type": s["detections_by_type"], "images": s["images"],
                })
        # filename carries the generation timestamp — decisive when mtimes tie
        reports.sort(key=lambda r: (r["created"], r["file"]), reverse=True)
        return {"reports": reports}

    # ------------------------------------------------------- settings
    @app.get("/api/settings")
    def api_get_settings():
        s: Settings = app.state.settings
        return {"values": {k: getattr(s, k) for k in _EDITABLE_SETTINGS},
                "models": data.model_status(s),
                "output_dir": str(s.output_path)}

    @app.post("/api/settings")
    def api_set_settings(body: SettingsBody):
        s: Settings = app.state.settings
        applied = {}
        for key, value in body.values.items():
            caster = _EDITABLE_SETTINGS.get(key)
            if caster is None:
                continue  # unknown/readonly keys are ignored, not an error
            try:
                casted = caster(value)
            except (TypeError, ValueError):
                raise HTTPException(400, f"invalid value for {key}: {value!r}")
            setattr(s, key, casted)
            applied[key] = casted
        for key, enabled in body.model_enabled.items():
            for src in s.model_sources:
                if src.key == key:
                    src.enabled = bool(enabled)
                    applied[f"model:{key}"] = bool(enabled)
        if app.state.persist_settings:
            s.save()
        # Loaded detectors baked in the old thresholds/toggles — rebuild next job.
        app.state.jobs.reset_detectors()
        return {"applied": applied, "models": data.model_status(s)}

    @app.post("/api/lmstudio-test")
    def api_lmstudio_test():
        from ..llm import health_check

        up, ids, err = health_check(app.state.settings.lmstudio_url)
        return {"up": up, "models": ids or [], "error": err}

    @app.post("/api/models/download")
    def api_models_download():
        from ..models import ensure_yolo_sources

        logs: list[str] = []
        paths = ensure_yolo_sources(app.state.settings, log=logs.append)
        logs.append(f"YOLO models present: {[p.name for p in paths] or 'none'}")
        return {"log": logs, "models": data.model_status(app.state.settings)}

    # ------------------------------------------------------- mission folder
    @app.get("/api/source")
    def api_source():
        folder = app.state.settings.source_dir
        if not folder:
            return {"folder": "", "exists": False, "sessions": []}
        if not Path(folder).is_dir():
            return {"folder": folder, "exists": False, "sessions": []}
        return _source_payload(folder)

    @app.post("/api/source")
    def api_set_source(body: SourceBody):
        folder = body.folder.strip().strip('"')
        if not folder or not Path(folder).is_dir():
            raise HTTPException(400, f"folder not found: {folder or '(empty)'}")
        s: Settings = app.state.settings
        s.source_dir = folder
        if app.state.persist_settings:
            s.save()  # persists so the console reopens on this folder
        return _source_payload(folder)

    def _find_session(session_id: str) -> dict:
        folder = app.state.settings.source_dir
        if not folder or not Path(folder).is_dir():
            raise HTTPException(400, "no mission folder configured")
        sessions = ingest.group_sessions(_scan_cached(folder)["images"])
        match = next((s for s in sessions if s["id"] == session_id), None)
        if match is None:
            raise HTTPException(404, f"session '{session_id}' not found (folder changed?)")
        return match

    @app.get("/api/source/session/{session_id}")
    def api_session_images(session_id: str):
        """Image names of one flight — instant. Thumbnails load lazily per image
        via /api/source/thumb/... so opening the picker never blocks."""
        match = _find_session(session_id)
        return {"session": session_id,
                "images": [{"name": n} for n in match["names"]]}

    @app.get("/api/source/thumb/{session_id}/{name}")
    def api_session_thumb(session_id: str, name: str):
        match = _find_session(session_id)
        try:
            idx = match["names"].index(name)
        except ValueError:
            raise HTTPException(404, "image not in this session")
        thumb = ingest.make_thumb(match["paths"][idx],
                                  app.state.settings.output_path / "_thumbs", max_px=300)
        if thumb is None:
            raise HTTPException(404, "unreadable image")
        return FileResponse(thumb, media_type="image/jpeg")

    @app.post("/api/detect-session")
    def api_detect_session(body: SessionBody):
        match = _find_session(body.session)
        paths = match["paths"]
        if body.names:  # subset picked in the UI
            wanted = set(body.names)
            paths = [p for n, p in zip(match["names"], match["paths"]) if n in wanted]
            if not paths:
                raise HTTPException(400, "none of the selected images are in this session")
        job = app.state.jobs.start_detection([Path(p) for p in paths], app.state.settings)
        return JSONResponse({"job": job.to_dict(), "images": len(paths)}, status_code=202)

    # ------------------------------------------------------- review app
    @app.get("/api/review/status")
    def api_review_status():
        return {"running": _review_running(), "url": REVIEW_APP_URL}

    @app.post("/api/review/start")
    def api_review_start():
        if _review_running():
            return {"running": True, "url": REVIEW_APP_URL}
        proc = app.state.review_proc
        if proc is None or proc.poll() is not None:
            log_path = app.state.settings.output_path / "_review_app.log"
            env = dict(os.environ, WILDFIRE_NO_BROWSER="1")
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            app.state.review_proc = subprocess.Popen(
                [sys.executable, "-m", "src.wildfire.app"],
                cwd=str(PROJECT_ROOT), env=env, creationflags=flags,
                stdout=open(log_path, "ab"), stderr=subprocess.STDOUT,
            )
        return {"running": False, "starting": True, "url": REVIEW_APP_URL}

    @app.post("/api/detect")
    async def api_detect(files: list[UploadFile]):
        settings: Settings = app.state.settings
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        staging = settings.output_path / "_uploads" / ts
        staging.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for f in files:
            name = _safe_name(f.filename)
            if Path(name).suffix.lower() not in SUPPORTED_EXTS:
                continue
            dest = staging / name
            dest.write_bytes(await f.read())
            saved.append(dest)
        if not saved:
            raise HTTPException(400, "no supported images in the upload (JPG/TIFF/PNG)")
        job = app.state.jobs.start_detection(saved, settings)
        return JSONResponse({"job": job.to_dict(), "images": len(saved)}, status_code=202)

    @app.post("/api/scans/{run_id}/labels")
    def api_save_labels(run_id: str, body: LabelsBody):
        """Persist reviewer-confirmed boxes (the training set) and rebuild the
        confirmed annotated/grid images. Boxes arrive in ORIGINAL pixel coords."""
        settings: Settings = app.state.settings
        run_dir = settings.output_path / Path(run_id).name
        batch_file = run_dir / "batch.json"
        if not batch_file.exists():
            raise HTTPException(404, f"run '{run_id}' has no batch.json")
        batch = BatchResult.from_dict(json.loads(batch_file.read_text(encoding="utf-8")))
        path_by_name = {im.name: im.path for im in batch.images}

        records = []
        for name, boxes in body.labels.items():
            image_path = path_by_name.get(name)
            if image_path is None:
                raise HTTPException(400, f"unknown image '{name}' in this run")
            for b in boxes:
                xyxy = [round(float(v), 1) for v in b.get("xyxy", [])]
                if len(xyxy) != 4 or xyxy[2] <= xyxy[0] or xyxy[3] <= xyxy[1]:
                    continue
                records.append({"image": image_path, "xyxy": xyxy,
                                "class": str(b.get("class") or "Dead Tree")})
        labels = {"labels": records}
        (run_dir / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
        _confirmed_batch(batch, labels, run_dir)  # refresh confirmed imagery
        detail = data.scan_detail(Path(run_id).name, settings)
        return {"saved": len(records), "detail": detail}

    @app.post("/api/scans/{run_id}/report")
    def api_generate_report(run_id: str):
        settings: Settings = app.state.settings
        run_dir = settings.output_path / Path(run_id).name
        batch_file = run_dir / "batch.json"
        if not batch_file.exists():
            raise HTTPException(404, f"run '{run_id}' has no batch.json")
        from ..llm import generate_analysis, resolve_model_id
        from ..report import build_report, build_summary_text, timestamped_report_path

        batch = BatchResult.from_dict(json.loads(batch_file.read_text(encoding="utf-8")))
        labels_file = run_dir / "labels.json"
        reviewed = labels_file.exists()
        if reviewed:
            labels = json.loads(labels_file.read_text(encoding="utf-8"))
            batch = _confirmed_batch(batch, labels, run_dir)

        ai_text = None
        model, _ = resolve_model_id(settings.lmstudio_url, settings.lmstudio_model)
        if model:
            ai_text, _ = generate_analysis(build_summary_text(batch), settings.lmstudio_url, model)

        pdf = build_report(batch, timestamped_report_path(run_dir), ai_text=ai_text)
        note = "" if reviewed else "Generated from UNREVIEWED proposals — confirm the boxes first for a reviewed report."
        if not model:
            note = (note + " LM Studio offline — AI analysis omitted.").strip()
        return {"report_url": data._rel_url(str(pdf), settings.output_path),
                "reviewed": reviewed, "note": note}

    return app
