"""Tests for the optional Azure Blob cloud sync.

AUTHORSHIP
    Everything from here to the "added later" banner - the FakeContainer double,
    the fixtures, and the upload/exclusion/incremental tests - is by
    **Tessa Rae Feyres**. Faking the container instead of reaching for the real
    SDK is why this suite runs offline and why the later tests could reuse the
    same seams; the venv does not even have azure-storage-blob installed.
"""

from __future__ import annotations

import json

import pytest

from src.wildfire import cloud_sync
from src.wildfire.config import Settings


# ===========================================================================
# Tessa Rae Feyres - test doubles, fixtures, and the upload-path tests
# ===========================================================================
class FakeContentSettings:
    def __init__(self, content_type=None):
        self.content_type = content_type
class FakeContainer:
    def __init__(self):
        self.uploads: list[str] = []

    def upload_blob(self, name, data, overwrite=True, content_settings=None):
        data.read()
        self.uploads.append(name)



def _settings(tmp_path, **overrides) -> Settings:
    s = Settings(output_dir=str(tmp_path), cloud_enabled=True,
                 azure_connection_string="fake", azure_container="wildfire-runs")
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _make_run(tmp_path):
    run_dir = tmp_path / "console_20260101_000000"
    (run_dir / "originals").mkdir(parents=True)
    (run_dir / "_cache").mkdir()
    (run_dir / "batch.json").write_text(json.dumps({"images": []}), encoding="utf-8")
    (run_dir / "originals" / "img1.jpg").write_bytes(b"fake-jpeg-bytes")
    (run_dir / "_cache" / "img1_det.jpg").write_bytes(b"should-be-excluded")
    (run_dir / "_job.json").write_text("{}", encoding="utf-8")
    return run_dir


def test_sync_status_no_marker(tmp_path):
    run_dir = _make_run(tmp_path)
    assert cloud_sync.sync_status(run_dir) == {"synced": False}


def test_upload_run_requires_cloud_enabled(tmp_path):
    run_dir = _make_run(tmp_path)
    settings = _settings(tmp_path, cloud_enabled=False)
    with pytest.raises(cloud_sync.CloudSyncError):
        cloud_sync.upload_run(run_dir, run_dir.name, settings)


def test_upload_run_uploads_and_excludes_internal_files(tmp_path, monkeypatch):
    run_dir = _make_run(tmp_path)
    settings = _settings(tmp_path)
    fake = FakeContainer()
    monkeypatch.setattr(cloud_sync, "_require_azure", lambda: (None, FakeContentSettings))
    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: fake)

    result = cloud_sync.upload_run(run_dir, run_dir.name, settings)

    assert result.uploaded == 2
    assert result.skipped == 0
    assert result.failed == 0
    assert set(fake.uploads) == {
        f"{run_dir.name}/batch.json",
        f"{run_dir.name}/originals/img1.jpg",
    }
    assert not any("_cache" in n or "_job.json" in n for n in fake.uploads)
    status = cloud_sync.sync_status(run_dir)
    assert status["synced"] is True
    assert status["file_count"] == 2


def test_upload_run_skips_unchanged_files_on_second_pass(tmp_path, monkeypatch):
    run_dir = _make_run(tmp_path)
    settings = _settings(tmp_path)
    fake = FakeContainer()
    monkeypatch.setattr(cloud_sync, "_require_azure", lambda: (None, FakeContentSettings))
    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: fake)

    cloud_sync.upload_run(run_dir, run_dir.name, settings)
    fake.uploads.clear()
    second = cloud_sync.upload_run(run_dir, run_dir.name, settings)

    assert second.uploaded == 0
    assert second.skipped == 2
    assert fake.uploads == []


