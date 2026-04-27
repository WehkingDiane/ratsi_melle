"""Download one SessionNet session selected from the online session index."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import logging
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - defensive
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching import SessionNetClient, SessionReference  # noqa: E402
from src.paths import ONLINE_INDEX_DB  # noqa: E402


REQUIRED_INDEX_TABLES = frozenset({"sessions"})


@dataclass(frozen=True)
class IndexedSession:
    """Session metadata loaded from the online SQLite index."""

    session_id: str
    date: date
    committee: str
    meeting_name: str
    start_time: str | None
    detail_url: str
    location: str | None

    def to_reference(self) -> SessionReference:
        """Convert index metadata into a SessionNet fetch reference."""

        return SessionReference(
            committee=self.committee,
            meeting_name=self.meeting_name,
            session_id=self.session_id,
            date=self.date,
            start_time=self.start_time,
            detail_url=self.detail_url,
            location=self.location,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-id",
        help="Session ID from data/db/online_session_index.sqlite, for example 7128.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List sessions from the index instead of downloading one.",
    )
    parser.add_argument(
        "--committee",
        help="Optional case-insensitive committee filter for --list.",
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        help="Optional lower date bound for --list in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        help="Optional upper date bound for --list in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of sessions to show with --list. Defaults to 30.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=ONLINE_INDEX_DB,
        help="SQLite index path. Defaults to data/db/online_session_index.sqlite.",
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
        help="Python logging level.",
    )
    return parser.parse_args()


def load_session_from_index(db_path: Path, session_id: str) -> IndexedSession:
    """Load one session row from the online index."""

    validate_index_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT session_id, date, committee, meeting_name, start_time, location, detail_url
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        raise SystemExit(f"Session {session_id!r} not found in {db_path}")
    if not row["detail_url"]:
        raise SystemExit(f"Session {session_id!r} has no detail_url in {db_path}")

    return IndexedSession(
        session_id=row["session_id"],
        date=date.fromisoformat(row["date"]),
        committee=row["committee"] or row["meeting_name"] or "Sitzung",
        meeting_name=row["meeting_name"] or row["committee"] or "Sitzung",
        start_time=row["start_time"],
        detail_url=row["detail_url"],
        location=row["location"],
    )


def validate_index_db(db_path: Path) -> None:
    """Fail fast if the SQLite index is missing or not initialized."""

    if not db_path.exists():
        raise SystemExit(f"Index database not found: {db_path}")
    if not db_path.is_file():
        raise SystemExit(f"Index database path is not a file: {db_path}")

    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }
    except sqlite3.Error as exc:
        raise SystemExit(f"Index database is not a readable SQLite database: {db_path}") from exc

    missing_tables = REQUIRED_INDEX_TABLES - tables
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise SystemExit(f"Index database is not initialized: missing table(s): {missing} in {db_path}")


def list_sessions(
    db_path: Path,
    *,
    committee: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 30,
) -> list[IndexedSession]:
    """Return sessions from the index for CLI selection."""

    validate_index_db(db_path)
    conditions: list[str] = []
    params: list[object] = []
    if committee:
        conditions.append("LOWER(committee) LIKE ?")
        params.append(f"%{committee.lower()}%")
    if from_date:
        conditions.append("date >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("date <= ?")
        params.append(to_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(max(limit, 1))

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT session_id, date, committee, meeting_name, start_time, location, detail_url
            FROM sessions
            {where_clause}
            ORDER BY date DESC, committee COLLATE NOCASE
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [
        IndexedSession(
            session_id=row["session_id"],
            date=date.fromisoformat(row["date"]),
            committee=row["committee"] or row["meeting_name"] or "Sitzung",
            meeting_name=row["meeting_name"] or row["committee"] or "Sitzung",
            start_time=row["start_time"],
            detail_url=row["detail_url"],
            location=row["location"],
        )
        for row in rows
    ]


def print_session_list(sessions: list[IndexedSession]) -> None:
    for session in sessions:
        start_time = f" {session.start_time}" if session.start_time else ""
        print(f"{session.session_id}\t{session.date.isoformat()}{start_time}\t{session.committee}")


def fetch_single_session(client: SessionNetClient, indexed_session: IndexedSession) -> Path:
    """Fetch detail HTML and documents for one indexed session."""

    reference = indexed_session.to_reference()
    detail = client.fetch_session(reference)
    client.download_documents(detail)
    return client._build_session_directory(reference)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if args.list:
        sessions = list_sessions(
            args.db,
            committee=args.committee,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
        )
        print_session_list(sessions)
        return

    if not args.session_id:
        raise SystemExit("Either --session-id or --list is required.")

    indexed_session = load_session_from_index(args.db, args.session_id)
    client = SessionNetClient(base_url=args.base_url)
    session_dir = fetch_single_session(client, indexed_session)
    print(f"Downloaded session {indexed_session.session_id} to {session_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
