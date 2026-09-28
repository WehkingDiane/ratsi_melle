"""Local embedding inventory validation tests; no model or network access."""

from dataclasses import replace
import json

import pytest

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
    MODEL_MANIFEST_FILENAME,
    ModelInventoryIncompatibleError,
    ModelInventoryIncompleteError,
    check_embedding_model_status,
    load_and_validate_model_inventory,
)


def _write_inventory(models_dir):
    components = []
    definitions = (
        ("dense_model", HARRIER_MODEL),
        ("tokenizer", HARRIER_TOKENIZER),
        ("sparse_model", BM25_MODEL),
    )
    for name, definition in definitions:
        relative_path = f"{name}/snapshot"
        model_root = models_dir / relative_path
        model_root.mkdir(parents=True)
        for artifact_path in definition.required_artifacts:
            artifact = model_root / artifact_path
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes((name + artifact_path).encode())
        components.append(
            PreparedModelManifest(
                model_id=definition.model_id,
                configured_revision=definition.revision,
                resolved_revision=definition.revision,
                relative_path=relative_path,
                artifacts=build_artifact_manifests(model_root, definition.required_artifacts),
            )
        )
    manifest = EmbeddingModelManifest(
        manifest_format_version=MODEL_MANIFEST_FORMAT_VERSION,
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        dense_model=components[0],
        tokenizer=components[1],
        sparse_model=components[2],
        library_versions=ModelLibraryVersions(
            transformers="5.5.0",
            sentence_transformers="5.4.0",
            fastembed="0.7.0",
            huggingface_hub="1.0.0",
        ),
        created_at="2026-09-27T12:00:00Z",
    )
    manifest = with_manifest_sha256(manifest)
    (models_dir / MODEL_MANIFEST_FILENAME).write_bytes(canonical_manifest_bytes(manifest))
    return manifest


def test_local_inventory_check_accepts_complete_manifest_without_network(tmp_path):
    expected = _write_inventory(tmp_path)

    actual = load_and_validate_model_inventory(tmp_path)

    assert actual == expected


def test_fast_inventory_check_skips_hashes_but_deep_check_verifies_them(tmp_path):
    _write_inventory(tmp_path)
    artifact = tmp_path / "dense_model/snapshot/config.json"
    original = artifact.read_bytes()
    artifact.write_bytes(b"x" * len(original))

    load_and_validate_model_inventory(tmp_path)
    with pytest.raises(ModelInventoryIncompleteError, match="SHA-256"):
        load_and_validate_model_inventory(tmp_path, deep=True)


def test_deep_inventory_check_accepts_valid_artifact_hashes(tmp_path):
    expected = _write_inventory(tmp_path)

    actual = load_and_validate_model_inventory(tmp_path, deep=True)

    assert actual == expected


def test_local_inventory_check_reports_missing_manifest(tmp_path):
    from src.config.embedding_model_status import ModelInventoryMissingError

    with pytest.raises(ModelInventoryMissingError):
        load_and_validate_model_inventory(tmp_path)


def test_local_inventory_check_detects_missing_artifact(tmp_path):
    _write_inventory(tmp_path)
    (tmp_path / "dense_model/snapshot/model.safetensors").unlink()

    with pytest.raises(ModelInventoryIncompleteError):
        load_and_validate_model_inventory(tmp_path)


def test_shared_status_model_reports_missing_inventory(tmp_path):
    result = check_embedding_model_status(tmp_path)

    assert result.state is EmbeddingModelReadiness.MISSING
    assert result.as_dict()["status"] == "fehlt"


def test_shared_status_model_reports_incomplete_inventory(tmp_path):
    _write_inventory(tmp_path)
    (tmp_path / "dense_model/snapshot/model.safetensors").unlink()

    result = check_embedding_model_status(tmp_path)

    assert result.state is EmbeddingModelReadiness.INCOMPLETE


def test_shared_status_model_reports_incompatible_inventory(tmp_path):
    manifest = _write_inventory(tmp_path)
    changed = with_manifest_sha256(
        replace(manifest, pipeline_version="passages-2")
    )
    (tmp_path / MODEL_MANIFEST_FILENAME).write_bytes(canonical_manifest_bytes(changed))

    result = check_embedding_model_status(tmp_path)

    assert result.state is EmbeddingModelReadiness.INCOMPATIBLE


def test_shared_status_model_reports_ready_inventory(tmp_path):
    manifest = _write_inventory(tmp_path)

    result = check_embedding_model_status(tmp_path)

    assert result.state is EmbeddingModelReadiness.READY
    assert result.manifest_sha256 == manifest.manifest_sha256
    assert result.as_dict()["status"] == "bereit"


def test_local_inventory_check_detects_incompatible_revision(tmp_path):
    manifest = _write_inventory(tmp_path)
    invalid_dense_model = replace(
        manifest.dense_model,
        resolved_revision="0" * 40,
    )
    changed = with_manifest_sha256(replace(manifest, dense_model=invalid_dense_model))
    (tmp_path / MODEL_MANIFEST_FILENAME).write_bytes(canonical_manifest_bytes(changed))

    with pytest.raises(ModelInventoryIncompatibleError):
        load_and_validate_model_inventory(tmp_path)


def test_local_inventory_check_detects_foreign_model_identity(tmp_path):
    manifest = _write_inventory(tmp_path)
    invalid_dense_model = replace(manifest.dense_model, model_id="other/embedding")
    changed = with_manifest_sha256(replace(manifest, dense_model=invalid_dense_model))
    (tmp_path / MODEL_MANIFEST_FILENAME).write_bytes(canonical_manifest_bytes(changed))

    with pytest.raises(ModelInventoryIncompatibleError):
        load_and_validate_model_inventory(tmp_path)


def test_local_inventory_check_detects_tampered_manifest_hash(tmp_path):
    _write_inventory(tmp_path)
    manifest_path = tmp_path / MODEL_MANIFEST_FILENAME
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["manifest_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelInventoryIncompatibleError, match="Hash"):
        load_and_validate_model_inventory(tmp_path)


def test_local_inventory_check_reports_size_mismatch(tmp_path):
    _write_inventory(tmp_path)
    artifact = tmp_path / "dense_model/snapshot/config.json"
    artifact.write_bytes(b"different size")

    with pytest.raises(ModelInventoryIncompleteError):
        load_and_validate_model_inventory(tmp_path)


def test_local_inventory_check_rejects_unexpected_behavior_affecting_artifact(tmp_path):
    _write_inventory(tmp_path)
    unexpected = tmp_path / "dense_model/snapshot/sentence_bert_config.json"
    unexpected.write_text("{}", encoding="utf-8")

    with pytest.raises(ModelInventoryIncompatibleError):
        load_and_validate_model_inventory(tmp_path)