def test_upload_run_reuploads_changed_file(tmp_path, monkeypatch):
    run_dir = _make_run(tmp_path)
    settings = _settings(tmp_path)
    fake = FakeContainer()
    monkeypatch.setattr(cloud_sync, "_require_azure", lambda: (None, FakeContentSettings))
    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: fake)

    cloud_sync.upload_run(run_dir, run_dir.name, settings)
    fake.uploads.clear()
    (run_dir / "labels.json").write_text(json.dumps({"img1.jpg": []}), encoding="utf-8")
    second = cloud_sync.upload_run(run_dir, run_dir.name, settings)

    assert second.uploaded == 1
    assert second.skipped == 2
    assert fake.uploads == [f"{run_dir.name}/labels.json"]


def test_test_connection_reports_missing_connection_string(tmp_path, monkeypatch):
    # The env var takes precedence over the setting, so a developer machine that
    # happens to export it would otherwise make this pass for the wrong reason.
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    settings = _settings(tmp_path, azure_connection_string="")
    ok, message = cloud_sync.test_connection(settings)
    assert ok is False
    assert "connection string" in message.lower()


# ===========================================================================
# Added later - credentials and results-only sync. Everything below reuses the
# FakeContainer and fixtures above rather than introducing its own.
# ===========================================================================
# A SAS token scoped to one container is the credential we want people to use.
# An account key also works and is what the portal offers first, so the code has
# to accept both, tell them apart, and say so.

def _install_fake_azure(monkeypatch) -> dict:
    """Stand in for azure.storage.blob so credential handling is testable.

    The venv deliberately does not have the SDK - the app must run without it -
    so these tests inject a module rather than requiring the real one.
    """
    import sys
    import types
    from urllib.parse import urlparse

    seen: dict = {}

    class FakeContainerClient:
        def __init__(self, name):
            self.container_name = name

        @classmethod
        def from_container_url(cls, url):
            seen["from_container_url"] = url
            return cls(urlparse(url.partition("?")[0]).path.strip("/"))

    class FakeBlobServiceClient:
        def __init__(self, account_url=None, credential=None):
            seen["account_url"] = account_url
            seen["credential"] = credential

        @classmethod
        def from_connection_string(cls, conn):
            seen["conn_str"] = conn
            return cls()

        def get_container_client(self, name):
            seen["container_asked"] = name
            return FakeContainerClient(name)

    blob = types.ModuleType("azure.storage.blob")
    blob.BlobServiceClient = FakeBlobServiceClient
    blob.ContainerClient = FakeContainerClient
    blob.ContentSettings = FakeContentSettings
    monkeypatch.setitem(sys.modules, "azure", types.ModuleType("azure"))
    monkeypatch.setitem(sys.modules, "azure.storage", types.ModuleType("azure.storage"))
    monkeypatch.setitem(sys.modules, "azure.storage.blob", blob)
    monkeypatch.setattr(cloud_sync, "_ensure_container", lambda c, n: None)
    return seen


def test_credential_kind_tells_sas_from_account_key():
    assert cloud_sync.credential_kind("") == "none"
    assert cloud_sync.credential_kind(
        "DefaultEndpointsProtocol=https;AccountName=a;AccountKey=abc==") == "account_key"
    assert cloud_sync.credential_kind(
        "BlobEndpoint=https://a.blob.core.windows.net/;SharedAccessSignature=sv=2024") == "sas"
    assert cloud_sync.credential_kind(
        "https://a.blob.core.windows.net/runs?sv=2024&sig=xyz") == "sas"


def test_sas_url_naming_a_container_wins_over_the_setting(tmp_path, monkeypatch):
    """A portal Blob SAS URL already points at one container; honour it."""
    seen = _install_fake_azure(monkeypatch)
    settings = _settings(
        tmp_path, azure_container="ignored-name",
        azure_connection_string="https://acct.blob.core.windows.net/wildfire-runs?sv=2024&sig=x")
    container = cloud_sync._container_client(settings)
    assert container.container_name == "wildfire-runs"
    assert seen["from_container_url"].startswith("https://acct.blob.core.windows.net/")


