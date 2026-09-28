"""CLI checks of local model inventories using controlled files and blocked network."""

from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import urllib.request

import pytest

from scripts import prepare_embedding_models as cli
from src.config.embedding_model_manifest import (
    EmbeddingModelManifest,
    ModelLibraryVersions,
    PreparedModelManifest,
    build_artifact_manifests,
    canonical_manifest_bytes,
    with_manifest_sha256,
)
from src.config.embedding_models import (
    BM25_MODEL,
    EMBEDDING_PIPELINE_VERSION,
    HARRIER_MODEL,
    HARRIER_TOKENIZER,
    MODEL_MANIFEST_FORMAT_VERSION,
)
from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    EmbeddingModelStatus,
    MODEL_MANIFEST_FILENAME,
)


@pytest.mark.parametrize("state", list(EmbeddingModelReadiness))
def test_check_uses_shared_status_and_configured_directory(tmp_path, monkeypatch, capsys, state):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    expected = EmbeddingModelStatus(state, "Testmeldung")

    def check_status(models_dir, *, deep=False):
        assert models_dir == tmp_path
        assert deep is False
        return expected

    monkeypatch.setattr(cli, "check_embedding_model_status", check_status)

    assert cli.main(["--check"]) == (0 if state is EmbeddingModelReadiness.READY else 1)
    output = capsys.readouterr()
    assert output.out == f"Schnellpruefung: {state.value} - Testmeldung\n"
    assert output.err == ""


def test_check_missing_inventory_stays_offline_and_does_not_create_directory(
    tmp_path, monkeypatch, capsys,
):
    models_dir = tmp_path / "absent_models"
    monkeypatch.setenv("RATSI_MODELS_DIR", str(models_dir))

    def reject_network(*args, **kwargs):
        raise AssertionError("Local CLI checks must remain offline")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)

    assert cli.main(["--check"]) == 1
    assert capsys.readouterr().out.startswith("Schnellpruefung: fehlt")
    assert not models_dir.exists()


def test_check_invalid_settings_reports_short_error(monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", " ")

    assert cli.main(["--check"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "RATSI_MODELS_DIR" in output.err
    assert "Traceback" not in output.err


@pytest.mark.integration
def test_script_can_be_called_from_another_working_directory(tmp_path):
    script = Path(cli.__file__).resolve()
    environment = dict(os.environ, RATSI_MODELS_DIR=str(tmp_path / "absent_models"))
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert result.stdout.startswith("Schnellpruefung: fehlt")
    assert result.stderr == ""


@pytest.fixture
def prepared_inventory(tmp_path, monkeypatch):
    components = {}
    for name, definition in (
        ("dense_model", HARRIER_MODEL),
        ("tokenizer", HARRIER_TOKENIZER),
        ("sparse_model", BM25_MODEL),
    ):
        root = tmp_path / name
        for relative_path in definition.required_artifacts:
            artifact = root / relative_path
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(f"{name}/{relative_path}".encode())
        components[name] = PreparedModelManifest(
            model_id=definition.model_id,
            configured_revision=definition.revision,
            resolved_revision=definition.revision,
            relative_path=name,
            artifacts=build_artifact_manifests(root, definition.required_artifacts),
        )
    manifest = with_manifest_sha256(EmbeddingModelManifest(
        manifest_format_version=MODEL_MANIFEST_FORMAT_VERSION,
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        **components,
        library_versions=ModelLibraryVersions(
            transformers="5.5.0", sentence_transformers="5.4.0",
            fastembed="0.7.0", huggingface_hub="1.0.0",
        ),
        created_at="2026-09-28T12:00:00Z",
    ))
    (tmp_path / MODEL_MANIFEST_FILENAME).write_bytes(canonical_manifest_bytes(manifest))
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    return tmp_path, manifest


@pytest.mark.parametrize("deep", [False, True])
@pytest.mark.parametrize("corrupt", [False, True])
@pytest.mark.parametrize("json_output", [False, True])
def test_check_levels_report_real_inventory_without_network_or_writes(
    prepared_inventory, monkeypatch, capsys, deep, corrupt, json_output,
):
    models_dir, manifest = prepared_inventory
    if corrupt:
        artifact = models_dir / "dense_model/config.json"
        artifact.write_bytes(b"x" * artifact.stat().st_size)
    before = {
        path.relative_to(models_dir): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in models_dir.rglob("*") if path.is_file()
    }

    def reject_network(*args, **kwargs):
        raise AssertionError("Local CLI checks must remain offline")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    args = ["--check"] + (["--deep"] if deep else []) + (["--json"] if json_output else [])
    damaged = deep and corrupt

    assert cli.main(args) == (1 if damaged else 0)

    output = capsys.readouterr()
    assert output.err == ""
    if json_output:
        payload = json.loads(output.out)
        assert set(payload) == {"status", "message", "manifest_sha256", "check_level"}
        assert payload["check_level"] == ("deep" if deep else "fast")
        assert payload["status"] == ("unvollstaendig" if damaged else "bereit")
        assert payload["manifest_sha256"] == (None if damaged else manifest.manifest_sha256)
        assert payload["message"]
    else:
        assert output.out.startswith("Tiefenpruefung:" if deep else "Schnellpruefung:")
        assert ("unvollstaendig" if damaged else "bereit") in output.out
        if not damaged:
            assert manifest.manifest_sha256 in output.out
    if damaged:
        assert "SHA-256" in output.out
    after = {
        path.relative_to(models_dir): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in models_dir.rglob("*") if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize("state", list(EmbeddingModelReadiness))
def test_json_preserves_shared_status_fields(tmp_path, monkeypatch, capsys, state):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    expected = EmbeddingModelStatus(state, "Testmeldung")
    monkeypatch.setattr(cli, "check_embedding_model_status", lambda *args, **kwargs: expected)

    assert cli.main(["--check", "--json"]) == (0 if state is EmbeddingModelReadiness.READY else 1)
    output = capsys.readouterr()
    assert json.loads(output.out) == {**expected.as_dict(), "check_level": "fast"}
    assert output.err == ""


def test_json_invalid_settings_returns_parseable_error(monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", " ")

    assert cli.main(["--check", "--deep", "--json"]) == 2
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["status"] == "inkompatibel"
    assert payload["check_level"] == "deep"
    assert payload["manifest_sha256"] is None
    assert "RATSI_MODELS_DIR" in payload["message"]
    assert output.err == ""


@pytest.mark.parametrize("args", [
    [], ["--deep"], ["--json"], ["--check", "--update"],
    ["--check", "--download"], ["--download", "--deep"],
    ["--download", "--model-id", "other/model"],
    ["--download", "--revision", "main"],
])
def test_unsupported_or_missing_action_is_rejected(args, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(args)

    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "usage:" in output.err
    assert "Traceback" not in output.err
