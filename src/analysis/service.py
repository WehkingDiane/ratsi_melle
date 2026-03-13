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
        if request.mode == "change_monitor":
            previous_documents = self._load_previous_documents(
                db_path=db_path,
                session=request.session,
                current_documents=documents,
            )
            previous_documents = enrich_documents_for_analysis(previous_documents)
            documents = self._annotate_change_history(documents, previous_documents)
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
            "SELECT d.session_id, s.date, s.committee, s.meeting_name, d.agenda_item, ai.title AS agenda_title, "
            "d.title, d.document_type, d.local_path, d.url, d.content_type, d.sha1, d.retrieved_at, s.session_path "
            "FROM documents d JOIN sessions s ON s.session_id = d.session_id "
            "LEFT JOIN agenda_items ai ON ai.session_id = d.session_id AND ai.number = d.agenda_item "
            f"WHERE {where} ORDER BY COALESCE(d.agenda_item,''), d.title"
        )
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def _load_previous_documents(
        self,
        *,
        db_path: Path,
        session: dict,
        current_documents: list[dict],
    ) -> list[dict]:
        if not db_path.exists() or not current_documents:
            return []

        committee = str(session.get("committee") or "").strip()
        session_date = str(session.get("date") or "").strip()
        if not committee or not session_date:
            return []

        urls = sorted({str(doc.get("url") or "").strip() for doc in current_documents if str(doc.get("url") or "").strip()})
        title_type_pairs = sorted(
            {
                (str(doc.get("title") or "").strip(), str(doc.get("document_type") or "").strip())
                for doc in current_documents
                if str(doc.get("title") or "").strip() and str(doc.get("document_type") or "").strip()
            }
        )
        if not urls and not title_type_pairs:
            return []

        where_parts = ["s.committee = ?", "s.date < ?"]
        params: list[object] = [committee, session_date]

        match_parts: list[str] = []
        if urls:
            placeholders = ", ".join("?" for _ in urls)
            match_parts.append(f"d.url IN ({placeholders})")
            params.extend(urls)
        if title_type_pairs:
            pair_parts: list[str] = []
            for title, document_type in title_type_pairs:
                pair_parts.append("(d.title = ? AND d.document_type = ?)")
                params.extend([title, document_type])
            match_parts.append("(" + " OR ".join(pair_parts) + ")")

        where_parts.append("(" + " OR ".join(match_parts) + ")")
        query = (
            "SELECT d.session_id, s.date, s.committee, s.meeting_name, d.agenda_item, ai.title AS agenda_title, "
            "d.title, d.document_type, d.local_path, d.url, d.content_type, d.sha1, d.retrieved_at, s.session_path "
            "FROM documents d JOIN sessions s ON s.session_id = d.session_id "
            "LEFT JOIN agenda_items ai ON ai.session_id = d.session_id AND ai.number = d.agenda_item "
            f"WHERE {' AND '.join(where_parts)} "
            "ORDER BY s.date DESC, COALESCE(d.retrieved_at, '') DESC, d.id DESC"
        )
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def _annotate_change_history(self, documents: list[dict], previous_documents: list[dict]) -> list[dict]:
        indexed_previous: dict[tuple[str, str], list[dict]] = {}
        for previous in previous_documents:
            for key in self._comparison_keys(previous):
                indexed_previous.setdefault(key, []).append(previous)

        annotated: list[dict] = []
        for document in documents:
            entry = dict(document)
            previous = self._latest_previous_match(entry, indexed_previous)
            if previous is not None:
                entry["historical_reference"] = {
                    "session_id": previous.get("session_id"),
                    "date": previous.get("date"),
                    "meeting_name": previous.get("meeting_name"),
                    "title": previous.get("title"),
                    "document_type": previous.get("document_type"),
                    "url": previous.get("url"),
                    "sha1": previous.get("sha1"),
                }
                entry["historical_change_signals"] = self._compare_document_versions(previous, entry)
            else:
                entry["historical_reference"] = None
                entry["historical_change_signals"] = []
            annotated.append(entry)
        return annotated

    @staticmethod
    def _comparison_keys(document: dict) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        url = str(document.get("url") or "").strip()
        if url:
            keys.append(("url", url))
        title = str(document.get("title") or "").strip()
        document_type = str(document.get("document_type") or "").strip()
        if title and document_type:
            keys.append(("title_type", f"{title}|{document_type}"))
        return keys

    def _latest_previous_match(
        self,
        document: dict,
        indexed_previous: dict[tuple[str, str], list[dict]],
    ) -> dict | None:
        candidates: list[dict] = []
        for key in self._comparison_keys(document):
            candidates.extend(indexed_previous.get(key, []))
        if not candidates:
            return None
        unique_candidates = {
            (str(candidate.get("session_id") or ""), str(candidate.get("title") or ""), str(candidate.get("url") or "")): candidate
            for candidate in candidates
        }
        ordered = sorted(
            unique_candidates.values(),
            key=lambda item: (str(item.get("date") or ""), str(item.get("retrieved_at") or "")),
            reverse=True,
        )
        return ordered[0] if ordered else None

    @staticmethod
    def _compare_document_versions(previous: dict, current: dict) -> list[str]:
        signals: list[str] = []
        if str(previous.get("sha1") or "") and str(current.get("sha1") or "") and previous.get("sha1") != current.get("sha1"):
            signals.append("datei_hash_geaendert")
        if str(previous.get("title") or "") != str(current.get("title") or ""):
            signals.append("titel_geaendert")
        previous_fields = previous.get("structured_fields") if isinstance(previous.get("structured_fields"), dict) else {}
        current_fields = current.get("structured_fields") if isinstance(current.get("structured_fields"), dict) else {}
        for field_name, signal in (
            ("beschlusstext", "beschlusstext_geaendert"),
            ("entscheidung", "entscheidung_geaendert"),
            ("finanzbezug", "finanzbezug_geaendert"),
            ("zustaendigkeit", "zustaendigkeit_geaendert"),
        ):
            if str(previous_fields.get(field_name) or "").strip() != str(current_fields.get(field_name) or "").strip():
                if str(previous_fields.get(field_name) or "").strip() or str(current_fields.get(field_name) or "").strip():
                    signals.append(signal)
        return signals

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