def test_account_level_sas_url_uses_the_configured_container(tmp_path, monkeypatch):
    """An account-scoped SAS URL names no container, so the setting supplies it."""
    seen = _install_fake_azure(monkeypatch)
    settings = _settings(
        tmp_path, azure_container="wildfire-runs",
        azure_connection_string="https://acct.blob.core.windows.net/?sv=2024&sig=x")
    container = cloud_sync._container_client(settings)
    assert container.container_name == "wildfire-runs"
    assert seen["account_url"] == "https://acct.blob.core.windows.net"
    assert seen["credential"] == "sv=2024&sig=x"


def test_connection_string_still_works(tmp_path, monkeypatch):
    """The original account-key path must keep working - people already use it."""
    seen = _install_fake_azure(monkeypatch)
    settings = _settings(tmp_path, azure_container="wildfire-runs",
                         azure_connection_string="DefaultEndpointsProtocol=https;AccountKey=k==")
    cloud_sync._container_client(settings)
    assert seen["conn_str"].startswith("DefaultEndpointsProtocol=")
    assert seen["container_asked"] == "wildfire-runs"


def test_ensure_container_tolerates_a_scoped_token(monkeypatch):
    """A container SAS can neither probe nor create; that must not be fatal."""
    class CannotProbe:
        container_name = "wildfire-runs"

        def exists(self):
            raise RuntimeError("403 AuthorizationFailure")

        def create_container(self):
            raise AssertionError("must not try to create when the probe is denied")

    cloud_sync._ensure_container(CannotProbe(), "wildfire-runs")  # must not raise

    class CannotCreate:
        def exists(self):
            return False

        def create_container(self):
            raise RuntimeError("403 AuthorizationFailure")

    cloud_sync._ensure_container(CannotCreate(), "wildfire-runs")  # must not raise


def test_test_connection_warns_when_an_account_key_is_used(tmp_path, monkeypatch):
    """Connecting with the master key succeeds - the operator still needs telling."""
    _install_fake_azure(monkeypatch)
    monkeypatch.setattr(cloud_sync, "_container_client",
                        lambda s: type("C", (), {"container_name": "wildfire-runs",
                                                 "get_container_properties": lambda self: None})())
    key = _settings(tmp_path, azure_connection_string="AccountName=a;AccountKey=abc==")
    ok, message = cloud_sync.test_connection(key)
    assert ok is True
    assert "account key" in message.lower() and "sas" in message.lower()

    sas = _settings(tmp_path,
                    azure_connection_string="https://a.blob.core.windows.net/runs?sv=1&sig=x")
    ok, message = cloud_sync.test_connection(sas)
    assert ok is True
    assert "sas" in message.lower() and "account key" not in message.lower()


# ------------------------------------------------------------- results sync
# Results mode uploads findings, not imagery: measured on real runs that is
# 2,056 MB against 48 KB. These pin the round trip and the two properties that
# make it safe - no local paths escape, and an import never clobbers a run this
# machine produced.

