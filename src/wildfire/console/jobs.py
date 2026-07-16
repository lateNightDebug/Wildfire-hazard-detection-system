"""Background detection jobs for the console: uploads -> run_batch in a thread.

One JobManager per server process. Detectors are built lazily on the first job
(model loading takes ~30s with DeepForest) and reused after that, same as the
Gradio app. Each job writes a normal run folder (outputs/console_<ts>/ with
batch.json), so finished jobs show up through the regular discover_scans path.
"""

from __future__ import annotations

import json
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import Settings


@dataclass
class Job:
    id: str  # equals the run folder name
    state: str = "queued"  # queued | running | done | error
    total: int = 0
    done: int = 0
    current: str = ""
    error: Optional[str] = None
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {"id": self.id, "state": self.state, "total": self.total, "done": self.done,
                "current": self.current, "error": self.error, "created": self.created,
                "progress": round(self.done / self.total, 3) if self.total else 0.0}


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._detectors = None
        self._det_lock = threading.Lock()

    # ------------------------------------------------------------- queries
    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def active(self) -> list[Job]:
        return [j for j in self._jobs.values() if j.state in ("queued", "running")]

    def all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    # ------------------------------------------------------------- detection
    def _get_detectors(self, settings: Settings, job: Job):
        with self._det_lock:
            if self._detectors is None:
                job.current = "loading detection models..."
                from ..detectors import build_detectors

                self._detectors = build_detectors(settings, log=lambda m: print(m))
            return self._detectors

    def reset_detectors(self) -> None:
        """Drop cached detectors so the next job rebuilds with fresh settings."""
        with self._det_lock:
            self._detectors = None

    def start_detection(self, image_paths: list[Path], settings: Settings) -> Job:
        """Kick off a detection run over already-saved image files."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"console_{ts}"
        job = Job(id=run_id, total=len(image_paths))
        with self._lock:
            self._jobs[run_id] = job

        def work() -> None:
            try:
                job.state = "running"
                detectors = self._get_detectors(settings, job)
                from ..pipeline import run_batch

                def cb(cur: int, tot: int, name: str) -> None:
                    job.done, job.total, job.current = cur, tot, name

                run_dir = settings.output_path / run_id
                batch = run_batch([str(p) for p in image_paths], detectors, settings,
                                  progress=cb, out_dir=run_dir, batch_label=run_id)
                (run_dir / "batch.json").write_text(
                    json.dumps(batch.to_dict(), indent=2), encoding="utf-8")
                job.state = "done"
                job.current = ""
            except Exception as e:
                job.state = "error"
                job.error = f"{type(e).__name__}: {e}"
                traceback.print_exc()

        threading.Thread(target=work, name=f"detect-{run_id}", daemon=True).start()
        return job
