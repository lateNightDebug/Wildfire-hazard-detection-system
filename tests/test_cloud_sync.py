from __future__ import annotations

# imports
import json
import pytest

from src.wildfire import cloud_sync
from src.wildfire.config import Settings


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


def test_test_connection_reports_missing_connection_string(tmp_path):
    settings = _settings(tmp_path, azure_connection_string="")
    ok, message = cloud_sync.test_connection(settings)
    assert ok is False
    assert "connection string" in message.lower()
