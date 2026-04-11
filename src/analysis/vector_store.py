"""Qdrant local file-based vector store for ratsi_melle documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_COLLECTION_NAME = "ratsi_documents"
_EMBEDDING_DIM = 1024


class DocumentVectorStore:
    """Manages a local Qdrant vector store persisted on disk.

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
        """Create the Qdrant collection if it does not already exist."""
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()
        existing = [col.name for col in client.get_collections().collections]
        if _COLLECTION_NAME not in existing:
            client.create_collection(
                collection_name=_COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=_EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

    def upsert_batch(self, points: list[dict]) -> None:
        """Insert or update a batch of vector points.

        Each point is a dict with keys:
            - ``id`` (int): Unique document ID.
            - ``vector`` (list[float]): Embedding vector of length 1024.
            - ``payload`` (dict): Arbitrary metadata stored alongside the vector.
        """
        from qdrant_client.models import PointStruct

        client = self._get_client()
        qdrant_points = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p["payload"],
            )
            for p in points
        ]
        client.upsert(collection_name=_COLLECTION_NAME, points=qdrant_points)

    def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        session_id: int | None = None,
    ) -> list[dict]:
        """Run a nearest-neighbour search.

        Args:
            query_vector: Query embedding of length 1024.
            limit: Maximum number of results to return.
            session_id: When set, restrict results to this session.

        Returns:
            List of result dicts with keys:
            ``doc_id``, ``score``, ``title``, ``session_id``,
            ``agenda_item``, ``url``, ``local_path``.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

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

        hits = client.search(
            collection_name=_COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit,
            query_filter=search_filter,
            with_payload=True,
        )

        results: list[dict] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "doc_id": hit.id,
                    "score": hit.score,
                    "title": payload.get("title", ""),
                    "session_id": payload.get("session_id"),
                    "agenda_item": payload.get("agenda_item"),
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
