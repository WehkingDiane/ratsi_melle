"""Canonical identities for models used by the hybrid search pipeline.

Concrete immutable revisions are intentionally populated in M1.3. Until then,
``None`` records that the existing runtime does not pin a revision; callers must
not replace it with a moving reference such as ``main``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DenseModelDefinition:
    """Identity and output contract of the dense embedding model."""

    model_id: str
    revision: str | None
    vector_dimension: int


@dataclass(frozen=True, slots=True)
class TokenizerDefinition:
    """Identity of the tokenizer used to split documents into passages."""

    model_id: str
    revision: str | None


@dataclass(frozen=True, slots=True)
class SparseModelDefinition:
    """Identity of the sparse embedding model."""

    model_id: str
    revision: str | None


HARRIER_MODEL = DenseModelDefinition(
    model_id="microsoft/harrier-oss-v1-0.6b",
    revision=None,
    vector_dimension=1024,
)

HARRIER_TOKENIZER = TokenizerDefinition(
    model_id="microsoft/harrier-oss-v1-0.6b",
    revision=None,
)

BM25_MODEL = SparseModelDefinition(
    model_id="Qdrant/bm25",
    revision=None,
)
