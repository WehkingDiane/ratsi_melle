"""Analysis API that decouples GUI workflows from analysis logic."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import re
import unicodedata

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis
from src.analysis.providers.registry import PROVIDER_NONE
from src.analysis.schemas import AnalysisOutputRecord
from src.paths import ANALYSIS_OUTPUTS_DIR, ANALYSIS_PROMPTS_DIR, DEFAULT_ANALYSIS_MARKDOWN


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
        documents = enrich_documents_for_analysis(documents)
        session_path = self._get_session_path(db_path, session_id)
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
            session_id=session_id,
            scope=request.scope,
            top_numbers=list(request.selected_tops) if request.scope != "session" else [],
            model_name=effective_model,
            prompt_version=request.prompt_version,
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
            # Strip the embedded "## Prompt-Hinweis" section so the prompt
            # is not sent twice (once in context, once as the prompt argument)
            context_for_provider = re.sub(
                r"\n## Prompt-Hinweis\n.*$", "", context, flags=re.DOTALL
            ).rstrip()
            ki = provider.analyze(
                prompt=request.prompt,
                context=context_for_provider,
                model=request.model_name or None,
                pdf_paths=request.pdf_paths or None,
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
            session_path=session_path,
            session_date=str(session.get("date", "")),
        )
        self.persist_analysis_artifacts(record)
        return record

    def persist_analysis_artifacts(self, record: AnalysisOutputRecord) -> None:
        """Persist markdown, prompt and versioned JSON output to analysis output dirs."""

        output_dir = self._resolve_output_dir(record)
        output_dir.mkdir(parents=True, exist_ok=True)
        ANALYSIS_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_ANALYSIS_MARKDOWN.parent.mkdir(parents=True, exist_ok=True)

        job_stem = _job_stem(record)
        md_content = record.markdown
        # Only append KI response for session/tops scope; document scope already
        # embeds the answer under "## KI-Antwort" inside record.markdown
        if record.ki_response and record.scope != "document":
            md_content += f"\n\n## KI-Analyse\n\n{record.ki_response}\n"
        (output_dir / f"{job_stem}.md").write_text(md_content, encoding="utf-8")
        (output_dir / f"{job_stem}.json").write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (ANALYSIS_PROMPTS_DIR / f"job_{record.job_id}.txt").write_text(
            record.prompt_text + "\n", encoding="utf-8"
        )
        DEFAULT_ANALYSIS_MARKDOWN.write_text(md_content, encoding="utf-8")

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

    def _get_session_path(self, db_path: Path, session_id: str) -> str:
        """Return the session_path for a given session, or empty string if not found."""
        if not db_path.exists():
            return ""
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT session_path FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return str(row[0]) if row and row[0] else ""


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

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
