"""SQLite helpers shared by desktop and web analysis workflows."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class SessionFilters:
    date_from: str
    date_to: str
    date_preset: str
    committee: str
    search: str
    session_status: str


class AnalysisStore:
    DATE_PRESET_LABELS = (
        "Benutzerdefiniert",
        "Heute",
        "Naechste 30 Tage",
        "Letzte 30 Tage",
        "Dieses Jahr",
    )
    SESSION_STATUS_LABELS = ("alle", "vergangen", "heute", "kommend")

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

        resolved_from, resolved_to = self.resolve_date_range(
            filters.date_preset,
            filters.date_from,
            filters.date_to,
        )
        today = date.today().isoformat()
        query = (
            "SELECT s.session_id, s.date, s.committee, s.meeting_name, "
            "CASE "
            "WHEN s.date < ? THEN 'vergangen' "
            "WHEN s.date = ? THEN 'heute' "
            "ELSE 'kommend' "
            "END AS session_status, "
            "COUNT(DISTINCT ai.id) AS top_count, "
            "COUNT(DISTINCT d.id) AS document_count "
            "FROM sessions s "
            "LEFT JOIN agenda_items ai ON ai.session_id = s.session_id "
            "LEFT JOIN documents d ON d.session_id = s.session_id "
            "WHERE 1=1"
        )
        params: list[object] = [today, today]

        if resolved_from:
            query += " AND s.date >= ?"
            params.append(resolved_from)
        if resolved_to:
            query += " AND s.date <= ?"
            params.append(resolved_to)
        if filters.committee:
            query += " AND s.committee = ?"
            params.append(filters.committee)
        if filters.session_status in {"vergangen", "heute", "kommend"}:
            if filters.session_status == "vergangen":
                query += " AND s.date < ?"
                params.append(today)
            elif filters.session_status == "heute":
                query += " AND s.date = ?"
                params.append(today)
            else:
                query += " AND s.date > ?"
                params.append(today)
        if filters.search:
            query += " AND (s.meeting_name LIKE ? OR s.committee LIKE ?)"
            like = f"%{filters.search}%"
            params.extend([like, like])

        query += (
            " GROUP BY s.session_id, s.date, s.committee, s.meeting_name "
            "ORDER BY s.date DESC, s.committee ASC"
        )

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def resolve_date_range(date_preset: str, date_from: str, date_to: str) -> tuple[str, str]:
        today = date.today()
        preset = (date_preset or "").strip()
        if preset == "Heute":
            iso = today.isoformat()
            return iso, iso
        if preset == "Naechste 30 Tage":
            return today.isoformat(), (today + timedelta(days=30)).isoformat()
        if preset == "Letzte 30 Tage":
            return (today - timedelta(days=30)).isoformat(), today.isoformat()
        if preset == "Dieses Jahr":
            return f"{today.year}-01-01", f"{today.year}-12-31"
        return date_from, date_to

    def load_session_and_agenda(self, db_path: Path, session_id: str) -> tuple[dict | None, list[dict]]:
        if not db_path.exists():
            return None, []

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            agenda_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(agenda_items)").fetchall()
            }
            has_status = "status" in agenda_columns
            has_decision = "decision" in agenda_columns
            has_documents_present = "documents_present" in agenda_columns
            session_row = conn.execute(
                "SELECT session_id, date, committee, meeting_name FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            agenda_rows = conn.execute(
                """
                SELECT
                    ai.number,
                    ai.title,
                    {status_sql} AS status,
                    {decision_sql} AS decision,
                    {documents_present_sql} AS documents_present,
                    COUNT(d.id) AS document_count,
                    GROUP_CONCAT(DISTINCT NULLIF(d.document_type, '')) AS document_types,
                    MAX(
                        CASE
                            WHEN d.local_path IS NOT NULL AND d.local_path != '' THEN 1
                            ELSE 0
                        END
                    ) AS has_local_source
                FROM agenda_items ai
                LEFT JOIN documents d
                    ON d.session_id = ai.session_id AND COALESCE(d.agenda_item, '') = COALESCE(ai.number, '')
                WHERE ai.session_id = ?
                GROUP BY ai.id, ai.number, ai.title
                ORDER BY ai.id
                """.format(
                    status_sql="ai.status" if has_status else "''",
                    decision_sql="ai.decision" if has_decision else "''",
                    documents_present_sql="ai.documents_present" if has_documents_present else "''",
                ),
                (session_id,),
            ).fetchall()

        agenda = []
        for row in agenda_rows:
            item = dict(row)
            item["document_count"] = int(item.get("document_count") or 0)
            doc_types = str(item.get("document_types") or "")
            item["document_types"] = [part for part in doc_types.split(",") if part]
            item["has_local_source"] = bool(item.get("has_local_source"))
            agenda.append(item)

        return (dict(session_row) if session_row else None, agenda)

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

        where_sql = where.replace("session_id", "d.session_id").replace("agenda_item", "d.agenda_item")
        query = (
            f"SELECT d.agenda_item, d.title, d.document_type, d.local_path, d.url, d.content_type, s.session_path "
            f"FROM documents d JOIN sessions s ON s.session_id = d.session_id WHERE {where_sql} "
            "ORDER BY COALESCE(d.agenda_item,''), d.title"
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
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
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
        columns = {row[1] for row in conn.execute("PRAGMA table_info(analysis_jobs)").fetchall()}
        if "purpose" not in columns:
            conn.execute(
                "ALTER TABLE analysis_jobs ADD COLUMN purpose TEXT NOT NULL DEFAULT 'content_analysis'"
            )
