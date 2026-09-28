"""Pinned download tests with a fake Hub; no real models or network access."""

import builtins
from dataclasses import replace
import errno
import json
import logging
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import urllib.request
from urllib.parse import quote

import pytest

from scripts import prepare_embedding_models as cli
from src import embedding_model_preparation as preparation
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER
from src.config.secrets import get_api_key as resolve_api_key
from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    check_embedding_model_status,
    load_and_validate_model_inventory,
)


@pytest.mark.parametrize("source", ["keyring", "env", "alias", "keyring_error", "anonymous"])
@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("json_output", [False, True])
def test_download_credentials_are_explicit_and_never_exposed(
    tmp_path, fake_hub, monkeypatch, capsys, source, failure, json_output,
):
    hub, calls = fake_hub
    monkeypatch.setattr("src.config.secrets.get_api_key", resolve_api_key)
    monkeypatch.setattr("src.config.secrets._MANAGED_HUGGINGFACE_TOKEN", None)
    stored, env, alias = "hf_keyring/private", "hf_env/private", "hf_alias/private"
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    if source in {"keyring", "env", "keyring_error"}:
        monkeypatch.setenv("HF_TOKEN", env)
    if source != "anonymous":
        monkeypatch.setenv("HUGGING_FACE_HUB_TOKEN", alias)

    keyring_calls = []

    def get_password(service, provider):
        keyring_calls.append((service, provider))
        if source == "keyring_error":
            raise RuntimeError(stored)
        return stored if source == "keyring" else None

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(get_password=get_password))
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path / "models"))
    credentials_before = {name: os.environ.get(name) for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")}
    original_download = hub.snapshot_download
    provider_calls = []

    def noisy_download(**kwargs):
        provider_calls.append(kwargs)
        for secret in (stored, env, alias, "hf_unknown_cache_token"):
            print(f"Authorization: Bearer {secret}")
            sys.stderr.write(secret[:5])
            sys.stderr.flush()
            sys.stderr.write(secret[5:] + "\n")
            print(f"https://user:{quote(secret, safe='')}@example.test/?token={quote(secret, safe='')}")
            logging.getLogger("embedding_model_preparation").critical("header=%s", secret)
            logging.getLogger("huggingface_hub").warning("provider=%s", secret)
        if failure:
            raise TimeoutError(f"Authorization: Bearer {stored}; body={env}")
        return original_download(**kwargs)

    monkeypatch.setattr(hub, "snapshot_download", noisy_download)
    previous_disable = logging.root.manager.disable
    args = ["--download", "--log-level", "DEBUG"] + (["--json"] if json_output else [])
    assert cli.main(args) == (1 if failure else 0)
    assert logging.root.manager.disable == previous_disable
    assert keyring_calls == [("ratsi_melle", "huggingface")]
    expected_token = {"keyring": stored, "env": env, "alias": alias, "keyring_error": env, "anonymous": False}[source]
    assert all(call["token"] == expected_token for call in provider_calls)
    assert len(provider_calls) == (1 if failure else 2)
    assert credentials_before == {name: os.environ.get(name) for name in credentials_before}
    output = capsys.readouterr()
    persisted = b"\n".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()).decode()
    combined = output.out + output.err + persisted
    for secret in (stored, env, alias, "hf_unknown_cache_token"):
        assert secret not in combined
        assert quote(secret, safe="") not in combined
    assert "Authorization" not in combined
    assert "Traceback" not in combined
    assert "event=model_snapshot_download_started" in persisted
    assert ("event=model_preparation_failed" if failure else "event=model_preparation_completed") in persisted
    if json_output:
        assert json.loads(output.out)["status"] == ("fehlgeschlagen" if failure else "bereit")
        assert not output.err
    if not failure:
        assert cli.main(args) == 0
        assert len(provider_calls) == 2
        assert len(keyring_calls) == 1  # Offline reuse never resolves credentials.
        if json_output:
            assert json.loads(capsys.readouterr().out)["reused"] is True


