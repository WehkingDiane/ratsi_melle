"""SQLite persistence and FTS search for Landkreis publications."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from src.fetching.landkreis.models import LandkreisDocument, LandkreisPublication

MAX_FTS_BODY_CHARS = 80_000


class LandkreisPublicationStore:
    """Owns the separated Landkreis publications SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        """Create or migrate the Landkreis publication schema."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS publications (
                    publication_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    date TEXT,
                    year INTEGER,
                    title TEXT NOT NULL,
                    detail_url TEXT NOT NULL,
                    list_url TEXT NOT NULL,
                    local_dir TEXT,
                    page_text TEXT,
                    retrieved_at TEXT
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    publication_id TEXT NOT NULL,
                    title TEXT,
                    url TEXT NOT NULL,
                    local_path TEXT,
                    content_type TEXT,
                    content_length INTEGER,
                    sha1 TEXT,
                    retrieved_at TEXT,
                    UNIQUE(publication_id, url)
                );

                CREATE TABLE IF NOT EXISTS extracted_texts (
                    document_id INTEGER PRIMARY KEY,
                    extraction_status TEXT,
                    parsing_quality TEXT,
                    extracted_text TEXT,
                    extracted_char_count INTEGER,
                    page_count INTEGER,
                    extraction_error TEXT,
                    ocr_needed INTEGER,
                    extraction_pipeline_version TEXT,
                    extracted_at TEXT
                );

                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_landkreis_publications_source
                    ON publications(source);
                CREATE INDEX IF NOT EXISTS idx_landkreis_publications_date
                    ON publications(date);
                CREATE INDEX IF NOT EXISTS idx_landkreis_documents_publication
                    ON documents(publication_id);
                """
            )
            self._create_fts(conn)

    def reset(self) -> None:
        """Clear all indexed Landkreis rows while keeping the schema."""

        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                DELETE FROM publications_fts;
                DELETE FROM extracted_texts;
                DELETE FROM documents;
                DELETE FROM publications;
                DELETE FROM crawl_runs;
                """
            )

    def upsert_publication(self, publication: LandkreisPublication) -> None:
        """Insert or update one publication and its document rows."""

        self.initialize()
        date_value = publication.date.isoformat() if publication.date else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO publications
                (publication_id, source, date, year, title, detail_url, list_url, local_dir, page_text, retrieved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(publication_id) DO UPDATE SET
                    source = excluded.source,
                    date = excluded.date,
                    year = excluded.year,
                    title = excluded.title,
                    detail_url = excluded.detail_url,
                    list_url = excluded.list_url,
                    local_dir = excluded.local_dir,
                    page_text = excluded.page_text,
                    retrieved_at = excluded.retrieved_at
                """,
                (
                    publication.publication_id,
                    publication.source,
                    date_value,
                    publication.year,
                    publication.title,
                    publication.detail_url,
                    publication.list_url,
                    publication.local_dir,
                    publication.page_text,
                    publication.retrieved_at,
                ),
            )
            for document in publication.documents:
                conn.execute(
                    """
                    INSERT INTO documents
                    (publication_id, title, url, local_path, content_type, content_length, sha1, retrieved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(publication_id, url) DO UPDATE SET
                        title = excluded.title,
                        local_path = excluded.local_path,
                        content_type = excluded.content_type,
                        content_length = excluded.content_length,
                        sha1 = excluded.sha1,
                        retrieved_at = excluded.retrieved_at
                    """,
                    (
                        publication.publication_id,
                        document.title,
                        document.url,
                        document.local_path,
                        document.content_type,
                        document.content_length,
                        document.sha1,
                        document.retrieved_at,
                    ),
                )
            self._refresh_fts(conn, [publication.publication_id])

    def upsert_extraction(
        self,
        document_id: int,
        result: dict[str, object],
        *,
        refresh_fts: bool = True,
    ) -> str | None:
        """Store text extraction metadata for one document and refresh FTS."""

        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO extracted_texts
                (
                    document_id,
                    extraction_status,
                    parsing_quality,
                    extracted_text,
                    extracted_char_count,
                    page_count,
                    extraction_error,
                    ocr_needed,
                    extraction_pipeline_version,
                    extracted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    extraction_status = excluded.extraction_status,
                    parsing_quality = excluded.parsing_quality,
                    extracted_text = excluded.extracted_text,
                    extracted_char_count = excluded.extracted_char_count,
                    page_count = excluded.page_count,
                    extraction_error = excluded.extraction_error,
                    ocr_needed = excluded.ocr_needed,
                    extraction_pipeline_version = excluded.extraction_pipeline_version,
                    extracted_at = excluded.extracted_at
                """,
                (
                    document_id,
                    result.get("extraction_status"),
                    result.get("parsing_quality"),
                    result.get("extracted_text"),
                    result.get("extracted_char_count"),
                    result.get("page_count"),
                    result.get("extraction_error"),
                    1 if result.get("ocr_needed") else 0,
                    result.get("extraction_pipeline_version"),
                    result.get("extracted_at"),
                ),
            )
            rows = conn.execute(
                """
                SELECT DISTINCT publication_id
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchall()
            publication_ids = [row[0] for row in rows if row and row[0]]
            if refresh_fts:
                self._refresh_fts(conn, publication_ids)
            return publication_ids[0] if publication_ids else None

    def refresh_publication_fts(self, publication_ids: Iterable[str]) -> None:
        """Refresh FTS rows for selected publications."""

        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            self._refresh_fts(conn, publication_ids)

    def document_rows(self) -> list[dict[str, Any]]:
        """Return document rows with publication metadata."""

        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.publication_id,
                    d.title,
                    d.url,
                    d.local_path,
                    d.content_type,
                    p.source,
                    p.date,
                    p.title AS publication_title
                FROM documents d
                JOIN publications p ON p.publication_id = d.publication_id
                ORDER BY p.date DESC, p.title ASC, d.title ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def search(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Search Landkreis publications via SQLite FTS5."""

        self.initialize()
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        match_query = " AND ".join(_quote_fts_term(term) for term in normalized_query.split())
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    p.publication_id,
                    p.source,
                    p.date,
                    p.title,
                    p.detail_url,
                    p.local_dir,
                    snippet(publications_fts, 3, '[', ']', ' ... ', 12) AS snippet,
                    bm25(publications_fts) AS rank
                FROM publications_fts
                JOIN publications p ON p.publication_id = publications_fts.publication_id
                WHERE publications_fts MATCH ?
                ORDER BY rank ASC, p.date DESC
                LIMIT ?
                """,
                (match_query, max(1, min(int(limit), 200))),
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def _create_fts(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS publications_fts USING fts5(
                publication_id UNINDEXED,
                source,
                title,
                body,
                date,
                detail_url UNINDEXED
            )
            """
        )

    @staticmethod
    def _refresh_fts(conn: sqlite3.Connection, publication_ids: Iterable[str]) -> None:
        ids = [value for value in publication_ids if value]
        if not ids:
            return
        for publication_id in ids:
            conn.execute("DELETE FROM publications_fts WHERE publication_id = ?", (publication_id,))
            row = conn.execute(
                """
                SELECT source, title, date, detail_url, page_text
                FROM publications
                WHERE publication_id = ?
                """,
                (publication_id,),
            ).fetchone()
            if row is None:
                continue
            extracted = conn.execute(
                """
                SELECT GROUP_CONCAT(COALESCE(et.extracted_text, ''), char(10) || char(10))
                FROM documents d
                LEFT JOIN extracted_texts et ON et.document_id = d.id
                WHERE d.publication_id = ?
                """,
                (publication_id,),
            ).fetchone()
            body = "\n\n".join(part for part in (row[4] or "", extracted[0] if extracted else "") if part)
            if len(body) > MAX_FTS_BODY_CHARS:
                body = body[:MAX_FTS_BODY_CHARS]
            conn.execute(
                """
                INSERT INTO publications_fts
                (publication_id, source, title, body, date, detail_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (publication_id, row[0], row[1], body, row[2], row[3]),
            )


def _quote_fts_term(term: str) -> str:
    escaped = term.replace('"', '""')
    return f'"{escaped}"'
