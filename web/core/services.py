"""Read-only data access for the Django web UI."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.analysis.schemas import normalize_analysis_output


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_INDEX_DB = REPO_ROOT / "data" / "db" / "local_index.sqlite"
ANALYSIS_WORKFLOW_DB = REPO_ROOT / "data" / "db" / "analysis_workflow.sqlite"
ANALYSIS_OUTPUTS_DIR = REPO_ROOT / "data" / "analysis_outputs"

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

    return _rows(
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
        LIMIT 200
        """,
    )


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
        rel_path = str(path.relative_to(REPO_ROOT))
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
