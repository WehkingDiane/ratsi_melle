"""Build a local SQLite index by fetching SessionNet sessions without downloading documents."""

from __future__ import annotations

import argparse
from datetime import timezone
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - defensive
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching import SessionNetClient  # noqa: E402  (import after sys.path manipulation)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, help="Year to fetch meetings for")
    parser.add_argument(
        "--months",
        type=int,
        nargs="*",
        default=tuple(range(1, 13)),
        help="Months to fetch (1-12). Defaults to the full year.",
    )
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default="https://session.melle.info/bi",
        help="Override the SessionNet base URL.",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Python logging level",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/online_session_index.sqlite"),
        help="SQLite output path.",
    )
    parser.add_argument(
        "--migrate-from",
        type=Path,
        default=Path("data/processed/local_index.sqlite"),
        help="Copy an existing SQLite database to the output path if output is missing.",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Rebuild entries for sessions that already exist in the database.",
    )
    parser.add_argument(
        "--only-refresh",
        action="store_true",
        help="Only refresh existing sessions; do not insert new ones.",
    )
    return parser.parse_args()


def build_session_db(
    client: SessionNetClient,
    year: int,
    months: Iterable[int],
    output_path: Path,
    refresh_existing: bool,
    only_refresh: bool,
    migrate_from: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _maybe_migrate_database(output_path, migrate_from)
    with sqlite3.connect(output_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        _create_tables(conn)
        _populate(conn, client, year, months, refresh_existing, only_refresh)


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
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

        CREATE TABLE IF NOT EXISTS agenda_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            number TEXT,
            title TEXT,
            reporter TEXT,
            status TEXT,
            decision TEXT,
            documents_present INTEGER
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            title TEXT,
            category TEXT,
            document_type TEXT,
            agenda_item TEXT,
            url TEXT,
            local_path TEXT,
            sha1 TEXT,
            retrieved_at TEXT,
            content_type TEXT,
            content_length INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
        CREATE INDEX IF NOT EXISTS idx_sessions_committee ON sessions(committee);
        CREATE INDEX IF NOT EXISTS idx_agenda_session ON agenda_items(session_id);
        CREATE INDEX IF NOT EXISTS idx_docs_session ON documents(session_id);
        """
    )
    _ensure_documents_columns(conn)
    _migrate_legacy_document_types(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(document_type);")
    _backfill_document_types(conn)


def _populate(
    conn: sqlite3.Connection,
    client: SessionNetClient,
    year: int,
    months: Iterable[int],
    refresh_existing: bool,
    only_refresh: bool,
) -> None:
    session_count = 0
    agenda_count = 0
    doc_count = 0
    seen_sessions: set[str] = set()
    existing = {
        row[0]
        for row in conn.execute("SELECT session_id FROM sessions").fetchall()
        if row and row[0]
    }

    for month in months:
        references = client.fetch_month(year=year, month=month)
        for reference in references:
            if reference.session_id in seen_sessions:
                continue
            if reference.session_id in existing and not refresh_existing:
                continue
            if reference.session_id not in existing and only_refresh:
                continue
            seen_sessions.add(reference.session_id)
            detail = client.fetch_session(reference)

            if reference.session_id in existing and refresh_existing:
                conn.execute("DELETE FROM agenda_items WHERE session_id = ?", (reference.session_id,))
                conn.execute("DELETE FROM documents WHERE session_id = ?", (reference.session_id,))

            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, date, year, month, committee, meeting_name, start_time, location, detail_url, session_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reference.session_id,
                    reference.date.isoformat(),
                    reference.date.year,
                    reference.date.month,
                    reference.committee,
                    reference.meeting_name,
                    reference.start_time,
                    reference.location,
                    reference.detail_url,
                    None,
                ),
            )
            session_count += 1

            agenda_count += _insert_agenda_items(conn, reference.session_id, detail)
            doc_count += _insert_documents(conn, reference.session_id, detail)

    conn.commit()
    print(
        "Indexed sessions={0} agenda_items={1} documents={2}".format(
            session_count, agenda_count, doc_count
        )
    )


def _insert_agenda_items(
    conn: sqlite3.Connection, session_id: str, detail
) -> int:
    inserted = 0
    for item in detail.agenda_items:
        conn.execute(
            """
            INSERT INTO agenda_items
            (session_id, number, title, reporter, status, decision, documents_present)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(item.number or ""),
                item.title,
                item.reporter,
                item.status,
                SessionNetClient._derive_decision_outcome(item.status),
                1 if item.documents else 0,
            ),
        )
        inserted += 1
    return inserted


