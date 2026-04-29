"""Read-only data access for the Django web UI."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.analysis.prompt_registry import load_templates
from src.analysis.schemas import normalize_analysis_output
from src.analysis.service import AnalysisRequest, AnalysisService


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_INDEX_DB = REPO_ROOT / "data" / "db" / "local_index.sqlite"
ANALYSIS_WORKFLOW_DB = REPO_ROOT / "data" / "db" / "analysis_workflow.sqlite"
ANALYSIS_OUTPUTS_DIR = REPO_ROOT / "data" / "analysis_outputs"
PROMPT_TEMPLATES_PATH = REPO_ROOT / "configs" / "prompt_templates.json"
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 900

JOB_ID_RE = re.compile(r"job[_-](?P<job_id>[\w.-]+)", re.IGNORECASE)


def _connect(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _rows(db_path: Path, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    if conn is None:
        return []
    try:
        with conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _first_row(db_path: Path, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    rows = _rows(db_path, query, params)
    return rows[0] if rows else None


def list_sessions() -> list[dict[str, Any]]:
    """Return indexed sessions, enriched with simple counts when available."""

    sessions = _rows(
        LOCAL_INDEX_DB,
        """
        SELECT
            s.session_id,
            s.date,
            s.committee,
            s.meeting_name,
            s.start_time,
            s.location,
            COUNT(DISTINCT ai.id) AS agenda_count,
            COUNT(DISTINCT d.id) AS document_count
        FROM sessions s
        LEFT JOIN agenda_items ai ON ai.session_id = s.session_id
        LEFT JOIN documents d ON d.session_id = s.session_id
        GROUP BY s.session_id, s.date, s.committee, s.meeting_name, s.start_time, s.location
        ORDER BY s.date DESC, s.committee ASC
        """,
    )
    return [_with_session_display_fields(session) for session in sessions]


def get_session(session_id: str) -> dict[str, Any] | None:
    """Return one session with agenda items and documents."""

    session = _first_row(
        LOCAL_INDEX_DB,
        """
        SELECT session_id, date, committee, meeting_name, start_time, location, detail_url, session_path
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,),
    )
    if not session:
        return None
    session = _with_session_display_fields(session)

    agenda_items = _rows(
        LOCAL_INDEX_DB,
        """
        SELECT id, number, title, reporter, status, decision, documents_present
        FROM agenda_items
        WHERE session_id = ?
        ORDER BY id
        """,
        (session_id,),
    )
    documents = _rows(
        LOCAL_INDEX_DB,
        """
        SELECT id, title, category, document_type, agenda_item, url, local_path, content_type, content_length
        FROM documents
        WHERE session_id = ?
        ORDER BY COALESCE(agenda_item, ''), title
        """,
        (session_id,),
    )
    documents_by_agenda: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        documents_by_agenda[str(document.get("agenda_item") or "")].append(document)
    for item in agenda_items:
        item["documents"] = documents_by_agenda.get(str(item.get("number") or ""), [])

    session["agenda_items"] = agenda_items
    session["documents"] = documents
    session["source_status"] = check_sources(session_id)
    return session


def check_sources(session_id: str) -> dict[str, Any]:
    """Return lightweight source availability information for a session."""

    session = _first_row(
        LOCAL_INDEX_DB,
        "SELECT session_path FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    documents = _rows(
        LOCAL_INDEX_DB,
        "SELECT local_path FROM documents WHERE session_id = ?",
        (session_id,),
    )
    session_path = Path(str(session.get("session_path") or "")) if session else None
    available = 0
    missing = 0
    for document in documents:
        local_path = str(document.get("local_path") or "")
        candidates = []
        if local_path:
            candidates.append(REPO_ROOT / local_path)
            if session_path and not Path(local_path).is_absolute():
                candidates.append(session_path / local_path)
        if any(path.exists() for path in candidates):
            available += 1
        else:
            missing += 1
    return {
        "session_path": str(session_path or ""),
        "document_count": len(documents),
        "available_count": available,
        "missing_count": missing,
    }


