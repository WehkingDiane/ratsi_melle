"""Hybrid dense/sparse vectorization for document indexing."""

from __future__ import annotations

from typing import Protocol


class DenseEmbedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return dense vectors for the given texts."""


class SparseEncoder(Protocol):
    def encode_documents(self, texts: list[str]) -> list[dict]:
        """Return sparse vectors for the given texts."""


class HybridVectorizer:
    """Combine dense Harrier vectors and sparse BM25 vectors by document order."""

    def __init__(self, dense_embedder: DenseEmbedder, sparse_encoder: SparseEncoder) -> None:
        self._dense_embedder = dense_embedder
        self._sparse_encoder = sparse_encoder

    def encode_documents(self, texts: list[str]) -> list[dict]:
        """Encode texts into paired dense and sparse vectors."""
        dense_vectors = self._dense_embedder.embed_documents(texts)
        sparse_vectors = self._sparse_encoder.encode_documents(texts)

        if len(dense_vectors) != len(texts) or len(sparse_vectors) != len(texts):
            raise ValueError("Vectorizer outputs must match input document count.")

        return [
            {
                "dense_vector": dense_vec,
                "sparse_vector": sparse_vec,
            }
            for dense_vec, sparse_vec in zip(dense_vectors, sparse_vectors)
        ]
