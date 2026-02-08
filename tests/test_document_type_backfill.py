from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts import build_local_index


def test_build_local_index_backfills_document_type_for_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "processed" / "local_index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT,
                year INTEGER,
                month INTEGER,
                committee TEXT,
                meeting_name TEXT,
                start_time TEXT,
                location TEXT,
                detail_url TEXT,
                session_path TEXT
            );

            CREATE TABLE agenda_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                number TEXT,
                title TEXT,
                reporter TEXT,
                status TEXT,
                decision TEXT,
                documents_present INTEGER
            );

            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                title TEXT,
                category TEXT,
                agenda_item TEXT,
                url TEXT,
                local_path TEXT,
                content_type TEXT,
                content_length INTEGER,
                document_type TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO documents
            (session_id, title, category, agenda_item, url, local_path, content_type, content_length, document_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "123",
                "Protokoll öffentlich",
                "PR",
                None,
                "https://example.org/protokoll.pdf",
                "session-documents/protokoll.pdf",
                "application/pdf",
                100,
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO documents
            (session_id, title, category, agenda_item, url, local_path, content_type, content_length, document_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "124",
                "Altwert",
                "PR",
                None,
                "https://example.org/legacy.pdf",
                "session-documents/legacy.pdf",
                "application/pdf",
                90,
                "niederschrift",
            ),
        )
        conn.commit()

    build_local_index.build_index(
        data_root=tmp_path / "data" / "raw",
        output_path=db_path,
        refresh_existing=False,
        only_refresh=False,
    )

    with sqlite3.connect(db_path) as conn:
        values = [row[0] for row in conn.execute("SELECT document_type FROM documents ORDER BY id").fetchall()]
    assert values == ["protokoll", "protokoll"]
