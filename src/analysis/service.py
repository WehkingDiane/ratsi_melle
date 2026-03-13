"""Analysis API that decouples GUI workflows from analysis logic."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis
from src.analysis.safety import (
    derive_bias_metrics,
    derive_plausibility_flags,
    derive_uncertainty_flags,
    estimate_hallucination_risk,
    hash_document,
    mask_document_for_analysis,
)
from src.analysis.schemas import AnalysisOutputRecord
from src.paths import ANALYSIS_PROMPTS_DIR, ANALYSIS_SUMMARIES_DIR, DEFAULT_ANALYSIS_MARKDOWN

SUPPORTED_ANALYSIS_MODES = {
    "summary",
    "decision_brief",
    "financial_impact",
    "citizen_explainer",
    "journalistic_brief",
    "topic_classifier",
    "change_monitor",
}


@dataclass(frozen=True)
class AnalysisRequest:
    """Input contract for the journalistic analysis workflow."""

    db_path: Path
    session: dict
    scope: str
    selected_tops: list[str]
    prompt: str
    mode: str = "journalistic_brief"
    model_name: str = "mock-journalism-v1"
    prompt_version: str = "local-template-1"
    parameters: dict[str, object] | None = None


class AnalysisService:
    """Service entry points used by GUI and other callers."""

    def run_analysis(self, request: AnalysisRequest) -> AnalysisOutputRecord:
        """Run an analysis in the requested mode and persist typed artifacts."""

        self._validate_mode(request.mode)
        db_path = request.db_path
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        documents = self._load_documents(
            db_path=db_path,
            session_id=str(request.session["session_id"]),
            scope=request.scope,
            selected_tops=request.selected_tops,
        )
        documents = enrich_documents_for_analysis(documents)
        sanitized_documents: list[dict] = []
        sensitive_data_masked = False
        for document in documents:
            masked_document, changed = mask_document_for_analysis(document)
            sanitized_documents.append(masked_document)
            sensitive_data_masked = sensitive_data_masked or changed

        parameters = dict(request.parameters or {})
        uncertainty_flags = derive_uncertainty_flags(sanitized_documents)
        plausibility_flags = derive_plausibility_flags(sanitized_documents, request.mode)
        bias_metrics = derive_bias_metrics(sanitized_documents)
        document_hashes = [hash_document(document) for document in sanitized_documents]
        hallucination_risk = estimate_hallucination_risk(
            sanitized_documents,
            uncertainty_flags,
            plausibility_flags,
        )
        source_refs = self._build_source_references(sanitized_documents)

        markdown = build_analysis_markdown(
            session=request.session,
            mode=request.mode,
            scope=request.scope,
            selected_tops=request.selected_tops,
            documents=sanitized_documents,
            prompt=request.prompt,
            uncertainty_flags=uncertainty_flags,
            plausibility_flags=plausibility_flags,
            bias_metrics=bias_metrics,
        )

        with sqlite3.connect(db_path) as conn:
            self.ensure_analysis_tables(conn)
            cur = conn.execute(
                "INSERT INTO analysis_jobs (created_at, session_id, scope, top_numbers_json, mode, model_name, prompt_version, "
                "parameters_json, status, draft_status, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    request.session["session_id"],
                    request.scope,
                    json.dumps(request.selected_tops, ensure_ascii=False),
                    request.mode,
                    request.model_name,
                    request.prompt_version,
                    json.dumps(parameters, ensure_ascii=False),
                    "running",
                    "draft",
                    None,
                ),
            )
            job_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO analysis_outputs (job_id, output_format, content, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (
                    job_id,
                    "markdown",
                    markdown,
                    created_at,
                    json.dumps(
                        {
                            "mode": request.mode,
                            "uncertainty_flags": uncertainty_flags,
                            "plausibility_flags": plausibility_flags,
                            "bias_metrics": bias_metrics,
                            "hallucination_risk": hallucination_risk,
                            "document_hashes": document_hashes,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.execute("UPDATE analysis_jobs SET status = ? WHERE id = ?", ("done", job_id))
            conn.commit()

        audit_trail = {
            "run_at": created_at,
            "mode": request.mode,
            "model_name": request.model_name,
            "prompt_version": request.prompt_version,
            "parameters": parameters,
            "source_db": str(db_path),
            "document_hashes": document_hashes,
            "plausibility_flags": plausibility_flags,
            "bias_metrics": bias_metrics,
        }
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
            document_count=len(sanitized_documents),
            source_db=str(db_path),
            mode=request.mode,
            parameters=parameters,
            document_hashes=document_hashes,
            uncertainty_flags=uncertainty_flags,
            plausibility_flags=plausibility_flags,
            bias_metrics=bias_metrics,
            hallucination_risk=hallucination_risk,
            sources=source_refs,
            sensitive_data_masked=sensitive_data_masked,
            draft_status="draft",
            audit_trail=audit_trail,
        )
        self.persist_analysis_artifacts(record)
        return record

    def run_journalistic_analysis(self, request: AnalysisRequest) -> AnalysisOutputRecord:
        """Backward-compatible wrapper for existing GUI calls."""

        if request.mode == "journalistic_brief":
            return self.run_analysis(request)
        adapted = AnalysisRequest(
            db_path=request.db_path,
            session=request.session,
            scope=request.scope,
            selected_tops=request.selected_tops,
            prompt=request.prompt,
            mode="journalistic_brief",
            model_name=request.model_name,
            prompt_version=request.prompt_version,
            parameters=request.parameters,
        )
        return self.run_analysis(adapted)

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
                mode TEXT,
                model_name TEXT,
                prompt_version TEXT,
                parameters_json TEXT,
                status TEXT NOT NULL,
                draft_status TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(job_id) REFERENCES analysis_jobs(id)
            );

            CREATE TABLE IF NOT EXISTS analysis_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES analysis_jobs(id)
            );
            """
        )
        self._ensure_column(conn, "analysis_jobs", "mode", "TEXT")
        self._ensure_column(conn, "analysis_jobs", "parameters_json", "TEXT")
        self._ensure_column(conn, "analysis_jobs", "draft_status", "TEXT")
        self._ensure_column(conn, "analysis_outputs", "metadata_json", "TEXT")

    def review_job(self, db_path: Path, *, job_id: int, reviewer: str, status: str, notes: str) -> None:
        """Store human review metadata and update draft status for one analysis job."""

        reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with sqlite3.connect(db_path) as conn:
            self.ensure_analysis_tables(conn)
            conn.execute(
                "INSERT INTO analysis_reviews (job_id, reviewed_at, reviewer, status, notes) VALUES (?, ?, ?, ?, ?)",
                (job_id, reviewed_at, reviewer, status, notes),
            )
            conn.execute("UPDATE analysis_jobs SET draft_status = ? WHERE id = ?", (status, job_id))
            conn.commit()

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

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in SUPPORTED_ANALYSIS_MODES:
            supported = ", ".join(sorted(SUPPORTED_ANALYSIS_MODES))
            raise ValueError(f"Unsupported analysis mode '{mode}'. Supported: {supported}")

    @staticmethod
    def _build_source_references(documents: list[dict]) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        for document in documents:
            title = str(document.get("title") or "(ohne Titel)")
            url = str(document.get("url") or "")
            local_path = str(document.get("resolved_local_path") or document.get("local_path") or "")
            sources.append({"title": title, "url": url, "local_path": local_path})
        return sources

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
