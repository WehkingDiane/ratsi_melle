from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from src.interfaces.shared.analysis_store import AnalysisStore, SessionFilters


def _build_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                committee TEXT,
                meeting_name TEXT
            );

            CREATE TABLE agenda_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                number TEXT,
                title TEXT
            );

            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                agenda_item TEXT,
                title TEXT,
                document_type TEXT,
                local_path TEXT,
                url TEXT,
                content_type TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO sessions (session_id, date, committee, meeting_name) VALUES (?, ?, ?, ?)",
            [
                ("1", "2026-02-20", "Rat", "Rat Februar"),
                ("2", "2026-03-01", "Rat", "Rat Maerz"),
                ("3", "2026-03-20", "Ausschuss fuer Finanzen", "Haushalt 2026"),
            ],
        )
        conn.executemany(
            "INSERT INTO agenda_items (session_id, number, title) VALUES (?, ?, ?)",
            [
                ("1", "1", "Alt"),
                ("2", "1", "Heute"),
                ("3", "1", "Neu"),
                ("3", "2", "Finanzen"),
            ],
        )
        conn.executemany(
            "INSERT INTO documents (session_id, agenda_item, title, document_type, local_path, url, content_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("1", "1", "Alt Vorlage", "vorlage", "doc1.pdf", "https://example.org/1", "application/pdf"),
                ("3", "1", "Neu Vorlage", "vorlage", "doc3.pdf", "", "application/pdf"),
                ("3", "2", "Finanzen Anlage", "anlage", "", "https://example.org/3", "application/pdf"),
            ],
        )
        conn.commit()


def test_list_sessions_supports_status_and_search_filters(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "local_index.sqlite"
    _build_db(db_path)
    store = AnalysisStore()

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 3, 1)

    monkeypatch.setattr("src.interfaces.shared.analysis_store.date", FixedDate)

    upcoming = store.list_sessions(
        db_path,
        SessionFilters(
            date_from="",
            date_to="",
            date_preset="Benutzerdefiniert",
            committee="",
            search="Haushalt",
            session_status="kommend",
        ),
    )

    assert [row["session_id"] for row in upcoming] == ["3"]
    assert upcoming[0]["session_status"] == "kommend"

    past = store.list_sessions(
        db_path,
        SessionFilters(
            date_from="",
            date_to="",
            date_preset="Benutzerdefiniert",
            committee="Rat",
            search="",
            session_status="vergangen",
        ),
    )

    assert [row["session_id"] for row in past] == ["1"]
    assert past[0]["session_status"] == "vergangen"


def test_resolve_date_range_supports_presets(monkeypatch) -> None:
    store = AnalysisStore()

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 3, 1)

    monkeypatch.setattr("src.interfaces.shared.analysis_store.date", FixedDate)

    assert store.resolve_date_range("Heute", "", "") == ("2026-03-01", "2026-03-01")
    assert store.resolve_date_range("Naechste 30 Tage", "", "") == ("2026-03-01", "2026-03-31")
    assert store.resolve_date_range("Letzte 30 Tage", "", "") == ("2026-01-30", "2026-03-01")
    assert store.resolve_date_range("Dieses Jahr", "", "") == ("2026-01-01", "2026-12-31")


def test_load_session_and_agenda_enriches_top_document_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "local_index.sqlite"
    _build_db(db_path)

    session, agenda = AnalysisStore().load_session_and_agenda(db_path, "3")

    assert session is not None
    assert session["session_id"] == "3"
    assert agenda[0]["document_count"] == 1
    assert agenda[0]["document_types"] == ["vorlage"]
    assert agenda[0]["has_local_source"] is True
    assert agenda[1]["document_types"] == ["anlage"]
