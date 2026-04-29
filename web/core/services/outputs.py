"""Analysis output loading for the Django web UI."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.analysis.schemas import normalize_analysis_output

from . import paths
from .db import connect
from .db import table_exists


JOB_ID_RE = re.compile(r"job[_-](?P<job_id>[\w.-]+)", re.IGNORECASE)


def list_analysis_outputs() -> list[dict[str, Any]]:
    """Return known analysis jobs from workflow tables and output files."""

    jobs: dict[str, dict[str, Any]] = {}
    for db_path in (paths.ANALYSIS_WORKFLOW_DB, paths.LOCAL_INDEX_DB):
        for row in _analysis_jobs_from_db(db_path):
            job_id = str(row.get("job_id") or row.get("id") or "")
            if not job_id:
                continue
            job = jobs.setdefault(job_id, _empty_job(job_id))
            job.update({key: value for key, value in row.items() if value not in (None, "")})
            job["sources"].add(str(db_path.relative_to(paths.REPO_ROOT)))

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


def _analysis_jobs_from_db(db_path: Path) -> list[dict[str, Any]]:
    conn = connect(db_path)
    if conn is None:
        return []
    try:
        if not table_exists(conn, "analysis_jobs"):
            return []
        job_rows = [dict(row) for row in conn.execute("SELECT * FROM analysis_jobs").fetchall()]
        if not table_exists(conn, "analysis_outputs"):
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
    if not paths.ANALYSIS_OUTPUTS_DIR.exists():
        return []

    jobs: dict[str, dict[str, Any]] = {}
    for path in paths.ANALYSIS_OUTPUTS_DIR.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        job_id = _job_id_from_path(path)
        if not job_id:
            continue
        job = jobs.setdefault(job_id, _empty_job(job_id))
        try:
            rel_path = str(path.relative_to(paths.REPO_ROOT))
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