def _insert_documents(
    conn: sqlite3.Connection, session_id: str, detail
) -> int:
    inserted = 0
    retrieved_at = detail.retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    for document in detail.session_documents:
        document_type = _infer_document_type(
            title=document.title,
            category=document.category,
            content_type=None,
            url=document.url,
            local_path=None,
        )
        conn.execute(
            """
            INSERT INTO documents
            (
                session_id,
                title,
                category,
                document_type,
                agenda_item,
                url,
                local_path,
                sha1,
                retrieved_at,
                content_type,
                content_length
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                document.title,
                document.category,
                document_type,
                None,
                document.url,
                None,
                None,
                retrieved_at,
                None,
                None,
            ),
        )
        inserted += 1

    for agenda_item in detail.agenda_items:
        for document in agenda_item.documents:
            document_type = _infer_document_type(
                title=document.title,
                category=document.category,
                content_type=None,
                url=document.url,
                local_path=None,
            )
            conn.execute(
                """
                INSERT INTO documents
                (
                    session_id,
                    title,
                    category,
                    document_type,
                    agenda_item,
                    url,
                    local_path,
                    sha1,
                    retrieved_at,
                    content_type,
                    content_length
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    document.title,
                    document.category,
                    document_type,
                    agenda_item.number,
                    document.url,
                    None,
                    None,
                    retrieved_at,
                    None,
                    None,
                ),
            )
            inserted += 1

    return inserted


def _ensure_documents_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    for column_name, column_type in (
        ("document_type", "TEXT"),
        ("sha1", "TEXT"),
        ("retrieved_at", "TEXT"),
    ):
        if column_name in columns:
            continue
        conn.execute(f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}")


def _backfill_document_types(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, title, category, content_type, url, local_path
        FROM documents
        WHERE document_type IS NULL OR TRIM(document_type) = ''
        """
    ).fetchall()
    if not rows:
        return
    updates = []
    for row in rows:
        doc_id, title, category, content_type, url, local_path = row
        updates.append(
            (
                _infer_document_type(
                    title=title,
                    category=category,
                    content_type=content_type,
                    url=url,
                    local_path=local_path,
                ),
                doc_id,
            )
        )
    conn.executemany("UPDATE documents SET document_type = ? WHERE id = ?", updates)


def _migrate_legacy_document_types(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE documents
        SET document_type = 'protokoll'
        WHERE LOWER(COALESCE(document_type, '')) = 'niederschrift'
        """
    )


def _infer_document_type(
    *,
    title: str | None,
    category: str | None,
    content_type: str | None,
    url: str | None,
    local_path: str | None,
) -> str:
    normalized_title = (title or "").lower()
    normalized_category = (category or "").lower()
    normalized_content_type = (content_type or "").lower()
    normalized_url = (url or "").lower()
    normalized_path = (local_path or "").lower()

    if normalized_category in {"pr", "ni"}:
        return "protokoll"
    if normalized_category in {"bm", "be", "bek"}:
        return "bekanntmachung"
    if normalized_category in {"bv"}:
        return "beschlussvorlage"
    if normalized_category in {"vo", "vl"}:
        return "vorlage"

    search_blob = " ".join(
        (
            normalized_title,
            normalized_category,
            normalized_content_type,
            normalized_url,
            normalized_path,
        )
    )
    if any(keyword in search_blob for keyword in ("niederschrift", "protokoll", "sitzungsprotokoll")):
        return "protokoll"
    if any(keyword in search_blob for keyword in ("bekanntmachung", "einladung", "tagesordnung")):
        return "bekanntmachung"
    if any(keyword in search_blob for keyword in ("beschlussvorlage", "beschlussvorschlag", "beschluss")):
        return "beschlussvorlage"
    if any(keyword in search_blob for keyword in ("vorlage", "antrag")):
        return "vorlage"
    return "sonstiges"


def _maybe_migrate_database(output_path: Path, migrate_from: Path) -> None:
    if output_path.exists():
        return
    if not migrate_from.exists():
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(migrate_from.read_bytes())


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    client = SessionNetClient(base_url=args.base_url)
    refresh_existing = args.refresh_existing or args.only_refresh
    build_session_db(
        client,
        args.year,
        args.months,
        args.output,
        refresh_existing,
        args.only_refresh,
        args.migrate_from,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
