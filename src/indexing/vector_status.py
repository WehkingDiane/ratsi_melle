"""Status helpers for the local SQLite and Qdrant vector index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.indexing.id_strategy import stable_document_id
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR

COLLECTION_NAME = "ratsi_documents"


def vector_index_status(
    local_index_db: Path = LOCAL_INDEX_DB,
    qdrant_dir: Path = QDRANT_DIR,
) -> dict[str, Any]:
    """Return a robust status snapshot for the local vector index."""

    db_path = Path(local_index_db)
    qdrant_path = Path(qdrant_dir)
    warnings: list[str] = []
    status: dict[str, Any] = {
        "local_index_exists": db_path.is_file(),
        "qdrant_exists": qdrant_path.exists(),
        "sqlite_document_count": None,
        "indexable_document_count": None,
        "indexed_vector_count": None,
        "missing_vector_count": None,
        "orphaned_vector_count": None,
        "coverage_percent": None,
        "latest_session_date": None,
        "latest_document_date": None,
        "warnings": warnings,
        "status": "unknown",
    }

    current_ids: set[int] | None = None
    if not status["local_index_exists"]:
        warnings.append(f"Lokaler SQLite-Index fehlt: {db_path}")
        status["status"] = "missing_local_index"
    else:
        current_ids = _read_sqlite_document_ids(db_path, status, warnings)

    indexed_ids: set[int] | None = None
    if not status["qdrant_exists"]:
        warnings.append(f"Qdrant/Vektorindex fehlt: {qdrant_path}")
        status["indexed_vector_count"] = 0
        if status["status"] == "unknown":
            status["status"] = "missing_qdrant"
    else:
        indexed_ids = _read_qdrant_ids(qdrant_path, status, warnings)

    if current_ids is not None and indexed_ids is not None:
        missing_ids = current_ids - indexed_ids
        orphaned_ids = indexed_ids - current_ids
        indexed_current_ids = current_ids & indexed_ids
        status["missing_vector_count"] = len(missing_ids)
        status["orphaned_vector_count"] = len(orphaned_ids)
        indexable_count = status["indexable_document_count"] or 0
        if indexable_count:
            status["coverage_percent"] = round(len(indexed_current_ids) * 100 / indexable_count, 1)
        else:
            status["coverage_percent"] = 100.0

    if status["status"] == "unknown":
        if warnings:
            status["status"] = "warning"
        elif status["missing_vector_count"] == 0 and status["orphaned_vector_count"] == 0:
            status["status"] = "ok"
        else:
            status["status"] = "needs_update"
    return status


def _read_sqlite_document_ids(
    db_path: Path,
    status: dict[str, Any],
    warnings: list[str],
) -> set[int] | None:
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            document_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            latest_session_date = conn.execute("SELECT MAX(date) FROM sessions").fetchone()[0]
            rows = conn.execute(
                """
                SELECT d.session_id, d.url, d.agenda_item, s.date
                FROM documents d
                LEFT JOIN sessions s ON s.session_id = d.session_id
                ORDER BY d.id
                """
            ).fetchall()
    except (sqlite3.Error, OSError) as exc:
        warnings.append(f"Lokaler SQLite-Index konnte nicht gelesen werden: {exc}")
        status["status"] = "warning"
        return None

    current_ids = {
        stable_document_id(
            str(row["session_id"] or ""),
            str(row["url"] or ""),
            str(row["agenda_item"] or ""),
        )
        for row in rows
    }
    status["sqlite_document_count"] = int(document_count or 0)
    status["indexable_document_count"] = len(current_ids)
    status["latest_session_date"] = latest_session_date or None
    status["latest_document_date"] = latest_session_date or None
    if len(current_ids) != int(document_count or 0):
        warnings.append(
            "Einige SQLite-Dokumente teilen sich dieselbe stabile Vektor-ID; "
            "Coverage wird anhand eindeutiger IDs berechnet."
        )
    return current_ids


def _read_qdrant_ids(
    qdrant_dir: Path,
    status: dict[str, Any],
    warnings: list[str],
) -> set[int] | None:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        warnings.append(f"Qdrant-Status konnte nicht gelesen werden; qdrant-client fehlt: {exc}")
        status["status"] = "warning"
        return None

    try:
        client = QdrantClient(path=str(qdrant_dir))
        collections = [collection.name for collection in client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            warnings.append(f"Qdrant-Collection fehlt: {COLLECTION_NAME}")
            status["indexed_vector_count"] = 0
            return set()

        info = client.get_collection(collection_name=COLLECTION_NAME)
        status["indexed_vector_count"] = int(info.points_count or 0)
        indexed_ids: set[int] = set()
        offset: int | None = None
        while True:
            records, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                with_payload=False,
                with_vectors=False,
                limit=1000,
                offset=offset,
            )
            indexed_ids.update(record.id for record in records if isinstance(record.id, int))
            if next_offset is None:
                break
            offset = next_offset
        return indexed_ids
    except Exception as exc:  # noqa: BLE001 - Qdrant can fail for locks/schema/runtime issues.
        warnings.append(f"Qdrant/Vektorindex konnte nicht gelesen werden: {exc}")
        status["status"] = "warning"
        return None
