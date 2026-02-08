"""SQLite helpers for GUI analysis workflows."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class SessionFilters:
    date_from: str
    date_to: str
    committee: str
    search: str
    past_only: bool


class AnalysisStore:
    def list_committees(self, db_path: Path) -> list[str]:
        if not db_path.exists():
            return []
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT committee FROM sessions WHERE committee IS NOT NULL AND committee != '' ORDER BY committee"
            ).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def list_sessions(self, db_path: Path, filters: SessionFilters) -> list[dict]:
        if not db_path.exists():
            return []

        query = (
            "SELECT s.session_id, s.date, s.committee, s.meeting_name, COUNT(ai.id) AS top_count "
            "FROM sessions s LEFT JOIN agenda_items ai ON ai.session_id = s.session_id WHERE 1=1"
        )
        params: list[object] = []

        if filters.date_from:
            query += " AND s.date >= ?"
            params.append(filters.date_from)
        if filters.date_to:
            query += " AND s.date <= ?"
            params.append(filters.date_to)
        if filters.committee:
            query += " AND s.committee = ?"
            params.append(filters.committee)
        if filters.past_only:
            query += " AND s.date <= ?"
            params.append(date.today().isoformat())
        if filters.search:
            query += " AND (s.meeting_name LIKE ? OR s.committee LIKE ?)"
            like = f"%{filters.search}%"
            params.extend([like, like])

        query += " GROUP BY s.session_id, s.date, s.committee, s.meeting_name ORDER BY s.date DESC"

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def load_session_and_agenda(self, db_path: Path, session_id: str) -> tuple[dict | None, list[dict]]:
        if not db_path.exists():
            return None, []

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            session_row = conn.execute(
                "SELECT session_id, date, committee, meeting_name FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            agenda_rows = conn.execute(
                "SELECT number, title, status, decision, documents_present FROM agenda_items "
                "WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

        return (dict(session_row) if session_row else None, [dict(row) for row in agenda_rows])

    def load_documents(
        self,
        db_path: Path,
        session_id: str,
        scope: str,
        selected_tops: list[str],
    ) -> list[dict]:
        if not db_path.exists():
            return []

        where = "session_id = ?"
        params: list[object] = [session_id]
        if scope == "tops" and selected_tops:
            placeholders = ", ".join("?" for _ in selected_tops)
            where += f" AND COALESCE(agenda_item, '') IN ({placeholders})"
            params.extend(selected_tops)

        query = (
            f"SELECT agenda_item, title, document_type, local_path, url FROM documents WHERE {where} "
            "ORDER BY COALESCE(agenda_item,''), title"
        )
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def ensure_analysis_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                model_name TEXT,
                prompt_version TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES analysis_jobs(id)
            );
            """
        )
