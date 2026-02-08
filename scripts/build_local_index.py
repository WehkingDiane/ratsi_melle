"""Build a local SQLite index for sessions and documents under data/raw."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class SessionFolder:
    session_id: str
    date: str
    committee: str
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        default=Path("data/raw"),
        type=Path,
        help="Root folder that contains raw sessions.",
    )
    parser.add_argument(
        "--output",
        default=Path("data/processed/local_index.sqlite"),
        type=Path,
        help="SQLite output path.",
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


def iter_session_folders(data_root: Path) -> Iterator[SessionFolder]:
    if not data_root.exists():
        return

    for path in data_root.rglob("*"):
        if not path.is_dir():
            continue
        if not _is_session_folder(path):
            continue
        session_info = _parse_session_folder(path)
        if session_info:
            yield session_info


def _is_session_folder(path: Path) -> bool:
    return any(
        (path / name).exists()
        for name in ("session_detail.html", "agenda_summary.json", "manifest.json")
    )


def _parse_session_folder(path: Path) -> SessionFolder | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})[-_](.+)[-_](\d+)$", path.name)
    if not match:
        return None
    date_str, committee, session_id = match.groups()
    return SessionFolder(
        session_id=session_id,
        date=date_str,
        committee=committee,
        path=path,
    )


def load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_index(data_root: Path, output_path: Path, refresh_existing: bool, only_refresh: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        _create_tables(conn)
        _populate(conn, data_root, refresh_existing, only_refresh)


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


def _populate(conn: sqlite3.Connection, data_root: Path, refresh_existing: bool, only_refresh: bool) -> None:
    session_count = 0
    agenda_count = 0
    doc_count = 0
    existing = {
        row[0]
        for row in conn.execute("SELECT session_id FROM sessions").fetchall()
        if row and row[0]
    }

    for session in iter_session_folders(data_root):
        if session.session_id in existing and not refresh_existing:
            continue
        if session.session_id not in existing and only_refresh:
            continue
        year, month = _split_date(session.date)
        manifest = load_json(session.path / "manifest.json")
        session_info = manifest.get("session") if isinstance(manifest, dict) else {}
        if not isinstance(session_info, dict):
            session_info = {}
        if session.session_id in existing and refresh_existing:
            conn.execute("DELETE FROM agenda_items WHERE session_id = ?", (session.session_id,))
            conn.execute("DELETE FROM documents WHERE session_id = ?", (session.session_id,))
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
            (session_id, date, year, month, committee, meeting_name, start_time, location, detail_url, session_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.date,
                year,
                month,
                session.committee,
                session_info.get("meeting_name"),
                None,
                session_info.get("location"),
                session_info.get("detail_url"),
                str(session.path),
            ),
        )
        session_count += 1

        agenda_summary = load_json(session.path / "agenda_summary.json")
        agenda_items = _extract_list(agenda_summary, "agenda_items")
        if agenda_items is not None:
            agenda_count += _insert_agenda_items(conn, session.session_id, agenda_items)

        documents = _extract_list(manifest, "documents")
        retrieved_at = manifest.get("retrieved_at") if isinstance(manifest, dict) else None
        if documents is not None:
            doc_count += _insert_documents(conn, session.session_id, documents, retrieved_at)

    conn.commit()
    print(
        "Indexed sessions={0} agenda_items={1} documents={2}".format(
            session_count, agenda_count, doc_count
        )
    )


def _insert_agenda_items(
    conn: sqlite3.Connection, session_id: str, agenda_summary: Iterable[dict]
) -> int:
    inserted = 0
    for item in agenda_summary:
        if not isinstance(item, dict):
            continue
        conn.execute(
            """
            INSERT INTO agenda_items
            (session_id, number, title, reporter, status, decision, documents_present)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(item.get("number") or item.get("top") or ""),
                item.get("title"),
                item.get("reporter"),
                item.get("status"),
                item.get("decision"),
                1 if item.get("documents_present") else 0,
            ),
        )
        inserted += 1
    return inserted


def _insert_documents(
    conn: sqlite3.Connection,
    session_id: str,
    manifest: Iterable[dict],
    default_retrieved_at: str | None,
) -> int:
    inserted = 0
    for doc in manifest:
        if not isinstance(doc, dict):
            continue
        document_type = _infer_document_type(
            title=doc.get("title"),
            category=doc.get("category"),
            content_type=doc.get("content_type"),
            url=doc.get("url"),
            local_path=doc.get("path"),
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
                doc.get("title"),
                doc.get("category"),
                document_type,
                doc.get("agenda_item"),
                doc.get("url"),
                doc.get("path"),
                doc.get("sha1"),
                doc.get("retrieved_at") or default_retrieved_at,
                doc.get("content_type"),
                doc.get("content_length"),
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


def _extract_list(payload: object | None, key: str) -> list[dict] | None:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get(key)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return None


def _split_date(date_str: str) -> tuple[int | None, int | None]:
    parts = date_str.split("-")
    if len(parts) != 3:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def main() -> None:
    args = parse_args()
    refresh_existing = args.refresh_existing or args.only_refresh
    build_index(args.data_root, args.output, refresh_existing, args.only_refresh)


if __name__ == "__main__":
    main()
