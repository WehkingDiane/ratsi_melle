"""BM25 sparse vector generator using fastembed for hybrid search."""

from __future__ import annotations

from src.config.embedding_model_status import prepared_model_path
from src.config.embedding_models import BM25_MODEL



class BM25Encoder:
    """Generates BM25 sparse vectors via fastembed.

    Lazy-loads the model on first use. Used alongside the Harrier dense
    embedder for hybrid (semantic + keyword) search.
    """

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            model_path = prepared_model_path("sparse_model")
            from fastembed import SparseTextEmbedding
            self._model = SparseTextEmbedding(
                model_name=BM25_MODEL.model_id,
                specific_model_path=str(model_path),
                local_files_only=True,
            )
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
