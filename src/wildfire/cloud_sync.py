from __future__ import annotations
# imports

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .config import Settings

MARKER_NAME = ".cloud_sync.json"

# Internal/working files that should never be uploaded — bookkeeping
# artifacts, not "processed data."
_EXCLUDE_NAMES = {MARKER_NAME, "_job.json", "_progress.json", "_worker.log"}

# Folder names to skip while walking a run directory. "_cache" holds the
# per-run detector-input cache — not part of the deliverable.
_EXCLUDE_DIR_NAMES = {"_cache"}

ProgressFn = Optional[Callable[[int, int, str], None]]


class CloudSyncError(RuntimeError):
    """error handling"""


@dataclass
class SyncResult:
    run_id: str
    container: str
    uploaded: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_uploaded: int = 0
    errors: list[str] = field(default_factory=list)
    synced_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "container": self.container,
            "uploaded": self.uploaded, "skipped": self.skipped, "failed": self.failed,
            "bytes_uploaded": self.bytes_uploaded, "errors": self.errors,
            "synced_at": self.synced_at,
        }


# setup for cloud storage
def _require_azure():
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings  # noqa: F401
    except ImportError as e:  # pragma: no cover - exercised only w/o the dep
        raise CloudSyncError(
            "azure-storage-blob is not installed. Run: "
            "pip install azure-storage-blob"
        ) from e
    return BlobServiceClient, ContentSettings


def credential_kind(credential: str) -> str:
    """Classify a credential so the UI can warn about over-broad ones.

    'sas'         - a Shared Access Signature: scoped to what the admin granted
                    and expires on its own. What we recommend.
    'account_key' - the storage account master key: full read/write/DELETE over
                    EVERY container in the account, and it never expires.
    """
    c = (credential or "").strip()
    if not c:
        return "none"
    if "SharedAccessSignature=" in c or "sig=" in c:
        return "sas"
    if "AccountKey=" in c:
        return "account_key"
    return "unknown"


def _read_credential(settings: Settings) -> str:
    import os

    return (os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            or settings.azure_connection_string or "").strip()


def _ensure_container(container, name: str) -> None:
    """Make sure the container is there, without demanding account-level rights.

    A container-scoped SAS - the credential we want people to use - can neither
    create containers nor always probe for their existence; both come back as a
    403. That is the intended setup, not a failure: the admin creates the
    container once and hands out a narrow token. So a probe we are not allowed
    to make is treated as "it exists", and a container that genuinely is not
    there surfaces with a clear message from test_connection() or on the first
    upload rather than blocking the client here.
    """
    try:
        if container.exists():
            return
    except Exception:
        return  # not permitted to look - assume the admin created it
    try:
        container.create_container()
    except Exception:
        return  # cannot create with this token either; let the real call report


def _container_client(settings: Settings):
    """Container client from any of the three credential shapes people paste.

    1. Account-key connection string  DefaultEndpointsProtocol=...;AccountKey=...
    2. SAS connection string          BlobEndpoint=...;SharedAccessSignature=...
    3. SAS URL from the portal        https://acct.blob.core.windows.net/name?sv=...

    Form 3 is what the Azure portal's "Generate SAS" button actually gives you,
    so accepting it directly saves the operator from hand-building a connection
    string - which is where this normally goes wrong.
    """
    credential = _read_credential(settings)
    if not credential:
        raise CloudSyncError(
            "No Azure credential configured. Paste a SAS URL or connection string "
            "in Settings -> Cloud sync, or set the AZURE_STORAGE_CONNECTION_STRING "
            "environment variable."
        )
    BlobServiceClient, _ = _require_azure()
    container_name = settings.azure_container or "wildfire-runs"
    try:
        if credential.startswith(("http://", "https://")):
            container = _container_from_url(credential, container_name)
        else:
            service = BlobServiceClient.from_connection_string(credential)
            container = service.get_container_client(container_name)
        _ensure_container(container, container_name)
        return container
    except CloudSyncError:
        raise
    except Exception as e:
        raise CloudSyncError(f"Azure connection failed: {type(e).__name__}: {e}") from e


