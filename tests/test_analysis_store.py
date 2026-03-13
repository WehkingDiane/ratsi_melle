from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from src.interfaces.gui.services.analysis_store import AnalysisStore, SessionFilters


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

            CREATE TABLE analysis_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                mode TEXT,
                model_name TEXT,
                prompt_version TEXT,
                parameters_json TEXT,
                status TEXT NOT NULL,
                draft_status TEXT,
                error_message TEXT
            );

            CREATE TABLE analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT
            );

            CREATE TABLE analysis_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL
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
        conn.execute(
            "INSERT INTO analysis_jobs (created_at, session_id, scope, mode, model_name, prompt_version, parameters_json, status, draft_status, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-03-01T12:00:00Z",
                "2",
                "session",
                "summary",
                "mock-model",
                "local-template-1",
                "{}",
                "done",
                "approved",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO analysis_outputs (job_id, output_format, content, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (1, "markdown", "# Analyse", "2026-03-01T12:00:00Z", "{\"hallucination_risk\":\"low\"}"),
        )
        conn.execute(
            "INSERT INTO analysis_reviews (job_id, reviewed_at, reviewer, status, notes) VALUES (?, ?, ?, ?, ?)",
            (1, "2026-03-01T13:00:00Z", "qa@example.org", "approved", "Sieht plausibel aus."),
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

    monkeypatch.setattr("src.interfaces.gui.services.analysis_store.date", FixedDate)

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

    monkeypatch.setattr("src.interfaces.gui.services.analysis_store.date", FixedDate)

    assert store.resolve_date_range("Heute", "", "") == ("2026-03-01", "2026-03-01")
    assert store.resolve_date_range("Naechste 30 Tage", "", "") == ("2026-03-01", "2026-03-31")
    assert store.resolve_date_range("Letzte 30 Tage", "", "") == ("2026-01-30", "2026-03-01")
    assert store.resolve_date_range("Dieses Jahr", "", "") == ("2026-01-01", "2026-12-31")


def test_analysis_store_loads_jobs_and_reviews(tmp_path: Path) -> None:
    db_path = tmp_path / "local_index.sqlite"
    _build_db(db_path)
    store = AnalysisStore()

    jobs = store.list_analysis_jobs(db_path, "2")
    latest_review = store.load_latest_review(db_path, 1)
    latest_output = store.load_latest_analysis_output(db_path, 1)

    assert len(jobs) == 1
    assert jobs[0]["mode"] == "summary"
    assert jobs[0]["draft_status"] == "approved"
    assert latest_review is not None
    assert latest_review["reviewer"] == "qa@example.org"
    assert latest_output is not None
    assert latest_output["content"] == "# Analyse"