def test_provider_output_state_is_restored_after_interruption(tmp_path, fake_hub, monkeypatch):
    hub, _ = fake_hub

    def interrupt(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(hub, "snapshot_download", interrupt)
    before = (sys.stdout, sys.stderr, logging.root.manager.disable)
    with pytest.raises(KeyboardInterrupt):
        preparation.download_embedding_models(tmp_path)
    assert (sys.stdout, sys.stderr, logging.root.manager.disable) == before


@pytest.fixture(autouse=True)
def isolate_preparation_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSI_LOG_DIR", str(tmp_path / "logs"))
    previous_level = logging.getLogger().level
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if getattr(handler, "_ratsi_handler", False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(previous_level)


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
        assert call["force_download"] is True
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
    assert "Fake Hub progress" not in output.err
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


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("error_type", [RuntimeError, OSError])
def test_model_root_resolution_error_has_safe_cli_output_and_preserves_inventory(
    tmp_path, fake_hub, monkeypatch, capsys, json_output, error_type,
):
    models_dir = tmp_path / "models"
    previous = preparation.prepare_embedding_models(models_dir)
    before = {path: path.read_bytes() for path in models_dir.rglob("*") if path.is_file()}
    _, calls = fake_hub
    calls.clear()
    monkeypatch.setenv("RATSI_MODELS_DIR", str(models_dir))
    original_resolve = Path.resolve

    def fail_model_root(path, *args, **kwargs):
        if path == models_dir:
            # Python 3.11/3.12 use RuntimeError for symlink loops. Simulate the
            # failure so this regression also runs without symlink privileges.
            raise error_type("symlink loop; sensitive path; token=secret")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_model_root)
    assert cli.main(["--download"] + (["--json"] if json_output else [])) == 1
    output = capsys.readouterr()
    if json_output:
        payload = json.loads(output.out)
        assert payload["status"] == "fehlgeschlagen"
        assert payload["error_code"] == "preparation_failed"
        assert not output.err
    else:
        assert not output.out
        assert "ERROR:" in output.err
    log = (tmp_path / "logs/embedding_model_preparation.log").read_text()
    assert f"error_type={error_type.__name__}" in log
    assert "Traceback" not in output.out + output.err + log
    assert "secret" not in output.out + output.err + log
    assert "sensitive" not in output.out + output.err + log
    assert not calls
    assert before == {path: path.read_bytes() for path in models_dir.rglob("*") if path.is_file()}
    monkeypatch.setattr(Path, "resolve", original_resolve)
    assert load_and_validate_model_inventory(models_dir, deep=True) == previous.manifest


def test_raw_download_classifies_symlink_loop_runtime_error(tmp_path, fake_hub, monkeypatch):
    _, calls = fake_hub
    original_resolve = Path.resolve

    def fail_model_root(path, *args, **kwargs):
        if path == tmp_path:
            raise RuntimeError("symlink loop; token=secret")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_model_root)
    with pytest.raises(preparation.EmbeddingModelDownloadError) as failure:
        preparation.download_embedding_models(tmp_path)
    assert failure.value.error_code == "preparation_failed"
    assert "Vorbereitungsordner" in str(failure.value)
    assert "secret" not in str(failure.value)
    assert not calls
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
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-new")
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
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-new")
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
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-new")

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


def test_ready_inventory_is_reused_without_hub_credentials_or_writes(tmp_path, fake_hub, monkeypatch):
    previous = preparation.prepare_embedding_models(tmp_path)
    before = (tmp_path / "manifest.json").read_bytes()
    _, calls = fake_hub
    calls.clear()

    def reject(*args, **kwargs):
        raise AssertionError("Ready inventory reuse must remain offline and read-only")

    monkeypatch.setattr(preparation, "download_embedding_models", reject)
    monkeypatch.setattr("src.config.secrets.get_api_key", reject)
    monkeypatch.setattr(preparation.os, "replace", reject)
    result = preparation.prepare_embedding_models(tmp_path)

    assert result.reused is True
    assert result.manifest == previous.manifest
    assert (tmp_path / "manifest.json").read_bytes() == before
    assert not calls
    assert not list((tmp_path / ".preparation").iterdir())


