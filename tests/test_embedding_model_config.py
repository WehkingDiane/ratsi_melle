"""Tests for the canonical embedding model definitions."""

from dataclasses import FrozenInstanceError

import pytest

from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER


def test_embedding_model_definitions_capture_existing_runtime_contract() -> None:
    assert HARRIER_MODEL.model_id == "microsoft/harrier-oss-v1-0.6b"
    assert HARRIER_MODEL.revision is None
    assert HARRIER_MODEL.vector_dimension == 1024
    assert HARRIER_TOKENIZER.model_id == HARRIER_MODEL.model_id
    assert HARRIER_TOKENIZER.revision is None
    assert BM25_MODEL.model_id == "Qdrant/bm25"
    assert BM25_MODEL.revision is None


@pytest.mark.parametrize("definition", [HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL])
def test_embedding_model_definitions_are_immutable(definition: object) -> None:
    with pytest.raises(FrozenInstanceError):
        definition.revision = "moving-reference"  # type: ignore[attr-defined]
