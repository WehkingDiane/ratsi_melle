from __future__ import annotations

import sqlite3
from pathlib import Path

from src.indexing.vector_status import vector_index_status


def test_vector_index_status_reports_missing_local_index(tmp_path: Path) -> None:
    status = vector_index_status(
        local_index_db=tmp_path / "missing.sqlite",
        qdrant_dir=tmp_path / "qdrant",
    )

    assert status["local_index_exists"] is False
    assert status["qdrant_exists"] is False
    assert status["status"] == "missing_local_index"
    assert status["warnings"]


def test_vector_index_status_reports_sqlite_without_qdrant(tmp_path: Path) -> None:
    db_path = tmp_path / "local_index.sqlite"
    _write_local_index(db_path)

    status = vector_index_status(
        local_index_db=db_path,
        qdrant_dir=tmp_path / "missing_qdrant",
    )

    assert status["local_index_exists"] is True
    assert status["qdrant_exists"] is False
    assert status["sqlite_document_count"] == 2
    assert status["indexable_document_count"] == 2
    assert status["indexed_vector_count"] == 0
    assert status["latest_session_date"] == "2026-03-11"
    assert status["latest_document_date"] == "2026-03-11"
    assert status["status"] == "missing_qdrant"
    assert any("Qdrant" in warning for warning in status["warnings"])


def test_vector_index_status_uses_document_backed_latest_document_date(tmp_path: Path) -> None:
    db_path = tmp_path / "local_index.sqlite"
    _write_local_index(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("9999", "2026-12-01", "Rat", "Sitzung ohne Dokumente", "18:00", "Rathaus", "", ""),
        )

    status = vector_index_status(
        local_index_db=db_path,
        qdrant_dir=tmp_path / "missing_qdrant",
    )

    assert status["latest_session_date"] == "2026-12-01"
    assert status["latest_document_date"] == "2026-03-11"


def test_vector_index_status_warns_on_sqlite_error(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.sqlite"
    db_path.write_text("not a sqlite database", encoding="utf-8")

    status = vector_index_status(
        local_index_db=db_path,
        qdrant_dir=tmp_path / "qdrant",
    )

    assert status["local_index_exists"] is True
    assert status["status"] == "warning"
    assert status["sqlite_document_count"] is None
    assert any("SQLite" in warning for warning in status["warnings"])


def _write_local_index(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT,
                committee TEXT,
                meeting_name TEXT,
                start_time TEXT,
                location TEXT,
                detail_url TEXT,
                session_path TEXT
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                title TEXT,
                category TEXT,
                document_type TEXT,
                agenda_item TEXT,
                url TEXT,
                local_path TEXT,
                content_type TEXT,
                content_length INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("7123", "2026-03-11", "Rat", "Ratssitzung", "18:00", "Rathaus", "", ""),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Vorlage", "", "Beschlussvorlage", "Oe 7", "https://example.test/1", "", "text/plain", 12),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "7123", "Anlage", "", "Anlage", "Oe 8", "https://example.test/2", "", "text/plain", 12),
        )
