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
from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    check_embedding_model_status,
    load_and_validate_model_inventory,
)


@pytest.fixture
def fake_hub(monkeypatch):
    calls = []

    def reject_network(*args, **kwargs):
        raise AssertionError("Download tests must not access the real Hub")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    monkeypatch.setattr("src.config.secrets.get_api_key", lambda provider: None)
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-test")

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
def test_download_cli_publishes_ready_inventory_without_overwriting_old_artifacts(
    tmp_path, fake_hub, monkeypatch, capsys, json_output,
):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    active_manifest = tmp_path / "manifest.json"
    active_artifact = tmp_path / "active/model.safetensors"
    active_artifact.parent.mkdir()
    active_manifest.write_bytes(b"existing manifest")
    active_artifact.write_bytes(b"existing weights")
    before = (active_artifact.read_bytes(), active_artifact.stat().st_mtime_ns)

    assert cli.main(["--download"] + (["--json"] if json_output else [])) == 0

    output = capsys.readouterr()
    assert "Fake Hub progress" not in output.out
    assert "Fake Hub progress" in output.err
    if json_output:
        payload = json.loads(output.out)
        assert payload["operation"] == "download"
        assert payload["status"] == "bereit"
        assert Path(payload["inventory_dir"]).parent == tmp_path / "inventories"
        assert payload["manifest_sha256"]
    else:
        assert "Modellbestand:" in output.out
        assert "Manifest-SHA-256:" in output.out
    assert "geprueft und freigegeben" in output.out
    assert before == (active_artifact.read_bytes(), active_artifact.stat().st_mtime_ns)
    manifest = load_and_validate_model_inventory(tmp_path, deep=True)
    assert manifest.dense_model.relative_path == manifest.tokenizer.relative_path
    assert manifest.library_versions.huggingface_hub == "huggingface-hub-test"
    if json_output:
        assert payload["manifest_sha256"] == manifest.manifest_sha256


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


@pytest.mark.parametrize("damage", ["missing", "empty", "unexpected", "escape"])
def test_invalid_candidate_never_replaces_ready_inventory(tmp_path, fake_hub, monkeypatch, damage):
    previous = preparation.prepare_embedding_models(tmp_path)
    old_manifest = (tmp_path / "manifest.json").read_bytes()
    hub, _ = fake_hub
    original = hub.snapshot_download

    def damage_download(**kwargs):
        result = original(**kwargs)
        if kwargs["repo_id"] == HARRIER_MODEL.model_id:
            root = Path(kwargs["local_dir"])
            artifact = root / "model.safetensors"
            if damage == "missing":
                artifact.unlink()
            elif damage == "empty":
                artifact.write_bytes(b"")
            elif damage == "unexpected":
                (root / "sentence_bert_config.json").write_bytes(b"{}")
            else:
                outside = tmp_path / "outside"
                outside.write_bytes(b"not a local model artifact")
                artifact.unlink()
                try:
                    artifact.symlink_to(outside)
                except OSError:
                    pytest.skip("Symlinks are unavailable on this platform")
        return result

    hub.snapshot_download = damage_download

    with pytest.raises(preparation.EmbeddingModelDownloadError, match="Modellpruefung"):
        preparation.prepare_embedding_models(tmp_path)

    assert (tmp_path / "manifest.json").read_bytes() == old_manifest
    assert load_and_validate_model_inventory(tmp_path, deep=True) == previous.manifest


def test_candidate_is_deeply_verified_before_activation(tmp_path, fake_hub, monkeypatch):
    previous = preparation.prepare_embedding_models(tmp_path)
    original_build = preparation._build_candidate_manifest

    def corrupt_after_hashing(download):
        candidate = original_build(download)
        artifact = download.staging_dir / candidate.dense_model.relative_path / "config.json"
        artifact.write_bytes(b"x" * artifact.stat().st_size)
        return candidate

    monkeypatch.setattr(preparation, "_build_candidate_manifest", corrupt_after_hashing)

    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)
    assert load_and_validate_model_inventory(tmp_path, deep=True) == previous.manifest


