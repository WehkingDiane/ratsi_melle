"""Validation and hashing tests for embedding model manifests."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from src.config.embedding_model_manifest import (
    ArtifactManifest,
    EmbeddingModelManifest,
    ModelLibraryVersions,
    PreparedModelManifest,
    build_artifact_manifests,
    calculate_manifest_sha256,
    canonical_manifest_bytes,
    select_checksum_artifacts,
    validate_absent_artifacts,
    with_manifest_sha256,
)


def _artifact(path: str = "config.json", content: bytes = b"{}") -> ArtifactManifest:
    from hashlib import sha256

    return ArtifactManifest(
        relative_path=path,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
    )


def _component(*artifacts: ArtifactManifest) -> PreparedModelManifest:
    return PreparedModelManifest(
        model_id="example/model",
        configured_revision="a" * 40,
        resolved_revision="a" * 40,
        relative_path="dense/example/model/a",
        artifacts=artifacts or (_artifact(),),
    )


def _manifest(**changes) -> EmbeddingModelManifest:
    component = _component()
    values = {
        "manifest_format_version": 1,
        "pipeline_version": "passages-1",
        "dense_model": component,
        "tokenizer": component,
        "sparse_model": component,
        "library_versions": ModelLibraryVersions(
            transformers="5.5.0",
            sentence_transformers="5.4.0",
            fastembed="0.7.0",
            huggingface_hub="1.0.0",
        ),
        "created_at": "2026-09-27T12:00:00Z",
    }
    values.update(changes)
    return EmbeddingModelManifest(**values)


@pytest.mark.parametrize(
    "paths",
    [
        (),
        ("",),
        (".",),
        ("/absolute.json",),
        ("../escape.json",),
        ("nested/../escape.json",),
        ("nested\\windows.json",),
        ("./not-canonical.json",),
        ("duplicate.json", "duplicate.json"),
    ],
)
def test_invalid_checksum_artifact_selections_are_rejected(paths) -> None:
    with pytest.raises(ValueError):
        select_checksum_artifacts(paths)


def test_artifact_selection_and_file_hashing_are_deterministic(tmp_path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "weights.bin").write_bytes(b"weights")
    (tmp_path / "config.json").write_bytes(b"{}")

    artifacts = build_artifact_manifests(
        tmp_path,
        ("nested/weights.bin", "config.json"),
    )

    assert artifacts == (_artifact(), _artifact("nested/weights.bin", b"weights"))


def test_file_hashing_rejects_a_missing_selected_artifact(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_artifact_manifests(tmp_path, ("missing.bin",))


def test_unexpected_behavior_artifact_is_rejected(tmp_path) -> None:
    (tmp_path / "config.json").write_bytes(b"{}")
    (tmp_path / "sentence_bert_config.json").write_bytes(b'{"max_seq_length":128}')

    with pytest.raises(ValueError, match="Unexpected model artifact"):
        build_artifact_manifests(
            tmp_path,
            ("config.json",),
            expected_absent_paths=("sentence_bert_config.json",),
        )


def test_expected_absent_behavior_artifact_allows_pinned_snapshot(tmp_path) -> None:
    validate_absent_artifacts(tmp_path, ("sentence_bert_config.json",))


@pytest.mark.parametrize(
    "changes",
    [
        {"relative_path": "../escape"},
        {"size_bytes": -1},
        {"size_bytes": True},
        {"sha256": "short"},
        {"sha256": "A" * 64},
    ],
)
def test_invalid_artifact_manifest_fields_are_rejected(changes) -> None:
    values = {
        "relative_path": "config.json",
        "size_bytes": 2,
        "sha256": "a" * 64,
    }
    values.update(changes)
    with pytest.raises(ValueError):
        ArtifactManifest(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"model_id": "missing-owner"},
        {"configured_revision": "main"},
        {"resolved_revision": "a" * 39},
        {"relative_path": "/absolute"},
        {"artifacts": ()},
        {"artifacts": (_artifact(), _artifact())},
    ],
)
def test_invalid_prepared_model_fields_are_rejected(changes) -> None:
    values = {
        "model_id": "example/model",
        "configured_revision": "a" * 40,
        "resolved_revision": "a" * 40,
        "relative_path": "dense/example/model/a",
        "artifacts": (_artifact(),),
    }
    values.update(changes)
    with pytest.raises(ValueError):
        PreparedModelManifest(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"manifest_format_version": 0},
        {"manifest_format_version": True},
        {"pipeline_version": ""},
        {"pipeline_version": " passages-1"},
        {"created_at": "2026-09-27T12:00:00"},
        {"created_at": "not-a-dateZ"},
        {"manifest_sha256": "bad"},
    ],
)
def test_invalid_top_level_manifest_fields_are_rejected(changes) -> None:
    with pytest.raises(ValueError):
        _manifest(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"transformers": ""},
        {"sentence_transformers": " 5.4.0"},
        {"fastembed": ""},
        {"huggingface_hub": ""},
    ],
)
def test_invalid_library_versions_are_rejected(changes) -> None:
    values = {
        "transformers": "5.5.0",
        "sentence_transformers": "5.4.0",
        "fastembed": "0.7.0",
        "huggingface_hub": "1.0.0",
    }
    values.update(changes)
    with pytest.raises(ValueError):
        ModelLibraryVersions(**values)


def test_canonical_hash_is_order_independent_and_self_excluding() -> None:
    first = _artifact("a.json", b"a")
    second = _artifact("b.json", b"b")
    forward = _manifest(dense_model=_component(first, second))
    reverse = _manifest(dense_model=_component(second, first))

    hashed = with_manifest_sha256(forward)

    assert calculate_manifest_sha256(forward) == calculate_manifest_sha256(reverse)
    assert calculate_manifest_sha256(hashed) == hashed.manifest_sha256
    assert b'"manifest_sha256"' not in canonical_manifest_bytes(
        hashed,
        include_manifest_sha256=False,
    )
    assert json.loads(canonical_manifest_bytes(hashed))["manifest_sha256"] == (
        hashed.manifest_sha256
    )


def test_manifest_hash_excludes_volatile_creation_time() -> None:
    first = _manifest(created_at="2026-09-27T12:00:00Z")
    prepared_again = replace(first, created_at="2026-09-28T09:30:00Z")

    assert calculate_manifest_sha256(first) == calculate_manifest_sha256(prepared_again)
    contract_bytes = canonical_manifest_bytes(
        first,
        include_manifest_sha256=False,
        include_created_at=False,
    )
    assert b'"created_at"' not in contract_bytes
    assert b'"manifest_sha256"' not in contract_bytes


def test_manifest_hash_changes_with_reproducibility_fields() -> None:
    manifest = _manifest()

    assert calculate_manifest_sha256(manifest) != calculate_manifest_sha256(
        replace(manifest, pipeline_version="passages-2")
    )


def test_manifest_schema_is_immutable() -> None:
    manifest = _manifest()

    with pytest.raises(FrozenInstanceError):
        manifest.pipeline_version = "passages-2"  # type: ignore[misc]