def _make_full_run(tmp_path):
    """A run with imagery, labels and a report, i.e. what results mode must strip."""
    run_dir = tmp_path / "console_20260101_000000"
    (run_dir / "originals").mkdir(parents=True)
    (run_dir / "annotated").mkdir()
    img = "D:\\Sait\\outputs\\console_20260101_000000\\originals\\DJI_0001.JPG"
    (run_dir / "batch.json").write_text(json.dumps({
        "batch_info": {"device": "FIELD-LAPTOP-1", "operator": "M. Reyes",
                       "generated_at": "2026-01-01T00:00:00",
                       "output_dir": "D:\\Sait\\outputs"},
        "stats": {"images_processed": 1, "total_detections": 2},
        "images": [{
            "path": img, "name": "DJI_0001.JPG", "width": 5280, "height": 3956,
            "gps": [51.1134, -115.3835], "altitude": 1387.2,
            "timestamp": "2025:05:02 13:48:22", "camera": "DJI FC3582", "flagged": True,
            "orig_display_path": img,
            "annotated_path": "D:\\Sait\\outputs\\...\\annotated\\DJI_0001.JPG",
            "density_path": "D:\\Sait\\outputs\\...\\gridmaps\\DJI_0001.JPG",
            "detections": [
                {"cls_name": "dead", "display": "Dead Tree", "score": 0.93,
                 "xyxy": [10, 20, 60, 90]},
                {"cls_name": "fire", "display": "Flame", "score": 0.71,
                 "xyxy": [200, 210, 260, 280]},
            ],
        }],
    }), encoding="utf-8")
    (run_dir / "labels.json").write_text(json.dumps({
        "labels": [{"image": img, "xyxy": [10, 20, 60, 90], "class": "Dead Tree"}]
    }), encoding="utf-8")
    (run_dir / "reviewed_images.json").write_text(
        json.dumps({"reviewed": ["DJI_0001.JPG"]}), encoding="utf-8")
    (run_dir / "originals" / "DJI_0001.JPG").write_bytes(b"x" * 4096)
    (run_dir / "report_20260101_000000.pdf").write_bytes(b"%PDF-1.4 fake")
    return run_dir


def test_results_payload_carries_findings_and_no_local_paths(tmp_path):
    run_dir = _make_full_run(tmp_path)
    payload = cloud_sync.results_payload(run_dir, run_dir.name)

    blob = json.dumps(payload)
    assert "D:\\\\Sait" not in blob and "D:\\Sait" not in blob, "a local path escaped"
    assert "originals" not in blob and ".pdf" not in blob.lower()

    assert payload["results_only"] is True
    # `machine` identifies the owner; `device` is the GPU and two laptops can
    # share one, so it must not be what ownership keys on.
    assert payload["source"]["machine"]
    assert payload["source"]["device"] == "FIELD-LAPTOP-1"
    im = payload["images"][0]
    assert im["name"] == "DJI_0001.JPG" and im["path"] == "DJI_0001.JPG"
    assert im["gps"] == [51.1134, -115.3835] and im["altitude"] == 1387.2
    assert len(im["detections"]) == 2
    # labels travel keyed by image NAME so they match again after the trip
    assert payload["labels"][0]["image"] == "DJI_0001.JPG"
    assert payload["reviewed_images"] == ["DJI_0001.JPG"]


def test_results_payload_is_tiny_next_to_the_run(tmp_path):
    """The whole point: findings are orders of magnitude smaller than imagery."""
    import gzip

    run_dir = _make_full_run(tmp_path)
    on_disk = sum(f.stat().st_size for f in run_dir.rglob("*") if f.is_file())
    packed = gzip.compress(
        json.dumps(cloud_sync.results_payload(run_dir, run_dir.name)).encode("utf-8"), 9)
    assert len(packed) < on_disk / 5
    assert len(packed) < 2000  # one image, two detections


