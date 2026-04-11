"""Qdrant local file-based vector store for ratsi_melle documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_COLLECTION_NAME = "ratsi_documents"
_DENSE_VECTOR = "harrier"
_SPARSE_VECTOR = "bm25"
_EMBEDDING_DIM = 1024


class DocumentVectorStore:
    """Manages a local Qdrant vector store persisted on disk.

    The collection uses two named vector fields:
    - ``harrier``: 1024-dim dense vectors from microsoft/harrier-oss-v1-0.6b
    - ``bm25``:    sparse BM25 vectors from fastembed for keyword matching

    Hybrid search combines both via Reciprocal Rank Fusion (RRF).

    Args:
        qdrant_path: Directory where the Qdrant storage files will be kept.
    """

    def __init__(self, qdrant_path: Path) -> None:
        self._path = qdrant_path
        self._client: Any = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient

            self._path.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(self._path))
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_collection(self) -> None:
        """Create the Qdrant collection if it does not already exist.

        Collection schema:
        - Named dense vector ``harrier`` (cosine, dim 1024)
        - Named sparse vector ``bm25`` (for keyword search)
        """
        from qdrant_client.models import (
            Distance,
            VectorParams,
            SparseVectorParams,
            SparseIndexParams,
        )

        client = self._get_client()
        existing = [col.name for col in client.get_collections().collections]
        if _COLLECTION_NAME not in existing:
            client.create_collection(
                collection_name=_COLLECTION_NAME,
                vectors_config={
                    _DENSE_VECTOR: VectorParams(
                        size=_EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    _SPARSE_VECTOR: SparseVectorParams(
                        index=SparseIndexParams(on_disk=False),
                    ),
                },
            )

    def upsert_batch(self, points: list[dict]) -> None:
        """Insert or update a batch of vector points.

        Each point is a dict with keys:
            - ``id`` (int): Unique stable document ID.
            - ``dense_vector`` (list[float]): Harrier embedding, length 1024.
            - ``sparse_vector`` (dict): BM25 sparse vector with ``indices``
              and ``values`` keys.
            - ``payload`` (dict): Arbitrary metadata stored alongside.
        """
        from qdrant_client.models import PointStruct, SparseVector

        client = self._get_client()
        qdrant_points = [
            PointStruct(
                id=p["id"],
                vector={
                    _DENSE_VECTOR: p["dense_vector"],
                    _SPARSE_VECTOR: SparseVector(
                        indices=p["sparse_vector"]["indices"],
                        values=p["sparse_vector"]["values"],
                    ),
                },
                payload=p["payload"],
            )
            for p in points
        ]
        client.upsert(collection_name=_COLLECTION_NAME, points=qdrant_points)

    def search(
        self,
        query_dense: list[float],
        query_sparse: dict,
        limit: int = 10,
        session_id: str | None = None,
    ) -> list[dict]:
        """Run hybrid search combining dense (Harrier) and sparse (BM25) vectors.

        Uses Reciprocal Rank Fusion (RRF) to merge results from both retrieval
        methods. Keyword matches (BM25) and semantic matches (Harrier) each
        contribute to the final ranking.

        Args:
            query_dense: Dense query vector of length 1024.
            query_sparse: BM25 sparse query dict with ``indices`` and ``values``.
            limit: Maximum number of results to return.
            session_id: When set, restrict results to this session.

        Returns:
            List of result dicts with keys: ``doc_id``, ``score``, ``title``,
            ``session_id``, ``agenda_item``, ``date``, ``committee``,
            ``document_type``, ``url``, ``local_path``.
        """
        from qdrant_client.models import (
            Filter,
            FieldCondition,
            MatchValue,
            Prefetch,
            FusionQuery,
            Fusion,
            SparseVector,
        )

        client = self._get_client()

        search_filter: Filter | None = None
        if session_id is not None:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="session_id",
                        match=MatchValue(value=session_id),
                    )
                ]
            )

        # Prefetch candidates from both retrieval methods, then fuse
        response = client.query_points(
            collection_name=_COLLECTION_NAME,
            prefetch=[
                Prefetch(
                    query=query_dense,
                    using=_DENSE_VECTOR,
                    limit=limit * 3,
                    filter=search_filter,
                ),
                Prefetch(
                    query=SparseVector(
                        indices=query_sparse["indices"],
                        values=query_sparse["values"],
                    ),
                    using=_SPARSE_VECTOR,
                    limit=limit * 3,
                    filter=search_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        )

        results: list[dict] = []
        for hit in response.points:
            payload = hit.payload or {}
            results.append(
                {
                    "doc_id": hit.id,
                    "score": hit.score,
                    "title": payload.get("title", ""),
                    "session_id": payload.get("session_id"),
                    "agenda_item": payload.get("agenda_item"),
                    "date": payload.get("date", ""),
                    "committee": payload.get("committee", ""),
                    "document_type": payload.get("document_type", ""),
                    "url": payload.get("url", ""),
                    "local_path": payload.get("local_path", ""),
                }
            )
        return results

    def count(self) -> int:
        """Return the total number of indexed document vectors."""
        client = self._get_client()
        try:
            info = client.get_collection(collection_name=_COLLECTION_NAME)
            return info.points_count or 0
        except Exception:
            return 0

    def get_indexed_ids(self) -> set[int]:
        """Return the set of all document IDs that have already been indexed."""
        client = self._get_client()
        try:
            ids: set[int] = set()
            offset: int | None = None
            while True:
                records, next_offset = client.scroll(
                    collection_name=_COLLECTION_NAME,
                    with_payload=False,
                    with_vectors=False,
                    limit=1000,
                    offset=offset,
                )
                for record in records:
                    if isinstance(record.id, int):
                        ids.add(record.id)
                if next_offset is None:
                    break
                offset = next_offset
            return ids
        except Exception:
            return set()

    def delete_ids(self, ids: set[int]) -> None:
        """Remove vector points by their IDs (used for reconciliation)."""
        if not ids:
            return
        from qdrant_client.models import PointIdsList

        client = self._get_client()
        client.delete(
            collection_name=_COLLECTION_NAME,
            points_selector=PointIdsList(points=list(ids)),
        )
