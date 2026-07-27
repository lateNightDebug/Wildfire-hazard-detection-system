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


def test_test_connection_reports_missing_connection_string(tmp_path, monkeypatch):
    # The env var takes precedence over the setting, so a developer machine that
    # happens to export it would otherwise make this pass for the wrong reason.
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    settings = _settings(tmp_path, azure_connection_string="")
    ok, message = cloud_sync.test_connection(settings)
    assert ok is False
    assert "connection string" in message.lower()


# ---------------------------------------------------------------- credentials
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