def test_upload_results_sends_one_blob_and_marks_the_run(tmp_path, monkeypatch):
    run_dir = _make_full_run(tmp_path)
    settings = _settings(tmp_path)
    fake = FakeContainer()
    monkeypatch.setattr(cloud_sync, "_require_azure", lambda: (None, FakeContentSettings))
    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: fake)

    result = cloud_sync.upload_results(run_dir, run_dir.name, settings)
    assert fake.uploads == [f"{run_dir.name}/results.json.gz"]
    assert result.uploaded == 1 and result.failed == 0
    marker = json.loads((run_dir / cloud_sync.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["mode"] == "results" and marker["synced_at"]


def test_results_round_trip_rebuilds_a_readable_run(tmp_path, monkeypatch):
    """Export, import into a different output root, and read it back with the
    same loaders the console uses - otherwise the far side sees nothing."""
    import gzip

    from src.wildfire.console import data as cdata
    from src.wildfire.types import BatchResult

    run_dir = _make_full_run(tmp_path)
    packed = gzip.compress(
        json.dumps(cloud_sync.results_payload(run_dir, run_dir.name)).encode("utf-8"), 9)

    class OneBlob:
        container_name = "wildfire-runs"

        def download_blob(self, name):
            assert name == f"{run_dir.name}/results.json.gz"
            return type("D", (), {"readall": lambda self: packed})()

    other_root = tmp_path / "other-machine"
    other_root.mkdir()
    remote_settings = _settings(tmp_path, output_dir=str(other_root))
    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: OneBlob())

    dest = cloud_sync.import_results(run_dir.name, remote_settings)
    assert dest == other_root / run_dir.name

    # parses with the real loader
    batch = BatchResult.from_dict(
        json.loads((dest / "batch.json").read_text(encoding="utf-8")))
    assert len(batch.images) == 1
    assert batch.images[0].gps == (51.1134, -115.3835)
    assert [d.display for d in batch.images[0].detections] == ["Dead Tree", "Flame"]

    # and the console's own detail view reports it as results-only
    detail = cdata.scan_detail(run_dir.name, remote_settings)
    assert detail["results_only"] is True
    assert detail["synced_from"]["machine"]
    assert detail["synced_from"]["device"] == "FIELD-LAPTOP-1"
    got = detail["images_detail"][0]
    assert got["original_url"] is None and got["annotated_url"] is None
    assert got["confirmed"], "confirmed labels should survive the re-keying"
    assert got["reviewed_by_user"] is True


def test_import_refuses_to_overwrite_a_local_run(tmp_path, monkeypatch):
    """An import has no imagery; silently replacing a local run would delete the
    photos and keep only the numbers."""
    import gzip

    run_dir = _make_full_run(tmp_path)
    packed = gzip.compress(
        json.dumps(cloud_sync.results_payload(run_dir, run_dir.name)).encode("utf-8"), 9)

    class OneBlob:
        container_name = "wildfire-runs"

        def download_blob(self, name):
            return type("D", (), {"readall": lambda self: packed})()

    settings = _settings(tmp_path)  # output_dir already holds this run
    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: OneBlob())

    with pytest.raises(cloud_sync.CloudSyncError, match="already exists"):
        cloud_sync.import_results(run_dir.name, settings)
    assert (run_dir / "originals" / "DJI_0001.JPG").exists()  # untouched

    cloud_sync.import_results(run_dir.name, settings, overwrite=True)  # explicit is fine


def test_import_rejects_a_traversing_run_id(tmp_path):
    settings = _settings(tmp_path)
    for bad in ("../escape", "a/b", "..\\escape"):
        with pytest.raises(cloud_sync.CloudSyncError):
            cloud_sync.import_results(bad, settings)


def test_list_remote_runs_skips_non_results_blobs(tmp_path, monkeypatch):
    from datetime import datetime as _dt

    class Blob:
        def __init__(self, name, size, when):
            self.name, self.size, self.last_modified = name, size, when

    class Listing:
        container_name = "wildfire-runs"

        def list_blobs(self):
            return [
                Blob("run_a/results.json.gz", 4096, _dt(2026, 1, 2)),
                Blob("run_b/results.json.gz", 2048, _dt(2026, 1, 3)),
                Blob("run_c/originals/DJI_0001.JPG", 9_000_000, _dt(2026, 1, 1)),
                Blob("run_c/batch.json", 1024, _dt(2026, 1, 1)),
            ]

    monkeypatch.setattr(cloud_sync, "_container_client", lambda s: Listing())
    runs = cloud_sync.list_remote_runs(_settings(tmp_path))
    assert [r["run_id"] for r in runs] == ["run_b", "run_a"]  # newest first
    assert runs[1]["size"] == 4096
