from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from scripts.fetch_session_from_index import list_sessions, load_session_from_index, validate_index_db


def _write_index(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
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
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO sessions
            (session_id, date, year, month, committee, meeting_name, start_time, location, detail_url, session_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "7128",
                    "2026-04-23",
                    2026,
                    4,
                    "Ausschuss fuer Planen und Stadtentwicklung",
                    "Ausschuss fuer Planen und Stadtentwicklung",
                    "18:00 Uhr",
                    "Forum Melle",
                    "https://session.melle.info/bi/si0057.asp?__ksinr=7128",
                    None,
                ),
                (
                    "8186",
                    "2026-04-22",
                    2026,
                    4,
                    "Ortsrat Melle-Mitte",
                    "Ortsrat Melle-Mitte",
                    "19:00 Uhr",
                    "Ratssaal",
                    "https://session.melle.info/bi/si0057.asp?__ksinr=8186",
                    None,
                ),
            ],
        )


def test_load_session_from_index_builds_fetch_reference(tmp_path: Path) -> None:
    db_path = tmp_path / "online_session_index.sqlite"
    _write_index(db_path)

    indexed_session = load_session_from_index(db_path, "7128")
    reference = indexed_session.to_reference()

    assert indexed_session.date == date(2026, 4, 23)
    assert reference.session_id == "7128"
    assert reference.committee == "Ausschuss fuer Planen und Stadtentwicklung"
    assert reference.detail_url == "https://session.melle.info/bi/si0057.asp?__ksinr=7128"
    assert reference.location == "Forum Melle"


def test_list_sessions_filters_by_committee_and_date(tmp_path: Path) -> None:
    db_path = tmp_path / "online_session_index.sqlite"
    _write_index(db_path)

    sessions = list_sessions(db_path, committee="ortsrat", from_date="2026-04-01", to_date="2026-04-30")

    assert [session.session_id for session in sessions] == ["8186"]


def test_validate_index_db_fails_without_creating_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite"

    with pytest.raises(SystemExit, match="Index database not found"):
        validate_index_db(db_path)

    assert not db_path.exists()


def test_load_session_from_index_fails_for_uninitialized_database(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite"
    sqlite3.connect(db_path).close()

    with pytest.raises(SystemExit, match="missing table\\(s\\): sessions"):
        load_session_from_index(db_path, "7128")


def test_list_sessions_fails_for_uninitialized_database(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite"
    sqlite3.connect(db_path).close()

    with pytest.raises(SystemExit, match="missing table\\(s\\): sessions"):
        list_sessions(db_path)
