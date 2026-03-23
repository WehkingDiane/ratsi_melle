"""Analysis API that decouples GUI workflows from analysis logic."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis
from src.analysis.providers.registry import PROVIDER_NONE
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
    provider_id: str = PROVIDER_NONE
    model_name: str = ""
    prompt_version: str = "draft"
    provider_kwargs: dict = field(default_factory=dict)


class AnalysisService:
    """Service entry points used by GUI and other callers."""

    def run_journalistic_analysis(self, request: AnalysisRequest) -> AnalysisOutputRecord:
        """Build a local analysis package and optionally call a KI provider."""

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

        # Resolve effective model name (provider default when not overridden)
        effective_model = request.model_name or request.provider_id

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
                    effective_model,
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
            conn.commit()

        ki_response_text = ""
        error_message: str | None = None

        if request.provider_id != PROVIDER_NONE:
            ki_response_text, effective_model, error_message = self._call_provider(
                request=request, context=markdown
            )

        final_status = "error" if error_message else "done"
        with sqlite3.connect(db_path) as conn:
            if ki_response_text:
                conn.execute(
                    "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
                    (job_id, "ki_response", ki_response_text, created_at),
                )
            conn.execute(
                "UPDATE analysis_jobs SET status = ?, error_message = ?, model_name = ? WHERE id = ?",
                (final_status, error_message, effective_model, job_id),
            )
            conn.commit()

        record = AnalysisOutputRecord(
            job_id=job_id,
            created_at=created_at,
            session_id=str(request.session["session_id"]),
            scope=request.scope,
            top_numbers=list(request.selected_tops),
            model_name=effective_model,
            prompt_version=request.prompt_version,
            prompt_text=request.prompt,
            markdown=markdown,
            ki_response=ki_response_text,
            document_count=len(documents),
            source_db=str(db_path),
        )
        self.persist_analysis_artifacts(record)
        return record

    def _call_provider(
        self, *, request: AnalysisRequest, context: str
    ) -> tuple[str, str, str | None]:
        """Dispatch to the configured KI provider.

        Returns:
            Tuple of (response_text, effective_model_name, error_message_or_None).
        """
        from src.analysis.providers.registry import build_provider

        try:
            provider = build_provider(request.provider_id, **request.provider_kwargs)
            ki = provider.analyze(
                prompt=request.prompt,
                context=context,
                model=request.model_name or None,
            )
            return ki.response_text, ki.model_name, None
        except Exception as exc:  # noqa: BLE001
            return "", request.model_name or request.provider_id, str(exc)

    def save_document_analysis(
        self,
        *,
        db_path: Path,
        session: dict,
        document: dict,
        prompt: str,
        ki_response: str,
        model_name: str,
        extraction_quality: str,
        extraction_chars: int,
    ) -> AnalysisOutputRecord:
        """Persist a document-level KI analysis result to the DB and file artifacts."""

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        top_number = str(document.get("agenda_item") or "")
        doc_title = str(document.get("title") or "")
        doc_type = str(document.get("document_type") or "")

        markdown = (
            f"# Dokument-Analyse: {doc_title}\n\n"
            f"- TOP: {top_number}\n"
            f"- Typ: {doc_type}\n"
            f"- Extraktionsqualitaet: {extraction_quality} ({extraction_chars} Zeichen)\n"
            f"- Modell: {model_name}\n\n"
            f"## KI-Antwort\n\n{ki_response}"
        )

        with sqlite3.connect(db_path) as conn:
            self.ensure_analysis_tables(conn)
            cur = conn.execute(
                "INSERT INTO analysis_jobs "
                "(created_at, session_id, scope, top_numbers_json, model_name, prompt_version, status, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    str(session["session_id"]),
                    "document",
                    json.dumps([top_number], ensure_ascii=False),
                    model_name,
                    "draft",
                    "done",
                    None,
                ),
            )
            job_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
                (job_id, "markdown", markdown, created_at),
            )
            if ki_response:
                conn.execute(
                    "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
                    (job_id, "ki_response", ki_response, created_at),
                )
            conn.commit()

        record = AnalysisOutputRecord(
            job_id=job_id,
            created_at=created_at,
            session_id=str(session["session_id"]),
            scope="document",
            top_numbers=[top_number],
            model_name=model_name,
            prompt_version="draft",
            prompt_text=prompt,
            markdown=markdown,
            ki_response=ki_response,
            document_count=1,
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