@pytest.mark.parametrize("failure_point", ["rename", "manifest_write", "flush", "activate"])
def test_publication_failure_preserves_previous_ready_inventory(
    tmp_path, fake_hub, monkeypatch, failure_point,
):
    previous = preparation.prepare_embedding_models(tmp_path)
    old_manifest = (tmp_path / "manifest.json").read_bytes()
    # A different library record creates a different candidate generation.
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-new")

    def fail(*args, **kwargs):
        raise OSError("simulated publication failure")

    if failure_point == "rename":
        monkeypatch.setattr(Path, "rename", fail)
    elif failure_point == "manifest_write":
        monkeypatch.setattr(preparation, "mkstemp", fail)
    elif failure_point == "flush":
        monkeypatch.setattr(preparation.os, "fsync", fail)
    else:
        monkeypatch.setattr(preparation.os, "replace", fail)

    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)

    assert (tmp_path / "manifest.json").read_bytes() == old_manifest
    assert load_and_validate_model_inventory(tmp_path, deep=True) == previous.manifest


def test_activation_switches_one_manifest_and_keeps_old_generation(tmp_path, fake_hub, monkeypatch):
    previous = preparation.prepare_embedding_models(tmp_path)
    original_replace = preparation.os.replace
    observations = []
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-new")

    def observe_switch(source, destination):
        assert Path(source).parent == tmp_path
        assert Path(destination) == tmp_path / "manifest.json"
        observations.append(load_and_validate_model_inventory(tmp_path, deep=True))
        original_replace(source, destination)
        observations.append(load_and_validate_model_inventory(tmp_path, deep=True))

    monkeypatch.setattr(preparation.os, "replace", observe_switch)

    prepared = preparation.prepare_embedding_models(tmp_path)

    assert observations == [previous.manifest, prepared.manifest]
    assert previous.inventory_dir.is_dir()
    assert prepared.inventory_dir != previous.inventory_dir
    assert not list((tmp_path / ".preparation").iterdir())


def test_identical_preparation_preserves_compatibility_hash(tmp_path, fake_hub):
    previous = preparation.prepare_embedding_models(tmp_path)

    prepared = preparation.prepare_embedding_models(tmp_path)

    assert prepared.inventory_dir == previous.inventory_dir
    assert prepared.manifest.manifest_sha256 == previous.manifest.manifest_sha256
    assert load_and_validate_model_inventory(tmp_path, deep=True) == prepared.manifest


def test_corrupted_existing_generation_is_not_overwritten(tmp_path, fake_hub):
    previous = preparation.prepare_embedding_models(tmp_path)
    old_manifest = (tmp_path / "manifest.json").read_bytes()
    artifact = tmp_path / previous.manifest.dense_model.relative_path / "config.json"
    artifact.write_bytes(b"x" * artifact.stat().st_size)

    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)

    assert (tmp_path / "manifest.json").read_bytes() == old_manifest
    assert artifact.read_bytes() == b"x" * artifact.stat().st_size


def test_missing_library_metadata_prevents_activation(tmp_path, fake_hub, monkeypatch):
    def missing(distribution):
        raise preparation.PackageNotFoundError(distribution)

    monkeypatch.setattr(preparation, "version", missing)

    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)
    assert not (tmp_path / "manifest.json").exists()


def test_interrupted_activation_preserves_previous_inventory(tmp_path, fake_hub, monkeypatch):
    previous = preparation.prepare_embedding_models(tmp_path)

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(preparation.os, "replace", interrupt)

    with pytest.raises(KeyboardInterrupt):
        preparation.prepare_embedding_models(tmp_path)
    assert load_and_validate_model_inventory(tmp_path, deep=True) == previous.manifest


def test_failed_first_activation_leaves_inventory_missing(tmp_path, fake_hub, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("manifest activation failed")

    monkeypatch.setattr(preparation.os, "replace", fail)

    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)

    assert check_embedding_model_status(tmp_path).state is EmbeddingModelReadiness.MISSING
    assert not (tmp_path / "manifest.json").exists()
