"""Pinned download tests with a fake Hub; no real models or network access."""

import builtins
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import urllib.request

import pytest

from scripts import prepare_embedding_models as cli
from src import embedding_model_preparation as preparation
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER


@pytest.fixture
def fake_hub(monkeypatch):
    calls = []

    def reject_network(*args, **kwargs):
        raise AssertionError("Download tests must not access the real Hub")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    monkeypatch.setattr("src.config.secrets.get_api_key", lambda provider: None)

    def snapshot_download(**kwargs):
        calls.append(kwargs)
        for relative_path in kwargs["allow_patterns"]:
            artifact = Path(kwargs["local_dir"]) / relative_path
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(f"{kwargs['repo_id']}/{relative_path}".encode())
        print("Fake Hub progress")
        return str(kwargs["local_dir"])

    hub = SimpleNamespace(snapshot_download=snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    return hub, calls


def test_download_requests_only_pinned_identities_and_required_artifacts(tmp_path, fake_hub):
    _, calls = fake_hub

    result = preparation.download_embedding_models(tmp_path)

    assert len(calls) == 2
    assert [(call["repo_id"], call["revision"]) for call in calls] == [
        (HARRIER_MODEL.model_id, HARRIER_MODEL.revision),
        (BM25_MODEL.model_id, BM25_MODEL.revision),
    ]
    assert calls[0]["allow_patterns"] == sorted(
        set(HARRIER_MODEL.required_artifacts) | set(HARRIER_TOKENIZER.required_artifacts)
    )
    assert calls[1]["allow_patterns"] == list(BM25_MODEL.required_artifacts)
    assert result.staging_dir.parent == tmp_path / ".preparation"
    assert not (tmp_path / "manifest.json").exists()
    for call, snapshot in zip(calls, result.snapshots, strict=True):
        assert call["repo_type"] == "model"
        assert call["token"] is False
        assert call["local_files_only"] is False
        assert call["local_dir"] == result.staging_dir / snapshot.relative_path
        assert call["revision"] in snapshot.relative_path
        assert all((call["local_dir"] / path).is_file() for path in snapshot.required_artifacts)
        assert not (call["local_dir"] / "sentence_bert_config.json").exists()


def test_different_tokenizer_revision_is_downloaded_separately(tmp_path, fake_hub, monkeypatch):
    _, calls = fake_hub
    tokenizer = replace(HARRIER_TOKENIZER, revision="a" * 40)
    monkeypatch.setattr(preparation, "HARRIER_TOKENIZER", tokenizer)

    result = preparation.download_embedding_models(tmp_path)

    assert len(result.snapshots) == 3
    assert calls[1]["revision"] == tokenizer.revision
    assert calls[1]["allow_patterns"] == list(tokenizer.required_artifacts)


@pytest.mark.parametrize("json_output", [False, True])
def test_download_cli_keeps_active_inventory_and_reports_only_candidates(
    tmp_path, fake_hub, monkeypatch, capsys, json_output,
):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    active_manifest = tmp_path / "manifest.json"
    active_artifact = tmp_path / "active/model.safetensors"
    active_artifact.parent.mkdir()
    active_manifest.write_bytes(b"existing manifest")
    active_artifact.write_bytes(b"existing weights")
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in (active_manifest, active_artifact)]

    assert cli.main(["--download"] + (["--json"] if json_output else [])) == 0

    output = capsys.readouterr()
    assert "Fake Hub progress" not in output.out
    assert "Fake Hub progress" in output.err
    if json_output:
        payload = json.loads(output.out)
        assert payload["operation"] == "download"
        assert payload["status"] == "heruntergeladen"
        assert Path(payload["staging_dir"]).parent == tmp_path / ".preparation"
        assert len(payload["snapshots"]) == 2
        assert "manifest_sha256" not in payload
    else:
        assert "Vorbereitungsordner:" in output.out
        assert HARRIER_MODEL.revision in output.out
        assert BM25_MODEL.revision in output.out
    assert "noch nicht geprueft oder freigegeben" in output.out
    assert before == [(path.read_bytes(), path.stat().st_mtime_ns) for path in (active_manifest, active_artifact)]


@pytest.mark.parametrize("json_output", [False, True])
def test_failed_download_does_not_publish_or_report_success(
    tmp_path, fake_hub, monkeypatch, capsys, json_output,
):
    hub, calls = fake_hub
    original = hub.snapshot_download

    def fail_second_snapshot(**kwargs):
        if kwargs["repo_id"] == BM25_MODEL.model_id:
            raise OSError("provider request failed")
        return original(**kwargs)

    hub.snapshot_download = fail_second_snapshot
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(b"active manifest")

    assert cli.main(["--download"] + (["--json"] if json_output else [])) == 1

    output = capsys.readouterr()
    if json_output:
        payload = json.loads(output.out)
        assert payload["status"] == "fehlgeschlagen"
        assert payload["operation"] == "download"
    else:
        assert output.out == ""
    assert "Traceback" not in output.out + output.err
    assert "heruntergeladen" not in output.out
    assert manifest_path.read_bytes() == b"active manifest"
    assert len(calls) == 1
    assert len(list((tmp_path / ".preparation").iterdir())) == 1


def test_check_does_not_import_hub_or_lookup_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    original_import = builtins.__import__

    def reject_online_import(name, *args, **kwargs):
        if name.startswith("huggingface_hub") or name == "keyring":
            raise AssertionError("Offline checks must not import the download dependencies")
        return original_import(name, *args, **kwargs)

    def reject_credentials(*args, **kwargs):
        raise AssertionError("Offline checks must not look up credentials")

    monkeypatch.setattr(builtins, "__import__", reject_online_import)
    monkeypatch.setattr("src.config.secrets.get_api_key", reject_credentials)

    assert cli.main(["--check", "--deep", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "fehlt"
    assert not (tmp_path / ".preparation").exists()


def test_download_dependency_is_loaded_before_creating_staging(tmp_path, monkeypatch):
    original_import = builtins.__import__

    def missing_hub(name, *args, **kwargs):
        if name == "huggingface_hub":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_hub)

    with pytest.raises(preparation.EmbeddingModelDownloadError, match="huggingface-hub fehlt"):
        preparation.download_embedding_models(tmp_path)
    assert not (tmp_path / ".preparation").exists()


def test_download_cannot_use_preparation_directory_outside_model_root(tmp_path, fake_hub):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    try:
        (models_dir / ".preparation").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this platform")

    with pytest.raises(preparation.EmbeddingModelDownloadError, match="Vorbereitungsordner"):
        preparation.download_embedding_models(models_dir)
    assert not list(external.iterdir())
    assert not fake_hub[1]


@pytest.mark.parametrize("json_output", [False, True])
def test_download_invalid_settings_never_calls_hub(fake_hub, monkeypatch, capsys, json_output):
    monkeypatch.setenv("RATSI_MODELS_DIR", " ")

    assert cli.main(["--download"] + (["--json"] if json_output else [])) == 2
    output = capsys.readouterr()
    if json_output:
        assert json.loads(output.out)["status"] == "fehlgeschlagen"
    else:
        assert output.out == ""
    assert "RATSI_MODELS_DIR" in output.out + output.err
    assert not fake_hub[1]
