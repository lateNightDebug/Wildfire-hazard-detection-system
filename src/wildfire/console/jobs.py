"""Background detection jobs: each job runs in its own LOW-PRIORITY subprocess
(src.wildfire.console.worker), never inside the server process — heavy
inference used to starve the UI event loop and every page went "Failed to
fetch" while a job ran. The manager just spawns the worker and polls the
run folder's _progress.json.

Each job writes a normal run folder (outputs/console_<ts>/ with batch.json),
so finished jobs show up through the regular discover_scans path.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import PROJECT_ROOT, Settings


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

    # ------------------------------------------------------------- queries
    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def active(self) -> list[Job]:
        return [j for j in self._jobs.values() if j.state in ("queued", "running")]

    def all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    def reset_detectors(self) -> None:
        """No-op since workers are per-job processes; kept for API compatibility."""

    # ------------------------------------------------------------- detection
    def start_detection(self, image_paths: list[Path], settings: Settings) -> Job:
        """Spawn a worker process for these images and monitor it."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"console_{ts}"
        job = Job(id=run_id, total=len(image_paths))
        with self._lock:
            self._jobs[run_id] = job

        run_dir = settings.output_path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        spec_path = run_dir / "_job.json"
        spec_path.write_text(json.dumps({
            "paths": [str(p) for p in image_paths],
            "run_dir": str(run_dir),
            "batch_label": run_id,
            "settings": asdict(settings),
        }), encoding="utf-8")

        # Below-normal priority keeps the console (and the operator's machine)
        # responsive while torch saturates the cores.
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                 | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
        log = open(run_dir / "_worker.log", "ab")
        proc = subprocess.Popen(
            [sys.executable, "-m", "src.wildfire.console.worker", str(spec_path)],
            cwd=str(PROJECT_ROOT), creationflags=flags,
            stdout=log, stderr=subprocess.STDOUT,
        )

        def monitor() -> None:
            progress_file = run_dir / "_progress.json"
            job.state = "running"
            while True:
                try:
                    p = json.loads(progress_file.read_text(encoding="utf-8"))
                    job.done = int(p.get("done", job.done))
                    job.total = int(p.get("total", job.total)) or job.total
                    job.current = p.get("current", "")
                    if p.get("state") == "error":
                        job.error = p.get("error")
                except Exception:
                    pass  # not written yet / mid-swap
                rc = proc.poll()
                if rc is not None:
                    if job.error is None and rc != 0:
                        job.error = f"worker exited with code {rc} (see {run_dir.name}/_worker.log)"
                    job.state = "error" if job.error else "done"
                    job.current = ""
                    log.close()
                    return
                time.sleep(1.0)

        threading.Thread(target=monitor, name=f"monitor-{run_id}", daemon=True).start()
        return job