def test_orphan_inventory_is_activated_without_hub(tmp_path, fake_hub, monkeypatch):
    original_replace = preparation.os.replace

    def fail(*args, **kwargs):
        raise OSError("activation failed")

    monkeypatch.setattr(preparation.os, "replace", fail)
    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)
    _, calls = fake_hub
    calls.clear()
    monkeypatch.setattr(preparation.os, "replace", original_replace)

    def reject(*args, **kwargs):
        raise AssertionError("Validated inventory must not require a download")

    monkeypatch.setattr(preparation, "download_embedding_models", reject)
    result = preparation.prepare_embedding_models(tmp_path)

    assert result.reused is True
    assert load_and_validate_model_inventory(tmp_path, deep=True) == result.manifest
    assert not calls


def test_completed_candidate_resumes_publication_without_hub(tmp_path, fake_hub, monkeypatch):
    original_rename = Path.rename

    def fail(*args, **kwargs):
        raise OSError("rename failed")

    monkeypatch.setattr(Path, "rename", fail)
    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)
    _, calls = fake_hub
    calls.clear()
    monkeypatch.setattr(Path, "rename", original_rename)
    monkeypatch.setattr(preparation, "download_embedding_models", lambda *args: pytest.fail("unexpected download"))

    result = preparation.prepare_embedding_models(tmp_path)

    assert result.reused is True
    assert load_and_validate_model_inventory(tmp_path, deep=True) == result.manifest
    assert not calls


@pytest.mark.parametrize("damage", ["none", "same_size", "missing_receipt", "bad_receipt", "wrong_plan", "symlink"])
def test_partial_download_resumes_only_confirmed_snapshots(tmp_path, fake_hub, damage):
    hub, calls = fake_hub
    original = hub.snapshot_download

    def fail_sparse(**kwargs):
        if kwargs["repo_id"] == BM25_MODEL.model_id:
            root = Path(kwargs["local_dir"])
            root.mkdir(parents=True, exist_ok=True)
            (root / "config.json").write_bytes(b"partial")
            raise OSError("interrupted sparse download")
        return original(**kwargs)

    hub.snapshot_download = fail_sparse
    with pytest.raises(preparation.EmbeddingModelDownloadError):
        preparation.prepare_embedding_models(tmp_path)
    staging = next((tmp_path / ".preparation").iterdir())
    dense_root = Path(calls[0]["local_dir"])
    if damage == "same_size":
        artifact = dense_root / "config.json"
        artifact.write_bytes(b"x" * artifact.stat().st_size)
    elif damage == "missing_receipt":
        (staging / "snapshot-0.json").unlink()
    elif damage == "bad_receipt":
        (staging / "snapshot-0.json").write_bytes(b"{")
    elif damage == "wrong_plan":
        plan_path = staging / "download-plan.json"
        plan = json.loads(plan_path.read_text())
        plan["snapshots"][0]["revision"] = "a" * 40
        plan_path.write_text(json.dumps(plan))
    elif damage == "symlink":
        artifact = dense_root / "config.json"
        outside = tmp_path / "outside"
        outside.write_bytes(artifact.read_bytes())
        artifact.unlink()
        try:
            artifact.symlink_to(outside)
        except OSError:
            pytest.skip("Symlinks are unavailable on this platform")
    calls.clear()
    hub.snapshot_download = original

    result = preparation.prepare_embedding_models(tmp_path)

    expected = [BM25_MODEL.model_id] if damage == "none" else [HARRIER_MODEL.model_id, BM25_MODEL.model_id]
    assert [call["repo_id"] for call in calls] == expected
    assert all(call["force_download"] is True for call in calls)
    reused_path = Path(calls[-1]["local_dir"]).parents[2]
    if damage in {"wrong_plan", "symlink"}:
        assert reused_path != staging
        assert staging.is_dir()
    else:
        assert reused_path == staging
        assert not staging.exists()
    assert load_and_validate_model_inventory(tmp_path, deep=True) == result.manifest