def list_analysis_outputs() -> list[dict[str, Any]]:
    """Return known analysis jobs from workflow tables and output files."""

    jobs: dict[str, dict[str, Any]] = {}
    for db_path in (ANALYSIS_WORKFLOW_DB, LOCAL_INDEX_DB):
        for row in _analysis_jobs_from_db(db_path):
            job_id = str(row.get("job_id") or row.get("id") or "")
            if not job_id:
                continue
            job = jobs.setdefault(job_id, _empty_job(job_id))
            job.update({key: value for key, value in row.items() if value not in (None, "")})
            job["sources"].add(str(db_path.relative_to(REPO_ROOT)))

    for file_job in _analysis_jobs_from_files():
        job_id = str(file_job["job_id"])
        job = jobs.setdefault(job_id, _empty_job(job_id))
        _merge_job(job, file_job)

    sorted_jobs = sorted(
        jobs.values(),
        key=lambda item: str(item.get("created_at") or item.get("job_id") or ""),
        reverse=True,
    )
    return [_public_job(job) for job in sorted_jobs]


def get_analysis_output(job_id: str) -> dict[str, Any] | None:
    """Return one analysis job/output bundle by id."""

    normalized_id = str(job_id)
    for job in list_analysis_outputs():
        if str(job.get("job_id")) == normalized_id:
            return job
    return None


def list_prompt_templates(scope: str = "") -> list[dict[str, Any]]:
    """Return configured prompt templates, optionally filtered by scope."""

    templates = load_templates(PROMPT_TEMPLATES_PATH)
    if not scope:
        return templates
    return [template for template in templates if scope in template.get("scope", [])]


def get_prompt_template(template_id: str) -> dict[str, Any] | None:
    """Return one prompt template by id."""

    for template in list_prompt_templates():
        if str(template.get("id") or "") == template_id:
            return template
    return None


def analysis_purpose_options() -> list[dict[str, str]]:
    """Return supported analysis purposes for the web form."""

    return [
        {"value": "content_analysis", "label": "Inhaltsanalyse"},
        {"value": "fact_extraction", "label": "Strukturierte Faktenerfassung"},
        {"value": "session_preparation", "label": "Sitzungsvorbereitung"},
        {"value": "journalistic_publication", "label": "Journalistischer Publikationsentwurf"},
    ]


def provider_options() -> list[dict[str, str]]:
    """Return provider options known to the existing analysis service."""

    return [
        {"value": "none", "label": "Kein Provider (nur Grundlage)"},
        {"value": "claude", "label": "Claude (Anthropic)"},
        {"value": "codex", "label": "Codex (OpenAI)"},
        {"value": "ollama", "label": "Ollama (lokal)"},
    ]


def service_status() -> dict[str, Any]:
    """Return lightweight status for service pages."""

    return {
        "local_index_exists": LOCAL_INDEX_DB.exists() and LOCAL_INDEX_DB.stat().st_size > 0,
        "online_index_exists": (REPO_ROOT / "data" / "db" / "online_session_index.sqlite").exists(),
        "qdrant_exists": (REPO_ROOT / "data" / "db" / "qdrant").exists(),
        "raw_data_exists": (REPO_ROOT / "data" / "raw").exists(),
        "local_index_path": "data/db/local_index.sqlite",
        "online_index_path": "data/db/online_session_index.sqlite",
        "qdrant_path": "data/db/qdrant/",
        "raw_data_path": "data/raw/",
    }


def build_service_command(action: str, data: dict[str, Any]) -> tuple[list[str] | None, list[str]]:
    """Build a whitelisted fetch/build command."""

    try:
        command = _service_command(action, data)
    except ValueError as exc:
        return None, [str(exc)]
    return command, []


