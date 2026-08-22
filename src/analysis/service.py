"""Analysis API that decouples GUI workflows from analysis logic."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import re
import unicodedata

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis
from src.analysis.providers._pdf_utils import extract_pdf_text
from src.analysis.providers.registry import PROVIDER_NONE
from src.analysis.schemas import (
    ANALYSIS_OUTPUT_SCHEMA_VERSION_V2,
    DEFAULT_ANALYSIS_PURPOSE,
    AnalysisOutputRecord,
    PublicationDraftOutput,
    RawAnalysisDocument,
    RawAnalysisOutput,
    StructuredAnalysisOutput,
    Topic,
)
from src.analysis.workflow_db import (
    AnalysisArtifactRecord,
    AnalysisJobRecord,
    PublicationJobRecord,
    add_analysis_output,
    create_analysis_job,
    create_publication_job,
    update_analysis_job,
)
from src.fetching.storage_layout import resolve_local_file_path
from src.paths import ANALYSIS_OUTPUTS_DIR, ANALYSIS_PROMPTS_DIR, DEFAULT_ANALYSIS_MARKDOWN, PROMPT_SNAPSHOTS_DIR


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
    prompt_template_id: str = ""
    prompt_template_revision: int | None = None
    prompt_template_label: str = ""
    purpose: str = DEFAULT_ANALYSIS_PURPOSE
    provider_kwargs: dict = field(default_factory=dict)
    pdf_paths: list[Path] = field(default_factory=list)


class AnalysisService:
    """Service entry points used by GUI and other callers."""

    def run_journalistic_analysis(self, request: AnalysisRequest) -> AnalysisOutputRecord:
        """Build a local analysis package and optionally call a KI provider."""

        db_path = request.db_path
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        session_id = str(request.session["session_id"])
        documents = self._load_documents(
            db_path=db_path,
            session_id=session_id,
            scope=request.scope,
            selected_tops=request.selected_tops,
        )
        documents = _prioritize_documents(enrich_documents_for_analysis(documents))
        pdf_paths = request.pdf_paths or _pdf_paths_from_documents(documents)
        session_path = self._get_session_path(db_path, session_id)
        markdown = build_analysis_markdown(
            session=request.session,
            scope=request.scope,
            selected_tops=request.selected_tops,
            documents=documents,
            prompt=request.prompt,
        )
        markdown = _with_ki_analysis(markdown, "")

        # Resolve effective model name (provider default when not overridden)
        effective_model = request.model_name or request.provider_id

        with sqlite3.connect(db_path) as conn:
            self.ensure_analysis_tables(conn)
            cur = conn.execute(
                "INSERT INTO analysis_jobs (created_at, session_id, scope, top_numbers_json, purpose, model_name, provider_id, input_tokens, output_tokens, response_status, prompt_version, prompt_template_id, prompt_template_revision, prompt_template_label, rendered_prompt_snapshot_path, status, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    request.session["session_id"],
                    request.scope,
                    json.dumps(request.selected_tops, ensure_ascii=False),
                    request.purpose or DEFAULT_ANALYSIS_PURPOSE,
                    effective_model,
                    request.provider_id,
                    0,
                    0,
                    "not_requested",
                    request.prompt_version,
                    request.prompt_template_id or None,
                    request.prompt_template_revision,
                    request.prompt_template_label or None,
                    None,
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
        input_tokens = 0
        output_tokens = 0
        response_status = "not_requested"

        if request.provider_id != PROVIDER_NONE:
            (ki_response_text, effective_model, input_tokens, output_tokens, error_message) = self._call_provider(
                request=request, context=markdown, pdf_paths=pdf_paths
            )
            if error_message:
                response_status = "error"
            elif not ki_response_text.strip():
                error_message = "Der KI-Provider hat keine Antwort geliefert."
                response_status = "empty"
            elif not _parse_ki_json_response(ki_response_text):
                error_message = "Die KI-Antwort ist kein valides JSON-Objekt."
                response_status = "invalid_json"
            else:
                response_status = "valid_json"

        final_status = "prepared" if request.provider_id == PROVIDER_NONE else ("error" if error_message else "done")
        with sqlite3.connect(db_path) as conn:
            if ki_response_text:
                conn.execute(
                    "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
                    (job_id, "ki_response", ki_response_text, created_at),
                )
            conn.execute(
                "UPDATE analysis_jobs SET status = ?, error_message = ?, model_name = ?, provider_id = ?, input_tokens = ?, output_tokens = ?, response_status = ? WHERE id = ?",
                (final_status, error_message, effective_model, request.provider_id, input_tokens, output_tokens, response_status, job_id),
            )
            conn.commit()

        markdown = _with_ki_analysis(markdown, ki_response_text)
        record = AnalysisOutputRecord(
            job_id=job_id,
            created_at=created_at,
            session_id=session_id,
            scope=request.scope,
            top_numbers=list(request.selected_tops) if request.scope != "session" else [],
            purpose=request.purpose or DEFAULT_ANALYSIS_PURPOSE,
            model_name=effective_model,
            provider_id=request.provider_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_status=response_status,
            prompt_version=request.prompt_version,
            prompt_template_id=request.prompt_template_id,
            prompt_template_revision=request.prompt_template_revision,
            prompt_template_label=request.prompt_template_label,
            prompt_text=request.prompt,
            markdown=markdown,
            ki_response=ki_response_text,
            document_count=len(documents),
            source_db=str(db_path),
            session_path=session_path,
            session_date=str(request.session.get("date", "")),
            status=final_status,
            error_message=error_message or "",
        )
        self.persist_analysis_artifacts(record, documents=documents, session=request.session)
        return record

    def execute_prepared_analysis(
        self,
        request: AnalysisRequest,
        *,
        workflow_job_id: int,
        source_job_id: int,
        markdown: str,
        artifact_paths: dict[str, Path],
        workflow_db_path: Path | None = None,
    ) -> AnalysisOutputRecord:
        """Run a provider for an existing prepared job without creating a new job."""

        documents = self._load_documents(
            db_path=request.db_path,
            session_id=str(request.session["session_id"]),
            scope=request.scope,
            selected_tops=request.selected_tops,
        )
        documents = _prioritize_documents(enrich_documents_for_analysis(documents))
        pdf_paths = request.pdf_paths or _pdf_paths_from_documents(documents)
        base_markdown = _with_ki_analysis(markdown, "")
        update_analysis_job(
            workflow_job_id,
            model_name=request.model_name or request.provider_id,
            provider_id=request.provider_id,
            input_tokens=0,
            output_tokens=0,
            response_status="pending",
            status="running",
            db_path=workflow_db_path,
        )
        response, model_name, input_tokens, output_tokens, error_message = self._call_provider(
            request=request,
            context=base_markdown,
            pdf_paths=pdf_paths,
        )
        if error_message:
            response_status = "error"
        elif not response.strip():
            error_message = "Der KI-Provider hat keine Antwort geliefert."
            response_status = "empty"
        elif not _parse_ki_json_response(response):
            error_message = "Die KI-Antwort ist kein valides JSON-Objekt."
            response_status = "invalid_json"
        else:
            response_status = "valid_json"
        status = "error" if error_message else "done"
        final_markdown = _with_ki_analysis(base_markdown, response)
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record = AnalysisOutputRecord(
            job_id=source_job_id,
            created_at=created_at,
            session_id=str(request.session["session_id"]),
            scope=request.scope,
            top_numbers=list(request.selected_tops),
            purpose=request.purpose or DEFAULT_ANALYSIS_PURPOSE,
            model_name=model_name,
            provider_id=request.provider_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_status=response_status,
            prompt_version=request.prompt_version,
            prompt_template_id=request.prompt_template_id,
            prompt_template_revision=request.prompt_template_revision,
            prompt_template_label=request.prompt_template_label,
            prompt_text=request.prompt,
            markdown=final_markdown,
            ki_response=response,
            document_count=len(documents),
            source_db=str(request.db_path),
            session_path=self._get_session_path(request.db_path, str(request.session["session_id"])),
            session_date=str(request.session.get("date") or ""),
            status=status,
            error_message=error_message or "",
        )
        self._update_source_job(record)
        update_analysis_job(
            workflow_job_id,
            model_name=model_name,
            provider_id=request.provider_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_status=response_status,
            status=status,
            error_message=error_message or "",
            db_path=workflow_db_path,
        )
        self._overwrite_existing_artifacts(record, documents, request.session, artifact_paths)
        self._persist_deferred_publication(
            record,
            request.session,
            artifact_paths,
            workflow_job_id,
            workflow_db_path,
        )
        return record

    def _update_source_job(self, record: AnalysisOutputRecord) -> None:
        """Keep legacy source tables synchronized when they still exist."""

        try:
            with sqlite3.connect(record.source_db) as conn:
                tables = {
                    str(row[0])
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                }
                if "analysis_jobs" not in tables or "analysis_outputs" not in tables:
                    return
                conn.execute(
                    """UPDATE analysis_jobs SET status = ?, error_message = ?, model_name = ?,
                       provider_id = ?, input_tokens = ?, output_tokens = ?, response_status = ?
                       WHERE id = ?""",
                    (
                        record.status,
                        record.error_message or None,
                        record.model_name,
                        record.provider_id,
                        record.input_tokens,
                        record.output_tokens,
                        record.response_status,
                        record.job_id,
                    ),
                )
                conn.execute(
                    "UPDATE analysis_outputs SET content = ? WHERE job_id = ? AND output_format = 'markdown'",
                    (record.markdown, record.job_id),
                )
                conn.execute(
                    "DELETE FROM analysis_outputs WHERE job_id = ? AND output_format = 'ki_response'",
                    (record.job_id,),
                )
                if record.ki_response:
                    conn.execute(
                        "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, 'ki_response', ?, ?)",
                        (record.job_id, record.ki_response, record.created_at),
                    )
                conn.commit()
        except sqlite3.Error:
            return

    def _overwrite_existing_artifacts(
        self,
        record: AnalysisOutputRecord,
        documents: list[dict],
        session: dict,
        artifact_paths: dict[str, Path],
    ) -> None:
        """Replace the artifacts belonging to one prepared workflow job in place."""

        article_path = artifact_paths.get("article")
        if article_path:
            _write_text(article_path, record.markdown)
        raw_path = artifact_paths.get("raw")
        if raw_path:
            _write_text(
                raw_path,
                json.dumps(self._build_raw_analysis(record, documents).to_dict(), indent=2, ensure_ascii=False),
            )
        structured_path = artifact_paths.get("structured")
        if structured_path:
            _write_text(
                structured_path,
                json.dumps(self._build_structured_analysis(record, session).to_dict(), indent=2, ensure_ascii=False),
            )
        if record.ki_response and raw_path:
            _write_text(
                _related_raw_artifact_path(raw_path, "ki_response"),
                json.dumps(_parse_ki_json_response(record.ki_response), indent=2, ensure_ascii=False),
            )
        DEFAULT_ANALYSIS_MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_ANALYSIS_MARKDOWN.write_text(record.markdown.rstrip() + "\n", encoding="utf-8")

    def _persist_deferred_publication(
        self,
        record: AnalysisOutputRecord,
        session: dict,
        artifact_paths: dict[str, Path],
        workflow_job_id: int,
        workflow_db_path: Path | None,
    ) -> None:
        """Create publication artifacts when a prepared publication job completes."""

        if record.purpose != "journalistic_publication" or record.status != "done":
            return

        parsed_ki = _parse_ki_json_response(record.ki_response)
        article_markdown = record.markdown
        if parsed_ki:
            title, subtitle, intro, body, sources = _publication_parts_from_ki_json(
                parsed_ki, session
            )
            if body:
                article_markdown = _publication_markdown_from_parts(
                    title=title,
                    subtitle=subtitle,
                    intro=intro,
                    body=body,
                    sources=sources,
                )

        article_path = artifact_paths.get("article")
        if article_path:
            _write_text(article_path, article_markdown)
        _write_text(DEFAULT_ANALYSIS_MARKDOWN, article_markdown)

        publication = self._build_publication_draft(record, article_markdown, session)
        raw_path = artifact_paths.get("raw")
        if raw_path:
            publication_path = _related_raw_artifact_path(raw_path, "publication")
        else:
            publication_path = (
                self._resolve_output_dir(record) / f"job_{record.job_id}.publication.json"
            )
        _write_text(
            publication_path,
            json.dumps(publication.to_dict(), indent=2, ensure_ascii=False),
        )
        self._index_publication_output(
            record,
            publication,
            publication_path,
            workflow_job_id,
            workflow_db_path,
        )

    def _call_provider(
        self, *, request: AnalysisRequest, context: str, pdf_paths: list[Path] | None = None
    ) -> tuple[str, str, int, int, str | None]:
        """Dispatch to the configured KI provider.

        Returns:
            Tuple of (response_text, effective_model_name, error_message_or_None).
        """
        from src.analysis.providers.registry import build_provider

        try:
            provider = build_provider(request.provider_id, **request.provider_kwargs)
            # Strip the embedded "## Prompt-Hinweis" section so the prompt
            # is not sent twice (once in context, once as the prompt argument)
            context_for_provider = re.sub(
                r"\n## Prompt-Hinweis\n.*$", "", context, flags=re.DOTALL
            ).rstrip()
            provider_context = context_for_provider
            provider_pdf_paths = pdf_paths or None
            summary_input_tokens = 0
            summary_output_tokens = 0
            if pdf_paths:
                extracted_documents = [(path, extract_pdf_text(path)) for path in pdf_paths]
                if sum(len(text) for _path, text in extracted_documents) > 140_000:
                    summaries: list[str] = []
                    for path, text in extracted_documents:
                        if not text.strip():
                            summaries.append(f"### {path.name}\nText nicht extrahierbar.")
                            continue
                        summary = provider.analyze(
                            prompt=(
                                "Fasse dieses einzelne Quelldokument sachlich und quellengetreu "
                                "in höchstens 900 Wörtern zusammen. Nenne Kernaussagen, Zahlen, "
                                "Beschlussbezug, Unsicherheiten und offene Fragen. Gib valides JSON "
                                "mit den Feldern title, key_facts, decision_relevance, uncertainties zurück."
                            ),
                            context=text[:40_000],
                            model=request.model_name or None,
                            pdf_paths=None,
                        )
                        summary_input_tokens += summary.input_tokens
                        summary_output_tokens += summary.output_tokens
                        summaries.append(f"### {path.name}\n{summary.response_text}")
                    provider_context = (
                        f"{context_for_provider}\n\n## Dokumentweise Voranalysen\n\n"
                        + "\n\n".join(summaries)
                    )
                    provider_pdf_paths = None
            ki = provider.analyze(
                prompt=request.prompt,
                context=provider_context,
                model=request.model_name or None,
                pdf_paths=provider_pdf_paths,
            )
            return (
                ki.response_text,
                ki.model_name,
                summary_input_tokens + ki.input_tokens,
                summary_output_tokens + ki.output_tokens,
                None,
            )
        except Exception as exc:  # noqa: BLE001
            return "", request.model_name or request.provider_id, 0, 0, str(exc)

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
        session_path = str(document.get("session_path") or "")

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
                "(created_at, session_id, scope, top_numbers_json, purpose, model_name, prompt_version, status, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    str(session["session_id"]),
                    "document",
                    json.dumps([top_number], ensure_ascii=False),
                    DEFAULT_ANALYSIS_PURPOSE,
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
            purpose=DEFAULT_ANALYSIS_PURPOSE,
            model_name=model_name,
            prompt_version="draft",
            prompt_text=prompt,
            markdown=markdown,
            ki_response=ki_response,
            document_count=1,
            source_db=str(db_path),
            session_path=session_path,
            session_date=str(session.get("date", "")),
        )
        self.persist_analysis_artifacts(record, documents=[document], session=session)
        return record

    def persist_analysis_artifacts(
        self,
        record: AnalysisOutputRecord,
        *,
        documents: list[dict] | None = None,
        session: dict | None = None,
    ) -> None:
        """Persist markdown, prompt and versioned JSON output to analysis output dirs."""

        output_dir = self._resolve_output_dir(record)
        output_dir.mkdir(parents=True, exist_ok=True)
        ANALYSIS_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_ANALYSIS_MARKDOWN.parent.mkdir(parents=True, exist_ok=True)

        job_stem = f"job_{record.job_id}"
        parsed_ki = _parse_ki_json_response(record.ki_response)
        md_content = record.markdown
        # Only append KI response for session/tops scope; document scope already
        # embeds the answer under "## KI-Antwort" inside record.markdown
        if parsed_ki and record.purpose == "journalistic_publication":
            title, subtitle, intro, body, sources = _publication_parts_from_ki_json(
                parsed_ki, session or {}
            )
            if body:
                md_content = _publication_markdown_from_parts(
                    title=title,
                    subtitle=subtitle,
                    intro=intro,
                    body=body,
                    sources=sources,
                )
        article_path = _write_text_no_overwrite(
            output_dir / f"{job_stem}.article.md", md_content
        )

        raw_output = self._build_raw_analysis(record, documents or [])
        structured_output = self._build_structured_analysis(record, session or {})
        raw_path = _write_text_no_overwrite(
            output_dir / f"{job_stem}.raw.json",
            json.dumps(raw_output.to_dict(), indent=2, ensure_ascii=False),
        )
        structured_path = _write_text_no_overwrite(
            output_dir / f"{job_stem}.structured.json",
            json.dumps(structured_output.to_dict(), indent=2, ensure_ascii=False),
        )
        if parsed_ki:
            _write_text_no_overwrite(
                output_dir / f"{job_stem}.ki_response.json",
                json.dumps(parsed_ki, indent=2, ensure_ascii=False),
            )
        _write_text_no_overwrite(
            ANALYSIS_PROMPTS_DIR / f"job_{record.job_id}.txt",
            record.prompt_text + "\n",
        )
        snapshot_path = _write_text_no_overwrite(
            PROMPT_SNAPSHOTS_DIR / f"job_{record.job_id}.txt",
            record.prompt_text + "\n",
        )
        record = replace(record, rendered_prompt_snapshot_path=str(snapshot_path))
        self._update_prompt_snapshot_path(record)
        DEFAULT_ANALYSIS_MARKDOWN.write_text(md_content, encoding="utf-8")
        workflow_job_id = self._index_workflow_outputs(
            record=record,
            raw_path=raw_path,
            structured_path=structured_path,
            article_path=article_path,
            session=session or {},
        )
        if record.purpose == "journalistic_publication" and record.status == "done":
            publication = self._build_publication_draft(record, md_content, session or {})
            publication_path = _write_text_no_overwrite(
                output_dir / f"{job_stem}.publication.json",
                json.dumps(publication.to_dict(), indent=2, ensure_ascii=False),
            )
            if workflow_job_id is not None:
                self._index_publication_output(
                    record, publication, publication_path, workflow_job_id
                )

    def _resolve_output_dir(self, record: AnalysisOutputRecord) -> Path:
        """Compute session-oriented output directory mirroring the raw data structure."""
        if record.session_path:
            # Normalize Windows backslashes before splitting
            p = Path(record.session_path.replace("\\", "/"))
            # session_path: data/raw/YYYY/MM/YYYY-MM-DD-Committee-ID
            # parts[-3]=YYYY, parts[-2]=MM, parts[-1]=session-folder-name
            if len(p.parts) >= 3:
                year, month, folder = p.parts[-3], p.parts[-2], p.parts[-1]
                if year.isdigit() and month.isdigit():
                    return ANALYSIS_OUTPUTS_DIR / year / month / folder
        # Fallback: construct per-session folder from session_date + session_id
        # so online-DB sessions (no session_path) still get isolated directories
        date_src = record.session_date or record.created_at[:10]
        folder = f"{date_src}-{record.session_id}" if record.session_id else date_src
        return ANALYSIS_OUTPUTS_DIR / date_src[:4] / date_src[5:7] / folder

    def export_markdown(self, markdown: str, target: Path | None = None) -> Path:
        """Export markdown to the standard analysis output location."""

        target = target or DEFAULT_ANALYSIS_MARKDOWN
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
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
                model_name TEXT,
                provider_id TEXT NOT NULL DEFAULT 'none',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                response_status TEXT NOT NULL DEFAULT 'not_requested',
                prompt_version TEXT,
                prompt_template_id TEXT,
                prompt_template_revision INTEGER,
                prompt_template_label TEXT,
                rendered_prompt_snapshot_path TEXT,
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
        self._ensure_column(conn, "analysis_jobs", "purpose", "TEXT NOT NULL DEFAULT 'content_analysis'")
        self._ensure_column(conn, "analysis_jobs", "prompt_template_id", "TEXT")
        self._ensure_column(conn, "analysis_jobs", "prompt_template_revision", "INTEGER")
        self._ensure_column(conn, "analysis_jobs", "prompt_template_label", "TEXT")
        self._ensure_column(conn, "analysis_jobs", "rendered_prompt_snapshot_path", "TEXT")
        self._ensure_column(conn, "analysis_jobs", "provider_id", "TEXT NOT NULL DEFAULT 'none'")
        self._ensure_column(conn, "analysis_jobs", "input_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "analysis_jobs", "output_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "analysis_jobs", "response_status", "TEXT NOT NULL DEFAULT 'not_requested'")

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

    def _get_session_path(self, db_path: Path, session_id: str) -> str:
        """Return the session_path for a given session, or empty string if not found."""
        if not db_path.exists():
            return ""
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT session_path FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return str(row[0]) if row and row[0] else ""

    def _build_raw_analysis(
        self, record: AnalysisOutputRecord, documents: list[dict]
    ) -> RawAnalysisOutput:
        raw_documents = [
            RawAnalysisDocument(
                title=str(doc.get("title") or ""),
                document_type=str(doc.get("document_type") or ""),
                agenda_item=str(doc.get("agenda_item") or ""),
                url=str(doc.get("url") or ""),
                local_path=str(doc.get("local_path") or ""),
                source_available=_source_available(doc),
            )
            for doc in documents
        ]
        return RawAnalysisOutput(
            job_id=record.job_id,
            session_id=record.session_id,
            scope=record.scope,
            top_numbers=record.top_numbers,
            documents=raw_documents,
            source_db=record.source_db,
            session_path=record.session_path,
            created_at=record.created_at,
        )

    def _build_structured_analysis(
        self, record: AnalysisOutputRecord, session: dict
    ) -> StructuredAnalysisOutput:
        parsed = _parse_ki_json_response(record.ki_response)
        title = (
            str(parsed.get("title") or "")
            or str(parsed.get("topic") or "")
            or str(session.get("meeting_name") or session.get("committee") or "")
        )
        open_questions = _list_from_json_value(
            parsed.get("open_questions") or parsed.get("missing_information") or []
        )
        risks = _list_from_json_value(
            parsed.get("source_notes") or parsed.get("contradictions") or []
        )
        if record.error_message:
            risks.append(record.error_message)
        return StructuredAnalysisOutput(
            job_id=record.job_id,
            session_id=record.session_id,
            purpose=record.purpose or DEFAULT_ANALYSIS_PURPOSE,
            topic=Topic(title=title),
            short_summary=str(parsed.get("short_summary") or parsed.get("summary") or ""),
            document_overview=_dict_list(parsed.get("document_overview")),
            proposal_or_decision=str(parsed.get("proposal_or_decision") or parsed.get("decision_context") or ""),
            background=str(parsed.get("background") or ""),
            financial_impact=str(parsed.get("financial_impact") or parsed.get("effects") or ""),
            legal_or_formal_basis=str(parsed.get("legal_or_formal_basis") or ""),
            affected_groups=_list_from_json_value(parsed.get("affected_groups") or []),
            neutral_assessment=str(parsed.get("neutral_assessment") or ""),
            sources=_dict_list(parsed.get("sources")),
            open_questions=open_questions,
            risks_or_uncertainties=risks,
        )

    def _build_publication_draft(
        self, record: AnalysisOutputRecord, markdown: str, session: dict
    ) -> PublicationDraftOutput:
        parsed = _parse_ki_json_response(record.ki_response)
        title, subtitle, intro, body, sources = _publication_parts_from_ki_json(parsed, session)
        if body:
            body_markdown = _publication_markdown_from_parts(
                title=title,
                subtitle=subtitle,
                intro=intro,
                body=body,
                sources=sources,
            )
        else:
            body_markdown = markdown
        summary_short = subtitle or intro[:240]
        summary_long = intro or body[:1000]
        date_prefix = (record.session_date or record.created_at[:10]).strip()
        slug_source = f"{date_prefix}-{title or record.session_id}"
        return PublicationDraftOutput(
            job_id=record.job_id,
            session_id=record.session_id,
            title=title,
            summary_short=summary_short,
            summary_long=summary_long,
            body_markdown=body_markdown,
            slug=_slugify(slug_source).lower(),
        )

    def _index_workflow_outputs(
        self,
        *,
        record: AnalysisOutputRecord,
        raw_path: Path,
        structured_path: Path,
        article_path: Path,
        session: dict,
    ) -> int | None:
        try:
            workflow_job_id = create_analysis_job(
                AnalysisJobRecord(
                    session_id=record.session_id,
                    scope=record.scope,
                    title=_analysis_job_title(session, record.session_date),
                    top_numbers=record.top_numbers,
                    purpose=record.purpose or DEFAULT_ANALYSIS_PURPOSE,
                    source_db=record.source_db,
                    source_job_id=record.job_id,
                    model_name=record.model_name,
                    provider_id=record.provider_id,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    response_status=record.response_status,
                    prompt_version=record.prompt_version,
                    prompt_template_id=record.prompt_template_id,
                    prompt_template_revision=record.prompt_template_revision,
                    prompt_template_label=record.prompt_template_label,
                    rendered_prompt_snapshot_path=record.rendered_prompt_snapshot_path,
                    status=record.status,
                    error_message=record.error_message,
                )
            )
            add_analysis_output(
                AnalysisArtifactRecord(
                    job_id=workflow_job_id,
                    output_type="raw_analysis",
                    schema_version=ANALYSIS_OUTPUT_SCHEMA_VERSION_V2,
                    json_path=str(raw_path),
                    status=record.status,
                )
            )
            add_analysis_output(
                AnalysisArtifactRecord(
                    job_id=workflow_job_id,
                    output_type="structured_analysis",
                    schema_version=ANALYSIS_OUTPUT_SCHEMA_VERSION_V2,
                    json_path=str(structured_path),
                    status=record.status,
                )
            )
            add_analysis_output(
                AnalysisArtifactRecord(
                    job_id=workflow_job_id,
                    output_type="journalistic_article",
                    schema_version=ANALYSIS_OUTPUT_SCHEMA_VERSION_V2,
                    markdown_path=str(article_path),
                    status=record.status,
                )
            )
            return workflow_job_id
        except sqlite3.Error:
            return None

    def _update_prompt_snapshot_path(self, record: AnalysisOutputRecord) -> None:
        try:
            with sqlite3.connect(record.source_db) as conn:
                self.ensure_analysis_tables(conn)
                conn.execute(
                    "UPDATE analysis_jobs SET rendered_prompt_snapshot_path = ? WHERE id = ?",
                    (record.rendered_prompt_snapshot_path, record.job_id),
                )
                conn.commit()
        except sqlite3.Error:
            return

    def _index_publication_output(
        self,
        record: AnalysisOutputRecord,
        publication: PublicationDraftOutput,
        publication_path: Path,
        workflow_job_id: int,
        workflow_db_path: Path | None = None,
    ) -> None:
        try:
            output_id = add_analysis_output(
                AnalysisArtifactRecord(
                    job_id=workflow_job_id,
                    output_type="publication_draft",
                    schema_version=ANALYSIS_OUTPUT_SCHEMA_VERSION_V2,
                    json_path=str(publication_path),
                    status=publication.status,
                ),
                db_path=workflow_db_path,
            )
            create_publication_job(
                PublicationJobRecord(
                    output_id=output_id,
                    target=publication.publication.target,
                    slug=publication.slug,
                    title=publication.title,
                    status=publication.status,
                    review_status=publication.review.status,
                    published_url=publication.publication.published_url,
                    published_at=publication.publication.published_at,
                ),
                db_path=workflow_db_path,
            )
        except sqlite3.Error:
            return

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _parse_ki_json_response(response_text: str) -> dict:
    """Parse a KI response that should contain a JSON object."""

    text = response_text.strip()
    if not text:
        return {}

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def _with_ki_analysis(markdown: str, response_text: str) -> str:
    """Return one Markdown document with exactly one KI analysis section."""

    base = re.sub(r"\n## KI-Analyse(?:\n.*)?$", "", markdown.rstrip(), flags=re.DOTALL).rstrip()
    response = response_text.strip()
    section = "## KI-Analyse"
    if response:
        section += f"\n\n{_analysis_response_markdown(response)}"
    return f"{base}\n\n{section}\n"


def _analysis_response_markdown(response_text: str) -> str:
    """Render a structured provider response as readable German Markdown."""

    data = _parse_ki_json_response(response_text)
    if not data:
        return response_text.strip()

    parts: list[str] = []
    scalar_sections = (
        ("topic", "Thema"),
        ("short_summary", "Kurzfassung"),
        ("proposal_or_decision", "Beschlussvorschlag und Ergebnis"),
        ("background", "Hintergrund"),
        ("financial_impact", "Finanzielle Auswirkungen"),
        ("legal_or_formal_basis", "Rechtliche und formale Grundlagen"),
        ("neutral_assessment", "Neutrale Einordnung"),
    )
    for key, label in scalar_sections:
        value = str(data.get(key) or "").strip()
        if value:
            parts.append(f"### {label}\n\n{value}")

    documents = data.get("document_overview")
    if isinstance(documents, list) and documents:
        lines = ["### Dokumentübersicht"]
        for index, document in enumerate(documents, start=1):
            if not isinstance(document, dict):
                lines.append(f"{index}. {document}")
                continue
            title = str(document.get("title") or f"Dokument {index}").strip()
            lines.append(f"#### {index}. {title}")
            metadata = [
                str(document.get(key) or "").strip()
                for key in ("document_type", "role")
                if str(document.get(key) or "").strip()
            ]
            if metadata:
                lines.append(f"*{' · '.join(metadata)}*")
            summary = str(document.get("summary") or "").strip()
            if summary:
                lines.append(summary)
        parts.append("\n\n".join(lines))

    list_sections = (
        ("affected_groups", "Betroffene Gruppen"),
        ("open_questions", "Offene Fragen"),
        ("contradictions", "Widersprüche und Unklarheiten"),
    )
    for key, label in list_sections:
        values = data.get(key)
        if isinstance(values, list) and values:
            parts.append(
                f"### {label}\n\n"
                + "\n".join(f"- {str(value).strip()}" for value in values if str(value).strip())
            )

    sources = data.get("sources")
    if isinstance(sources, list) and sources:
        lines = ["### Quellen"]
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                lines.append(f"{index}. {source}")
                continue
            title = str(source.get("title") or "Quelle").strip()
            url = str(source.get("url") or "").strip()
            document_type = str(source.get("document_type") or "").strip()
            agenda_item = str(source.get("agenda_item") or "").strip()
            line = f"{index}. [{title}]({url})" if url else f"{index}. {title}"
            details = " · ".join(value for value in (document_type, agenda_item) if value)
            if details:
                line += f" — {details}"
            lines.append(line)
        parts.append("\n".join(lines))

    known_keys = {key for key, _label in scalar_sections + list_sections} | {
        "document_overview",
        "sources",
    }
    for key, value in data.items():
        if key in known_keys or value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").strip().capitalize()
        parts.append(f"### {label}\n\n{_generic_markdown_value(value)}")

    return "\n\n".join(part for part in parts if part.strip()).strip()


def _generic_markdown_value(value: object) -> str:
    """Render unknown structured fields without discarding their content."""

    if isinstance(value, list):
        return "\n".join(f"- {_generic_markdown_value(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(
            f"- **{str(key).replace('_', ' ').capitalize()}:** {_generic_markdown_value(item)}"
            for key, item in value.items()
        )
    return str(value).strip()


def _analysis_job_title(session: dict, fallback_date: str = "") -> str:
    """Build the concise human-readable title used throughout the web UI."""

    date = str(session.get("date") or fallback_date or "ohne Datum")
    committee = str(
        session.get("committee")
        or session.get("meeting_name")
        or session.get("name")
        or "unbekanntes Gremium"
    )
    return f"Analyse Sitzung {date} - {committee}"


def _publication_parts_from_ki_json(
    parsed: dict, session: dict
) -> tuple[str, str, str, str, list]:
    article = parsed.get("article") if isinstance(parsed.get("article"), dict) else {}
    title = (
        str(parsed.get("title") or "")
        or str(article.get("title") or "")
        or str(session.get("meeting_name") or session.get("committee") or "Analyseentwurf")
    )
    subtitle = str(parsed.get("subtitle") or "")
    intro = str(parsed.get("intro") or "")
    body = str(parsed.get("body") or "")

    if article:
        title = str(article.get("title") or title)
        subtitle = str(article.get("subtitle") or subtitle)
        intro = str(article.get("teaser") or intro)
        body = str(article.get("body_markdown") or body)

    sources = parsed.get("sources") or article.get("sources") or []
    if not isinstance(sources, list):
        sources = []

    return title, subtitle, intro, body, sources


def _publication_markdown_from_parts(
    *,
    title: str,
    subtitle: str,
    intro: str,
    body: str,
    sources: list,
) -> str:
    parts: list[str] = []

    if title:
        parts.append(f"# {title}")
    if subtitle:
        parts.append(f"**{subtitle}**")
    if intro:
        parts.append(intro)
    if body:
        parts.append(body)
    if sources:
        parts.append("## Quellen")
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                continue
            source_title = str(source.get("title") or "Quelle")
            document_type = str(source.get("document_type") or "")
            url = str(source.get("url") or "")
            line = f"{index}. {source_title}"
            if document_type:
                line += f" ({document_type})"
            if url:
                line += f" - {url}"
            parts.append(line)

    return "\n\n".join(parts).strip()


def _list_from_json_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _slugify(text: str) -> str:
    """Convert arbitrary text to a safe, ASCII filename slug."""
    # Normalise unicode: decompose accents, then map common German chars explicitly
    replacements = {"Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    # Strip remaining non-ASCII via NFKD + encode
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # Replace any non-alphanumeric character with hyphen
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    return text.strip("-")[:30]


def _job_stem(record: AnalysisOutputRecord) -> str:
    """Build a semantic filename stem for a job's output files."""
    tops_slug = "-".join(_slugify(t) for t in record.top_numbers[:3] if t) or "all"
    model_slug = _slugify(record.model_name) or "none"
    return f"job_{record.job_id}-{record.scope}-{tops_slug}-{model_slug}"


