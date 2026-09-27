"""Tests for the canonical embedding model definitions."""

from dataclasses import FrozenInstanceError

import pytest

from src.config.embedding_models import (
    BM25_MODEL,
    EMBEDDING_PIPELINE_VERSION,
    HARRIER_MODEL,
    HARRIER_TOKENIZER,
    MODEL_MANIFEST_FORMAT_VERSION,
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