def _container_from_url(url: str, container_name: str):
    """Build a client from a portal SAS URL.

    The portal hands out two shapes: a container URL that already names the
    container (.../wildfire-runs?sv=...) and an account URL that does not
    (...blob.core.windows.net/?sv=...). Only the second needs the configured
    container name appended.
    """
    from urllib.parse import urlparse

    from azure.storage.blob import BlobServiceClient, ContainerClient

    base, _, query = url.partition("?")
    path = urlparse(base).path.strip("/")
    if path:  # the container is already in the URL; its name wins
        return ContainerClient.from_container_url(url)
    account_url = base.rstrip("/")
    service = BlobServiceClient(account_url=account_url, credential=query or None)
    return service.get_container_client(container_name)


# test connection
def test_connection(settings: Settings) -> tuple[bool, str]:
    """Quick round-trip check for the Settings page's "Test connection" button.

    Reports which kind of credential is in use, because "it works" is not the
    whole story: an account key works perfectly and is still the wrong thing to
    copy onto several field laptops.
    """
    kind = credential_kind(_read_credential(settings))
    try:
        container = _container_client(settings)
        container.get_container_properties()
    except CloudSyncError as e:
        return False, str(e)
    except Exception as e:  # pragma: no cover - defensive
        return False, f"{type(e).__name__}: {e}"

    msg = f"Connected to container '{container.container_name}'"
    if kind == "account_key":
        msg += (" - using an ACCOUNT KEY, which grants full read/write/delete over "
                "the whole storage account and never expires. Prefer a SAS token "
                "scoped to this container.")
    elif kind == "sas":
        msg += " (SAS token)"
    return True, msg


# marker
def _load_marker(run_dir: Path) -> dict:
    f = run_dir / MARKER_NAME
    if not f.exists():
        return {"files": {}}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"files": {}}


def _save_marker(run_dir: Path, marker: dict) -> None:
    (run_dir / MARKER_NAME).write_text(json.dumps(marker, indent=2), encoding="utf-8")


def sync_status(run_dir: Path) -> dict:
    """Status for the Scans / Scan Detail pages: has this run been synced, and when."""
    marker = _load_marker(run_dir)
    if not marker.get("synced_at"):
        return {"synced": False}
    return {
        "synced": True,
        "synced_at": marker.get("synced_at"),
        "container": marker.get("container"),
        "file_count": len(marker.get("files", {})),
    }


# uploadin files
def _iter_run_files(run_dir: Path):
    for path in sorted(run_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.name in _EXCLUDE_NAMES:
            continue
        if any(part in _EXCLUDE_DIR_NAMES for part in path.relative_to(run_dir).parts):
            continue
        yield path

# running upload of files
def upload_run(run_dir: Path, run_id: str, settings: Settings,
                progress: ProgressFn = None) -> SyncResult:
    if not settings.cloud_enabled:
        raise CloudSyncError("Cloud sync is disabled in Settings.")
    _, ContentSettings = _require_azure()
    container = _container_client(settings)
    container_name = settings.azure_container or "wildfire-runs"

    marker = _load_marker(run_dir)
    files_state: dict = marker.get("files", {})
    result = SyncResult(run_id=run_id, container=container_name)

    all_files = list(_iter_run_files(run_dir))
    total = len(all_files)
    for i, path in enumerate(all_files):
        rel = path.relative_to(run_dir).as_posix()
        st = path.stat()
        fingerprint = f"{st.st_size}:{int(st.st_mtime)}"
        if files_state.get(rel) == fingerprint:
            result.skipped += 1
            if progress:
                progress(i + 1, total, rel)
            continue
        blob_name = f"{run_id}/{rel}"
        content_type = _content_type(path)
        try:
            with path.open("rb") as fh:
                container.upload_blob(
                    name=blob_name, data=fh, overwrite=True,
                    content_settings=ContentSettings(content_type=content_type) if content_type else None,
                )
            files_state[rel] = fingerprint
            result.uploaded += 1
            result.bytes_uploaded += st.st_size
        except Exception as e:
            result.failed += 1
            result.errors.append(f"{rel}: {type(e).__name__}: {e}")
        if progress:
            progress(i + 1, total, rel)

    marker["files"] = files_state
    marker["container"] = container_name
    if result.failed == 0:
        marker["synced_at"] = result.synced_at
    _save_marker(run_dir, marker)
    return result


def _content_type(path: Path) -> Optional[str]:
    return {
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(path.suffix.lower())