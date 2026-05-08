"""Status and overview data for web UI pages."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import paths
from .outputs import list_analysis_outputs
from .sessions import list_sessions


def service_status() -> dict[str, Any]:
    """Return lightweight status for service pages."""

    raw_data_root = paths.REPO_ROOT / "data" / "raw"
    online_index_db = paths.REPO_ROOT / "data" / "db" / "online_session_index.sqlite"
    local_session_count = _table_count(paths.LOCAL_INDEX_DB, "sessions")
    local_document_count = _table_count(paths.LOCAL_INDEX_DB, "documents")
    online_session_count = _table_count(online_index_db, "sessions")
    raw_session_count = _raw_session_directory_count(raw_data_root)
    qdrant_dir = paths.REPO_ROOT / "data" / "db" / "qdrant"

    return {
        "local_index_exists": paths.LOCAL_INDEX_DB.exists() and paths.LOCAL_INDEX_DB.stat().st_size > 0,
        "online_index_exists": online_index_db.exists(),
        "qdrant_exists": qdrant_dir.exists(),
        "raw_data_exists": raw_data_root.exists(),
        "local_index_path": "data/db/local_index.sqlite",
        "online_index_path": "data/db/online_session_index.sqlite",
        "qdrant_path": "data/db/qdrant/",
        "raw_data_path": "data/raw/",
        "raw_session_count": raw_session_count,
        "raw_data_summary": _count_label(raw_session_count, "Sitzungsordner"),
        "local_session_count": local_session_count,
        "local_document_count": local_document_count,
        "local_index_summary": _local_index_label(local_session_count, local_document_count),
        "online_session_count": online_session_count,
        "online_index_summary": _count_label(online_session_count, "Sitzungen"),
        "qdrant_summary": "vorhanden" if qdrant_dir.exists() else "fehlt",
    }


def source_overview() -> dict[str, Any]:
    """Return basic source availability for overview pages."""

    return {
        "local_index_exists": paths.LOCAL_INDEX_DB.exists() and paths.LOCAL_INDEX_DB.stat().st_size > 0,
        "analysis_outputs_exists": paths.ANALYSIS_OUTPUTS_DIR.exists(),
        "session_count": len(list_sessions()),
        "analysis_count": len(list_analysis_outputs()),
        "local_index_path": str(paths.LOCAL_INDEX_DB.relative_to(paths.REPO_ROOT)),
        "analysis_outputs_path": str(paths.ANALYSIS_OUTPUTS_DIR.relative_to(paths.REPO_ROOT)),
    }


def _table_count(db_path, table_name: str) -> int | None:
    if not db_path.exists() or db_path.stat().st_size <= 0:
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if not table_exists:
                return None
            row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else None


def _raw_session_directory_count(raw_data_root) -> int | None:
    if not raw_data_root.exists():
        return None
    count = 0
    for year_dir in raw_data_root.iterdir():
        if not year_dir.is_dir():
            continue
        for entry in year_dir.iterdir():
            if not entry.is_dir():
                continue
            if _looks_like_session_directory(entry):
                count += 1
            else:
                count += sum(
                    1 for session_dir in entry.iterdir()
                    if session_dir.is_dir() and _looks_like_session_directory(session_dir)
                )
    return count


def _looks_like_session_directory(path) -> bool:
    return (path / "manifest.json").is_file() or (path / "agenda").is_dir() or (path / "session-documents").is_dir()


def _count_label(count: int | None, noun: str) -> str:
    if count is None:
        return "fehlt"
    return f"{count} {noun}"


def _local_index_label(session_count: int | None, document_count: int | None) -> str:
    if session_count is None and document_count is None:
        return "fehlt"
    sessions = session_count if session_count is not None else 0
    documents = document_count if document_count is not None else 0
    return f"{sessions} Sitzungen / {documents} Dokumente"
