"""BM25 sparse vector generator using fastembed for hybrid search."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_BM25_MODEL = "Qdrant/bm25"


class BM25Encoder:
    """Generates BM25 sparse vectors via fastembed.

    Lazy-loads the model on first use. Used alongside the Harrier dense
    embedder for hybrid (semantic + keyword) search.
    """

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from fastembed import SparseTextEmbedding
            self._model = SparseTextEmbedding(model_name=_BM25_MODEL)
        return self._model

    def encode_documents(self, texts: list[str]) -> list[dict]:
        """Encode a list of texts into BM25 sparse vectors.

        Returns:
            List of dicts with ``indices`` and ``values`` keys.
        """
        model = self._get_model()
        results = []
        for embedding in model.embed(texts):
            results.append({
                "indices": embedding.indices.tolist(),
                "values": embedding.values.tolist(),
            })
        return results

    def encode_query(self, text: str) -> dict:
        """Encode a single query into a BM25 sparse vector."""
        model = self._get_model()
        embeddings = list(model.query_embed(text))
        emb = embeddings[0]
        return {
            "indices": emb.indices.tolist(),
            "values": emb.values.tolist(),
        }