def _write_text_no_overwrite(path: Path, content: str) -> Path:
    """Write text to a unique path without replacing existing artifacts."""

    path.parent.mkdir(parents=True, exist_ok=True)
    target = path
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.stem}.{counter}{path.suffix}")
        counter += 1
    target.write_text(content.rstrip() + "\n", encoding="utf-8")
    return target


def _write_text(path: Path, content: str) -> Path:
    """Write a known job artifact in place."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def _related_raw_artifact_path(raw_path: Path, artifact_type: str) -> Path:
    """Derive a sibling JSON path while preserving a collision suffix."""

    match = re.fullmatch(
        r"(?P<prefix>.+)\.raw(?P<collision>\.\d+)?\.json",
        raw_path.name,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Kein gültiges Raw-Analyseartefakt: {raw_path.name}")
    collision = match.group("collision") or ""
    return raw_path.with_name(
        f"{match.group('prefix')}.{artifact_type}{collision}.json"
    )


def _source_available(document: dict) -> bool:
    """Return true only when the local source file was resolved and exists."""

    if "source_file_available" in document:
        return bool(document["source_file_available"])

    resolved_local_path = document.get("resolved_local_path")
    if resolved_local_path:
        return Path(str(resolved_local_path)).is_file()

    resolved = resolve_local_file_path(
        session_path=str(document.get("session_path") or ""),
        local_path=str(document.get("local_path") or ""),
    )
    return bool(resolved and resolved.is_file())


def _pdf_paths_from_documents(documents: list[dict]) -> list[Path]:
    pdf_paths: list[Path] = []
    for document in documents:
        if not document.get("source_file_available"):
            continue
        resolved = document.get("resolved_local_path")
        if not resolved:
            continue
        path = Path(str(resolved))
        if path.suffix.lower() == ".pdf" and path.is_file():
            pdf_paths.append(path)
    return pdf_paths


def _prioritize_documents(documents: list[dict]) -> list[dict]:
    """Put decision-bearing sources before large supporting attachments."""

    priorities = (
        "beschlussvorlage",
        "vorlage",
        "begründung",
        "planzeichnung",
        "umweltbericht",
        "stellungnahme",
        "prognose",
        "gutachten",
    )

    def sort_key(document: dict) -> tuple[int, str]:
        title = str(document.get("title") or "").casefold()
        priority = next(
            (index for index, marker in enumerate(priorities) if marker in title),
            len(priorities),
        )
        return priority, title

    return sorted(documents, key=sort_key)