def run_analysis_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate web form data and run the existing analysis service."""

    errors: list[str] = []
    session_id = str(data.get("session_id") or "").strip()
    scope = str(data.get("scope") or "session").strip()
    selected_tops = [str(top).strip() for top in data.get("top_numbers", []) if str(top).strip()]
    provider_id = str(data.get("provider_id") or "none").strip()
    model_name = str(data.get("model_name") or "").strip()
    template_id = str(data.get("template_id") or "").strip()
    prompt = str(data.get("prompt_text") or "").strip()
    purpose = str(data.get("purpose") or "content_analysis").strip()

    session = get_session(session_id) if session_id else None
    if not session:
        errors.append("Bitte eine vorhandene Sitzung waehlen.")
    if scope not in {"session", "tops"}:
        errors.append("Der Scope ist ungueltig.")
    if scope == "tops" and not selected_tops:
        errors.append("Bitte mindestens einen TOP waehlen oder Scope 'Ganze Sitzung' nutzen.")
    if provider_id not in {option["value"] for option in provider_options()}:
        errors.append("Der KI-Provider ist ungueltig.")
    if purpose not in {option["value"] for option in analysis_purpose_options()}:
        errors.append("Der Analysezweck ist ungueltig.")

    template = get_prompt_template(template_id) if template_id else None
    if template:
        purpose = str(template.get("purpose") or purpose)
        if not prompt:
            prompt = str(template.get("text") or "")
    if not prompt:
        errors.append("Bitte einen Prompt eingeben oder eine Vorlage waehlen.")

    if errors or not session:
        return None, errors

    request = AnalysisRequest(
        db_path=LOCAL_INDEX_DB,
        session=session,
        scope=scope,
        selected_tops=selected_tops if scope == "tops" else [],
        prompt=prompt,
        provider_id=provider_id,
        model_name=model_name,
        prompt_version=template_id or "web",
        purpose=purpose,
    )
    record = AnalysisService().run_journalistic_analysis(request)
    return record.to_dict(), []


def _service_command(action: str, data: dict[str, Any]) -> list[str]:
    """Return a command for one known service action."""

    if action == "fetch_sessions":
        year = _validated_year(data.get("year"))
        months = _validated_months(data.get("months"))
        return [sys.executable, "scripts/fetch_sessions.py", str(year), "--months", *months]

    if action == "fetch_session_from_index":
        session_id = str(data.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("Bitte eine Session-ID angeben.")
        return [sys.executable, "scripts/fetch_session_from_index.py", "--session-id", session_id]

    if action == "build_local_index":
        command = [sys.executable, "scripts/build_local_index.py"]
        if data.get("refresh_existing"):
            command.append("--refresh-existing")
        if data.get("only_refresh"):
            command.append("--only-refresh")
        return command

    if action == "build_online_index":
        year = _validated_year(data.get("year"))
        months = _validated_months(data.get("months"))
        command = [sys.executable, "scripts/build_online_index_db.py", str(year), "--months", *months]
        if data.get("refresh_existing"):
            command.append("--refresh-existing")
        if data.get("only_refresh"):
            command.append("--only-refresh")
        return command

    if action == "build_vector_index":
        command = [sys.executable, "scripts/build_vector_index.py"]
        limit = str(data.get("limit") or "").strip()
        if limit:
            try:
                parsed_limit = int(limit)
            except ValueError as exc:
                raise ValueError("Limit muss eine Zahl sein.") from exc
            if parsed_limit < 1:
                raise ValueError("Limit muss groesser als 0 sein.")
            command.extend(["--limit", str(parsed_limit)])
        return command

    raise ValueError("Unbekannte Service-Aktion.")


def _validated_year(value: Any) -> int:
    try:
        year = int(str(value or "").strip())
    except ValueError as exc:
        raise ValueError("Bitte ein gueltiges Jahr angeben.") from exc
    if year < 2000 or year > 2100:
        raise ValueError("Das Jahr muss zwischen 2000 und 2100 liegen.")
    return year


def _validated_months(value: Any) -> list[str]:
    raw = str(value or "").replace(",", " ").strip()
    if not raw:
        return [str(month) for month in range(1, 13)]
    months: list[str] = []
    for token in raw.split():
        try:
            month = int(token)
        except ValueError as exc:
            raise ValueError("Monate muessen Zahlen zwischen 1 und 12 sein.") from exc
        if month < 1 or month > 12:
            raise ValueError("Monate muessen zwischen 1 und 12 liegen.")
        months.append(str(month))
    return months


def source_overview() -> dict[str, Any]:
    """Return basic source availability for overview pages."""

    return {
        "local_index_exists": LOCAL_INDEX_DB.exists() and LOCAL_INDEX_DB.stat().st_size > 0,
        "analysis_outputs_exists": ANALYSIS_OUTPUTS_DIR.exists(),
        "session_count": len(list_sessions()),
        "analysis_count": len(list_analysis_outputs()),
        "local_index_path": str(LOCAL_INDEX_DB.relative_to(REPO_ROOT)),
        "analysis_outputs_path": str(ANALYSIS_OUTPUTS_DIR.relative_to(REPO_ROOT)),
    }


def _with_session_display_fields(session: dict[str, Any]) -> dict[str, Any]:
    """Add UI-oriented display fields without changing source values."""

    enriched = dict(session)
    enriched["display_date"] = _format_german_date(str(enriched.get("date") or ""))
    return enriched


def _format_german_date(value: str) -> str:
    """Format ISO dates as DD.MM.YYYY for UI display."""

    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def _analysis_jobs_from_db(db_path: Path) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    if conn is None:
        return []
    try:
        if not _table_exists(conn, "analysis_jobs"):
            return []
        job_rows = [dict(row) for row in conn.execute("SELECT * FROM analysis_jobs").fetchall()]
        if not _table_exists(conn, "analysis_outputs"):
            return job_rows
        output_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT job_id, output_format, content, created_at FROM analysis_outputs"
            ).fetchall()
        ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    outputs_by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for output in output_rows:
        outputs_by_job[str(output.get("job_id"))].append(output)

    jobs = []
    for row in job_rows:
        row["job_id"] = row.get("id")
        row["db_outputs"] = outputs_by_job.get(str(row.get("id")), [])
        for output in row["db_outputs"]:
            fmt = str(output.get("output_format") or "").lower()
            content = str(output.get("content") or "")
            if fmt in {"markdown", "md"}:
                row.setdefault("markdown", content)
            elif fmt in {"ki_response", "text"}:
                row.setdefault("ki_response", content)
        jobs.append(row)
    return jobs


def _analysis_jobs_from_files() -> list[dict[str, Any]]:
    if not ANALYSIS_OUTPUTS_DIR.exists():
        return []

    jobs: dict[str, dict[str, Any]] = {}
    for path in ANALYSIS_OUTPUTS_DIR.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        job_id = _job_id_from_path(path)
        if not job_id:
            continue
        job = jobs.setdefault(job_id, _empty_job(job_id))
        try:
            rel_path = str(path.relative_to(REPO_ROOT))
        except ValueError:
            rel_path = str(path)
        job["files"].append(rel_path)
        job["sources"].add(rel_path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            _read_json_output(path, job)
        elif suffix == ".md":
            job.setdefault("markdown", _read_text(path))
        elif suffix == ".txt" and "prompts" in path.parts:
            job.setdefault("prompt_text", _read_text(path))

    return list(jobs.values())


def _read_json_output(path: Path, job: dict[str, Any]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        job["warnings"].append(f"{path.name} konnte nicht gelesen werden.")
        return
    normalized = normalize_analysis_output(data if isinstance(data, dict) else {})
    job["structured_outputs"].append(normalized)
    for key in (
        "job_id",
        "created_at",
        "session_id",
        "scope",
        "purpose",
        "model_name",
        "prompt_version",
        "prompt_text",
        "markdown",
        "ki_response",
        "status",
        "error_message",
        "session_date",
        "session_path",
        "output_type",
        "schema_version",
    ):
        value = normalized.get(key)
        if value not in (None, "", []):
            job[key] = value
    if "body_markdown" in normalized and not job.get("markdown"):
        job["markdown"] = str(normalized.get("body_markdown") or "")


def _job_id_from_path(path: Path) -> str:
    match = JOB_ID_RE.search(path.stem)
    if match:
        return match.group("job_id").split(".")[0]
    return ""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _empty_job(job_id: str) -> dict[str, Any]:
    return {
        "job_id": str(job_id),
        "created_at": "",
        "session_id": "",
        "scope": "",
        "purpose": "",
        "model_name": "",
        "prompt_version": "",
        "status": "",
        "error_message": "",
        "markdown": "",
        "ki_response": "",
        "prompt_text": "",
        "output_type": "",
        "schema_version": "",
        "files": [],
        "sources": set(),
        "structured_outputs": [],
        "warnings": [],
    }


def _merge_job(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key == "sources":
            target["sources"].update(value)
        elif key in {"files", "structured_outputs", "warnings"}:
            target[key].extend(value)
        elif value not in (None, "", []) and not target.get(key):
            target[key] = value


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    public = dict(job)
    public["sources"] = sorted(public.get("sources", []))
    public["files"] = sorted(set(public.get("files", [])))
    public["has_content"] = any(
        public.get(key) for key in ("markdown", "ki_response", "prompt_text", "structured_outputs")
    )
    return public
