"""Canonical identities for models used by the hybrid search pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DenseModelDefinition:
    """Identity and output contract of the dense embedding model."""

    model_id: str
    revision: str
    vector_dimension: int


@dataclass(frozen=True, slots=True)
class TokenizerDefinition:
    """Identity of the tokenizer used to split documents into passages."""

    model_id: str
    revision: str


@dataclass(frozen=True, slots=True)
class SparseModelDefinition:
    """Identity of the sparse embedding model."""

    model_id: str
    revision: str


HARRIER_MODEL = DenseModelDefinition(
    model_id="microsoft/harrier-oss-v1-0.6b",
    revision="f9b9dc8d367d443f2479d27aa5d8d2850c0774ee",
    vector_dimension=1024,
)

HARRIER_TOKENIZER = TokenizerDefinition(
    model_id="microsoft/harrier-oss-v1-0.6b",
    revision="f9b9dc8d367d443f2479d27aa5d8d2850c0774ee",
)

BM25_MODEL = SparseModelDefinition(
    model_id="Qdrant/bm25",
    revision="22b8d2af71a76161e18dd432d2cee0eefa66e412",
)
