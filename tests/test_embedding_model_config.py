"""Tests for the canonical embedding model definitions."""

from dataclasses import FrozenInstanceError

import pytest

from src.config.embedding_models import (
    BM25_MODEL,
    DenseModelDefinition,
    EMBEDDING_PIPELINE_VERSION,
    HARRIER_MODEL,
    HARRIER_TOKENIZER,
    MODEL_MANIFEST_FORMAT_VERSION,
    SparseModelDefinition,
    TokenizerDefinition,
)
from src.config.embedding_model_manifest import (
    EmbeddingModelManifest,
    ModelLibraryVersions,
    PreparedModelManifest,
    build_artifact_manifests,
    calculate_manifest_sha256,
    canonical_manifest_bytes,
    with_manifest_sha256,
)


def test_embedding_model_definitions_capture_existing_runtime_contract() -> None:
    assert HARRIER_MODEL.model_id == "microsoft/harrier-oss-v1-0.6b"
    assert HARRIER_MODEL.revision == "f9b9dc8d367d443f2479d27aa5d8d2850c0774ee"
    assert HARRIER_MODEL.vector_dimension == 1024
    assert HARRIER_TOKENIZER.model_id == HARRIER_MODEL.model_id
    assert HARRIER_TOKENIZER.revision == HARRIER_MODEL.revision
    assert BM25_MODEL.model_id == "Qdrant/bm25"
    assert BM25_MODEL.revision == "22b8d2af71a76161e18dd432d2cee0eefa66e412"


def test_embedding_contract_versions_have_distinct_types_and_initial_values() -> None:
    assert EMBEDDING_PIPELINE_VERSION == "passages-1"
    assert isinstance(EMBEDDING_PIPELINE_VERSION, str)
    assert MODEL_MANIFEST_FORMAT_VERSION == 1
    assert isinstance(MODEL_MANIFEST_FORMAT_VERSION, int)


def test_required_artifacts_are_immutable_central_allowlists() -> None:
    assert HARRIER_MODEL.required_artifacts == (
        "1_Pooling/config.json",
        "config.json",
        "config_sentence_transformers.json",
        "model.safetensors",
        "modules.json",
    )
    assert HARRIER_TOKENIZER.required_artifacts == (
        "added_tokens.json",
        "merges.txt",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    )
    assert BM25_MODEL.required_artifacts == ("config.json", "english.txt")


def test_manifest_artifacts_and_hash_are_deterministic(tmp_path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "weights.bin").write_bytes(b"weights")
    (tmp_path / "config.json").write_bytes(b"{}")
    artifacts = build_artifact_manifests(
        tmp_path,
        ("nested/weights.bin", "config.json"),
    )
    component = PreparedModelManifest(
        model_id="example/model",
        configured_revision="a" * 40,
        resolved_revision="a" * 40,
        relative_path="dense/example/model/a",
        artifacts=tuple(reversed(artifacts)),
    )
    manifest = EmbeddingModelManifest(
        manifest_format_version=MODEL_MANIFEST_FORMAT_VERSION,
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        dense_model=component,
        tokenizer=component,
        sparse_model=component,
        library_versions=ModelLibraryVersions(
            transformers="5.5.0",
            sentence_transformers="5.4.0",
            fastembed="0.7.0",
            huggingface_hub="1.0.0",
        ),
        created_at="2026-09-27T12:00:00Z",
    )

    hashed = with_manifest_sha256(manifest)

    assert [artifact.relative_path for artifact in artifacts] == [
        "config.json",
        "nested/weights.bin",
    ]
    assert hashed.manifest_sha256 == calculate_manifest_sha256(manifest)
    assert calculate_manifest_sha256(hashed) == hashed.manifest_sha256
    assert b'"manifest_sha256"' not in canonical_manifest_bytes(
        hashed,
        include_manifest_sha256=False,
    )


@pytest.mark.parametrize("definition", [HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL])
def test_embedding_model_revisions_are_full_commit_hashes(definition: object) -> None:
    revision = definition.revision  # type: ignore[attr-defined]
    assert len(revision) == 40
    assert all(character in "0123456789abcdef" for character in revision)
    assert revision not in {"main", "master", "latest"}


@pytest.mark.parametrize("definition", [HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL])
def test_embedding_model_definitions_are_immutable(definition: object) -> None:
    with pytest.raises(FrozenInstanceError):
        definition.revision = "moving-reference"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("definition_type", "kwargs"),
    [
        (
            DenseModelDefinition,
            {
                "model_id": "missing-owner",
                "revision": "a" * 40,
                "vector_dimension": 1024,
                "required_artifacts": ("model.bin",),
            },
        ),
        (
            TokenizerDefinition,
            {
                "model_id": "owner/model",
                "revision": "main",
                "required_artifacts": ("tokenizer.json",),
            },
        ),
        (
            SparseModelDefinition,
            {
                "model_id": "owner/model",
                "revision": "A" * 40,
                "required_artifacts": ("config.json",),
            },
        ),
        (
            DenseModelDefinition,
            {
                "model_id": "owner/model",
                "revision": "a" * 40,
                "vector_dimension": 0,
                "required_artifacts": ("model.bin",),
            },
        ),
        (
            TokenizerDefinition,
            {
                "model_id": "owner/model",
                "revision": "a" * 40,
                "required_artifacts": ("z.json", "a.json"),
            },
        ),
        (
            SparseModelDefinition,
            {
                "model_id": "owner/model",
                "revision": "a" * 40,
                "required_artifacts": ("../config.json",),
            },
        ),
    ],
)
def test_invalid_model_definitions_are_rejected(definition_type, kwargs) -> None:
    with pytest.raises(ValueError):
        definition_type(**kwargs)
