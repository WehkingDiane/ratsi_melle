"""Analysis API that decouples GUI workflows from analysis logic."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis
from src.analysis.schemas import AnalysisOutputRecord
from src.paths import ANALYSIS_PROMPTS_DIR, ANALYSIS_SUMMARIES_DIR, DEFAULT_ANALYSIS_MARKDOWN


@dataclass(frozen=True)
class AnalysisRequest:
    """Input contract for the KI-oriented analysis preparation workflow."""

    db_path: Path
    session: dict
    scope: str
    selected_tops: list[str]
    prompt: str
    model_name: str = "pending-provider"
    prompt_version: str = "draft"


class AnalysisService:
    """Service entry points used by GUI and other callers."""

    def run_journalistic_analysis(self, request: AnalysisRequest) -> AnalysisOutputRecord:
        """Build a local analysis package summary and persist versioned artifacts."""

        db_path = request.db_path
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        documents = self._load_documents(
            db_path=db_path,
            session_id=str(request.session["session_id"]),
            scope=request.scope,
            selected_tops=request.selected_tops,
        )
        documents = enrich_documents_for_analysis(documents)
        markdown = build_analysis_markdown(
            session=request.session,
            scope=request.scope,
            selected_tops=request.selected_tops,
            documents=documents,
            prompt=request.prompt,
        )

        with sqlite3.connect(db_path) as conn:
            self.ensure_analysis_tables(conn)
            cur = conn.execute(
                "INSERT INTO analysis_jobs (created_at, session_id, scope, top_numbers_json, model_name, prompt_version, status, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    request.session["session_id"],
                    request.scope,
                    json.dumps(request.selected_tops, ensure_ascii=False),
                    request.model_name,
                    request.prompt_version,
                    "running",
                    None,
                ),
            )
            job_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
                (job_id, "markdown", markdown, created_at),
            )
            conn.execute("UPDATE analysis_jobs SET status = ? WHERE id = ?", ("done", job_id))
            conn.commit()

        record = AnalysisOutputRecord(
            job_id=job_id,
            created_at=created_at,
            session_id=str(request.session["session_id"]),
            scope=request.scope,
            top_numbers=list(request.selected_tops),
            model_name=request.model_name,
            prompt_version=request.prompt_version,
            prompt_text=request.prompt,
            markdown=markdown,
            document_count=len(documents),
            source_db=str(db_path),
        )
        self.persist_analysis_artifacts(record)
        return record

    def persist_analysis_artifacts(self, record: AnalysisOutputRecord) -> None:
        """Persist markdown, prompt and versioned JSON output to analysis output dirs."""

        ANALYSIS_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

        job_stem = f"job_{record.job_id}"
        (ANALYSIS_SUMMARIES_DIR / f"{job_stem}.md").write_text(record.markdown + "\n", encoding="utf-8")
        (ANALYSIS_SUMMARIES_DIR / f"{job_stem}.json").write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (ANALYSIS_PROMPTS_DIR / f"{job_stem}.txt").write_text(record.prompt_text + "\n", encoding="utf-8")
        DEFAULT_ANALYSIS_MARKDOWN.write_text(record.markdown + "\n", encoding="utf-8")

    def export_markdown(self, markdown: str, target: Path = DEFAULT_ANALYSIS_MARKDOWN) -> Path:
        """Export markdown to the standard analysis output location."""

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown.rstrip() + "\n", encoding="utf-8")
        return target

    def ensure_analysis_tables(self, conn: sqlite3.Connection) -> None:
        """Create analysis job/output metadata tables in the given database."""

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

    def _load_documents(
        self,
        *,
        db_path: Path,
        session_id: str,
        scope: str,
        selected_tops: list[str],
    ) -> list[dict]:
        if not db_path.exists():
            return []

        where = "d.session_id = ?"
        params: list[object] = [session_id]
        if scope == "tops" and selected_tops:
            placeholders = ", ".join("?" for _ in selected_tops)
            where += f" AND COALESCE(d.agenda_item, '') IN ({placeholders})"
            params.extend(selected_tops)

        query = (
            "SELECT d.agenda_item, d.title, d.document_type, d.local_path, d.url, d.content_type, s.session_path "
            "FROM documents d JOIN sessions s ON s.session_id = d.session_id "
            f"WHERE {where} ORDER BY COALESCE(d.agenda_item,''), d.title"
        )
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]