def test_mismatched_library_versions_do_not_reuse_ready_inventory(tmp_path, fake_hub, monkeypatch):
    original = preparation.prepare_embedding_models(tmp_path)
    _, calls = fake_hub
    calls.clear()
    monkeypatch.setattr(preparation, "version", lambda distribution: f"{distribution}-new")

    result = preparation.prepare_embedding_models(tmp_path)

    assert len(calls) == 2
    assert result.manifest.manifest_sha256 != original.manifest.manifest_sha256
    assert result.inventory_dir != original.inventory_dir
    assert original.inventory_dir.is_dir()


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("failure,expected_code", [
    (ConnectionError("sensitive provider detail"), "network_unavailable"),
    (TimeoutError("sensitive provider detail"), "network_unavailable"),
    (OSError(errno.ENOSPC, "sensitive disk path"), "disk_full"),
    (PermissionError(errno.EACCES, "sensitive disk path"), "permission_denied"),
])
def test_expected_download_failures_have_safe_short_cli_and_structured_logs(
    tmp_path, fake_hub, monkeypatch, capsys, failure, expected_code, json_output,
):
    previous = preparation.prepare_embedding_models(tmp_path)
    old_manifest = (tmp_path / "manifest.json").read_bytes()
    monkeypatch.setattr(preparation, "version", lambda name: f"{name}-new")
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("RATSI_RUN_ID", "expected-error-run")
    hub, _ = fake_hub

    def fail(**kwargs):
        raise failure

    hub.snapshot_download = fail
    capsys.readouterr()

    assert cli.main(["--download", "--log-level", "DEBUG"] + (["--json"] if json_output else [])) == 1

    output = capsys.readouterr()
    log = (tmp_path / "logs/embedding_model_preparation.log").read_text()
    if json_output:
        payload = json.loads(output.out)
        assert payload["error_code"] == expected_code
        assert payload["status"] == "fehlgeschlagen"
        assert output.err == ""
    else:
        assert output.out == ""
        assert "--download" in output.err
    assert "event=model_preparation_failed" in log
    assert f"error_code={expected_code}" in log
    assert "phase=download" in log
    assert "run_id=expected-error-run" in log
    assert "error_type=" in log
    assert "Traceback" not in output.out + output.err + log
    assert "sensitive" not in output.out + output.err + log
    assert (tmp_path / "manifest.json").read_bytes() == old_manifest
    assert load_and_validate_model_inventory(tmp_path, deep=True) == previous.manifest


