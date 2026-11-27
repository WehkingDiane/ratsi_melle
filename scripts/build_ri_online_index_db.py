"""RI-Onlineindex bauen: Kopie des BI-Builders mit separater Anmeldung und RI-Pfaden."""

from __future__ import annotations

import argparse
from datetime import timezone
from dataclasses import replace
import logging
import sqlite3
import sys
from pathlib import Path
from time import perf_counter
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - defensive
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching import SessionNetClient  # noqa: E402  (import after sys.path manipulation)
from src.fetching.ri_session import login, BASE_URL, RI_ROOT, RiPageUnavailable  # noqa: E402
from src.config.ri_proton import RiAccessError  # noqa: E402

ONLINE_INDEX_DB = RI_ROOT / "db" / "online_session_index.sqlite"


from src.config.ri import configure_file_logging, select_months


def check_ri_path(path: Path) -> Path:
    """Restrict the online index to its dedicated RI database directory."""
    resolved = (path if path.is_absolute() else REPO_ROOT / path).resolve()
    if (not resolved.is_relative_to((RI_ROOT / "db").resolve())
            or resolved.suffix != ".sqlite"
            or resolved == (RI_ROOT / "db/local_index.sqlite").resolve()):
        raise RiAccessError("Online-Datenbank muss eine separate .sqlite-Datei unter der RI-db-Wurzel sein.")
    return resolved


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
        default=BASE_URL,
        help="Override the SessionNet base URL.",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default=None,
        help="Python logging level",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ONLINE_INDEX_DB,
        help="SQLite output path.",
    )
    parser.add_argument(
        "--migrate-from",
        type=Path,
        default=None,
        help="Optional existing RI online database to copy if output is missing.",
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
    migrate_from: Path | None = None,
) -> None:
    output_path = check_ri_path(output_path)
    migrate_from = check_ri_path(migrate_from) if migrate_from and migrate_from.exists() else None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _maybe_migrate_database(output_path, migrate_from)
    with sqlite3.connect(output_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        _create_tables(conn)
        _populate(conn, client, year, months, refresh_existing, only_refresh)


def _create_tables(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "source" in columns:
        raise RiAccessError("Die gewählte Datei ist eine Vergleichsdatenbank. Für den RI-Onlineindex eine eigene Datei verwenden.")
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
        row[0]: row[1]
        for row in conn.execute("SELECT session_id, detail_url FROM sessions").fetchall()
        if row and row[0]
    }

    months = tuple(months)
    total_references = 0
    for month_index, month in enumerate(months, start=1):
        logging.info("Build progress: fetching month %04d-%02d (%d/%d)", year, month, month_index, len(months))
        references = client.fetch_month(year=year, month=month, include_planned=True)
        total_references += len(references)
        logging.info("Found %d sessions for %04d-%02d", len(references), year, month)
        for reference_index, reference in enumerate(references, start=1):
            if reference.session_id in seen_sessions:
                continue
            refresh_session = refresh_existing or (
                reference.session_id in existing
                and not existing[reference.session_id]
                and bool(reference.detail_url)
            )
            if reference.session_id in existing and not refresh_session:
                continue
            if reference.session_id not in existing and only_refresh:
                continue
            seen_sessions.add(reference.session_id)
            logging.info("Build progress: %d/%d sessions in %04d-%02d; indexing %s", reference_index, len(references), year, month, reference.session_id)
            try:
                detail = client.fetch_session(reference) if reference.detail_url else None
            except RiPageUnavailable:
                logging.warning("Sitzung %s: Detailansicht ungeprüft; nur Kalenderdaten übernehmen.", reference.session_id)
                client.unavailable_details += 1
                if reference.session_id in existing:
                    continue  # Keep a previously indexed detail unchanged.
                reference = replace(reference, detail_url="")
                detail = None

            if reference.session_id in existing and refresh_session and detail is not None:
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

            if detail is not None:
                agenda_count += _insert_agenda_items(conn, reference.session_id, detail)
                doc_count += _insert_documents(conn, reference.session_id, detail)

    conn.commit()
    logging.info("Build complete: indexed_sessions=%d agenda_items=%d documents=%d discovered_sessions=%d", session_count, agenda_count, doc_count, total_references)
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


def _maybe_migrate_database(output_path: Path, migrate_from: Path | None) -> None:
    if output_path.exists():
        return
    if migrate_from is None or not migrate_from.exists():
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"{migrate_from.as_uri()}?mode=ro", uri=True) as source:
        if "visibility" in {row[1] for row in source.execute("PRAGMA table_info(documents)")}:
            raise RiAccessError("Lokale Dokumentdatenbank kann nicht als Onlineindex übernommen werden.")
        with sqlite3.connect(output_path) as target:
            source.backup(target)


def main() -> int:
    args = parse_args()
    if args.base_url.rstrip("/") != BASE_URL:
        print("Abbruch: Dieser RI-Builder verwendet ausschließlich den RI-Bereich.", file=sys.stderr)
        return 1
    try:
        args.output = check_ri_path(args.output)
        if args.migrate_from is not None:
            args.migrate_from = check_ri_path(args.migrate_from)
        if not 2000 <= args.year <= 2100 or any(month not in range(1, 13) for month in args.months):
            raise RiAccessError("Jahr 2000-2100 und Monate 1-12 angeben.")
        args.months = select_months(args.year, args.months)
        log_path = configure_file_logging(Path(__file__).stem, args.log_level)
        started = perf_counter()
        logging.info("Starting RI online index build: year=%d output=%s log_file=%s", args.year, args.output, log_path)
        with login() as client:
            client.unavailable_details = 0
            build_session_db(client, args.year, args.months, args.output,
                             args.refresh_existing or args.only_refresh, args.only_refresh, args.migrate_from)
        print(f"RI-Datenbank: {args.output}")
        logging.info("RI online index build runtime: %.2f seconds", perf_counter() - started)
        if client.unavailable_details:
            print(f"Hinweis: {client.unavailable_details} Detailansichten bleiben ungeprüft; Kalenderdaten sind erfasst.")
        return 2 if client.unavailable_details or client.ri_cleanup_warning or client.proton_cleanup_warning else 0
    except RiAccessError as error:
        print(f"Abbruch: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("RI-Build abgebrochen.", file=sys.stderr)
        return 1
    except Exception:
        print("Abbruch: RI-Build fehlgeschlagen; keine vertraulichen Fehlerdetails ausgegeben.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
