"""Tests for the common Qdrant index compatibility record."""

from dataclasses import FrozenInstanceError, replace

import pytest

from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    EmbeddingModelStatus,
    PreparedModelUnavailableError,
)
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER
from src.config.index_compatibility import IndexCompatibility, current_index_compatibility


def test_current_compatibility_uses_validated_inventory_and_canonical_models(tmp_path, monkeypatch):
    calls = []

    def check(models_dir, *, deep):
        calls.append((models_dir, deep))
        return EmbeddingModelStatus(EmbeddingModelReadiness.READY, "bereit", "a" * 64)

    monkeypatch.setattr("src.config.index_compatibility.check_embedding_model_status", check)

    record = current_index_compatibility(tmp_path, deep=True)

    assert calls == [(tmp_path, True)]
    assert record.as_dict() == {
        "dense_model_id": HARRIER_MODEL.model_id,
        "dense_revision": HARRIER_MODEL.revision,
        "sparse_model_id": BM25_MODEL.model_id,
        "sparse_revision": BM25_MODEL.revision,
        "tokenizer_model_id": HARRIER_TOKENIZER.model_id,
        "tokenizer_revision": HARRIER_TOKENIZER.revision,
        "manifest_sha256": "a" * 64,
        "vector_dimension": HARRIER_MODEL.vector_dimension,
        "pipeline_version": "passages-1",
    }
    assert IndexCompatibility.from_dict(record.as_dict()) == record
    with pytest.raises(FrozenInstanceError):
        record.pipeline_version = "changed"


@pytest.mark.parametrize("state", [
    EmbeddingModelReadiness.MISSING,
    EmbeddingModelReadiness.INCOMPLETE,
    EmbeddingModelReadiness.INCOMPATIBLE,
])
def test_current_compatibility_rejects_unready_inventory(tmp_path, monkeypatch, state):
    monkeypatch.setattr(
        "src.config.index_compatibility.check_embedding_model_status",
        lambda *args, **kwargs: EmbeddingModelStatus(state, "unready"),
    )

    with pytest.raises(PreparedModelUnavailableError, match="prepare_embedding_models.py --download"):
        current_index_compatibility(tmp_path)


@pytest.mark.parametrize("field,value", [
    ("dense_revision", "main"),
    ("sparse_model_id", "invalid"),
    ("manifest_sha256", "A" * 64),
    ("manifest_sha256", "a" * 63),
    ("vector_dimension", True),
    ("pipeline_version", ""),
])
def test_compatibility_rejects_invalid_fields(field, value):
    valid = IndexCompatibility(
        dense_model_id=HARRIER_MODEL.model_id,
        dense_revision=HARRIER_MODEL.revision,
        sparse_model_id=BM25_MODEL.model_id,
        sparse_revision=BM25_MODEL.revision,
        tokenizer_model_id=HARRIER_TOKENIZER.model_id,
        tokenizer_revision=HARRIER_TOKENIZER.revision,
        manifest_sha256="a" * 64,
        vector_dimension=1024,
        pipeline_version="passages-1",
    )

    with pytest.raises(ValueError):
        replace(valid, **{field: value})


@pytest.mark.parametrize("change", [
    lambda data: data.pop("sparse_revision"),
    lambda data: data.update(extra="unexpected"),
])
def test_stored_compatibility_rejects_wrong_schema(change):
    record = IndexCompatibility(
        dense_model_id=HARRIER_MODEL.model_id,
        dense_revision=HARRIER_MODEL.revision,
        sparse_model_id=BM25_MODEL.model_id,
        sparse_revision=BM25_MODEL.revision,
        tokenizer_model_id=HARRIER_TOKENIZER.model_id,
        tokenizer_revision=HARRIER_TOKENIZER.revision,
        manifest_sha256="a" * 64,
        vector_dimension=1024,
        pipeline_version="passages-1",
    )
    data = record.as_dict()
    change(data)

    with pytest.raises(ValueError, match="fields do not match"):
        IndexCompatibility.from_dict(data)