def test_incomplete_download_reports_missing_artifacts_without_traceback(tmp_path, fake_hub, monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    hub, _ = fake_hub

    def incomplete(**kwargs):
        Path(kwargs["local_dir"]).mkdir(parents=True)
        return str(kwargs["local_dir"])

    hub.snapshot_download = incomplete

    assert cli.main(["--download", "--json"]) == 1
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["error_code"] == "incomplete_artifacts"
    assert "--download" in payload["message"]
    log = (tmp_path / "logs/embedding_model_preparation.log").read_text()
    assert "phase=validate_download" in log
    assert "error_type=FileNotFoundError" in log
    assert "Traceback" not in output.out + output.err + log
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize("failure_point", ["directory", "activate"])
def test_disk_full_in_local_preparation_preserves_manifest(tmp_path, fake_hub, monkeypatch, capsys, failure_point):
    previous = preparation.prepare_embedding_models(tmp_path)
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(preparation, "version", lambda name: f"{name}-new")

    def disk_full(*args, **kwargs):
        raise OSError(errno.ENOSPC, "secret local path")

    if failure_point == "directory":
        monkeypatch.setattr(preparation, "mkdtemp", disk_full)
    else:
        monkeypatch.setattr(preparation.os, "replace", disk_full)
    capsys.readouterr()

    assert cli.main(["--download", "--json"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["error_code"] == "disk_full"
    assert load_and_validate_model_inventory(tmp_path, deep=True) == previous.manifest


def test_logging_setup_failure_is_reported_without_starting_download(tmp_path, fake_hub, monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))

    def fail(*args, **kwargs):
        raise OSError(errno.ENOSPC, "secret log path")

    monkeypatch.setattr(cli, "configure_logging", fail)

    assert cli.main(["--download", "--json"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["error_code"] == "disk_full"
    assert "secret" not in output.out + output.err
    assert "Traceback" not in output.out + output.err
    assert not fake_hub[1]


def test_wrapped_disk_full_is_classified_without_exposing_exception_chain(caplog):
    try:
        try:
            raise OSError(errno.ENOSPC, "secret disk detail")
        except OSError as cause:
            raise RuntimeError("secret provider detail") from cause
    except RuntimeError as wrapped:
        result = preparation.preparation_error(wrapped, phase="download")

    assert result.error_code == "disk_full"
    assert "error_type=OSError" in caplog.text
    assert "secret" not in caplog.text + str(result)


@pytest.mark.parametrize("status,code", [(401, "source_unavailable"), (404, "source_unavailable"), (429, "network_unavailable"), (503, "network_unavailable")])
def test_hub_http_errors_log_only_status_and_type(status, code, caplog):
    import httpx
    from huggingface_hub.errors import HfHubHTTPError

    response = httpx.Response(status, request=httpx.Request("GET", "https://user:secret@example.test/model?token=secret"))
    failure = HfHubHTTPError("secret response body", response=response)

    result = preparation.preparation_error(failure, phase="download")

    assert result.error_code == code
    assert f"http_status={status}" in caplog.text
    assert "secret" not in str(result) + caplog.text


def test_httpx_transport_timeout_is_classified_without_hub_import(caplog):
    import httpx

    result = preparation.preparation_error(httpx.ReadTimeout("secret request detail"), phase="download")

    assert result.error_code == "network_unavailable"
    assert "secret" not in caplog.text + str(result)


def test_log_write_failure_does_not_emit_traceback_or_hide_cli_result(tmp_path, fake_hub, monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    real_configure = cli.configure_logging

    class FullLogStream:
        def seek(self, *args):
            pass

        def tell(self):
            return 0

        def write(self, value):
            raise OSError(errno.ENOSPC, "secret log detail")

        def flush(self):
            pass

        def close(self):
            pass

    def configure(*args, **kwargs):
        path = real_configure(*args, **kwargs)
        for handler in logging.getLogger().handlers:
            if getattr(handler, "_ratsi_handler", False):
                handler.stream.close()
                handler.stream = FullLogStream()
        return path

    monkeypatch.setattr(cli, "configure_logging", configure)

    assert cli.main(["--download", "--json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "bereit"
    assert "Traceback" not in output.err
    assert "Logging error" not in output.err
    assert "secret" not in output.out + output.err


def test_component_log_does_not_copy_provider_debug_messages(tmp_path, fake_hub, monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    hub, _ = fake_hub

    def fail(**kwargs):
        logging.getLogger("httpx").debug("secret provider request URL")
        raise TimeoutError("secret provider request URL")

    hub.snapshot_download = fail

    assert cli.main(["--download", "--json", "--log-level", "DEBUG"]) == 1
    output = capsys.readouterr()
    log = (tmp_path / "logs/embedding_model_preparation.log").read_text()
    assert "error_code=network_unavailable" in log
    assert "secret" not in log + output.out + output.err
