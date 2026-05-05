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
            job_id = str(row.get("job_id") or "")
            if not job_id:
                continue
            job = jobs.setdefault(job_id, _empty_job(job_id))
            job.update({key: value for key, value in row.items() if value not in (None, "")})
            job["sources"].add(str(db_path.relative_to(paths.REPO_ROOT)))

    for file_job in _analysis_jobs_from_files():
        job_id = _job_key_for_file_job(file_job, jobs)
        job = jobs.setdefault(job_id, _empty_job(job_id))
        _merge_job(job, file_job)

    sorted_jobs = sorted(
        jobs.values(),
        key=lambda item: str(item.get("created_at") or item.get("job_id") or ""),
        reverse=True,
    )
    return [_public_job(job) for job in sorted_jobs]


def _job_key_for_file_job(file_job: dict[str, Any], jobs: dict[str, dict[str, Any]]) -> str:
    file_job_id = str(file_job["job_id"])
    matches = [
        job_key
        for job_key, job in jobs.items()
        if str(job.get("db_job_id") or "") == file_job_id
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        file_sources = {str(source) for source in file_job.get("sources", set())}
        source_matches = [
            job_key
            for job_key in matches
            if file_sources & {str(source) for source in jobs[job_key].get("sources", set())}
        ]
        if len(source_matches) == 1:
            return source_matches[0]
        workflow_matches = [job_key for job_key in matches if job_key.startswith("workflow:")]
        if len(workflow_matches) == 1:
            return workflow_matches[0]
    return file_job_id


def get_analysis_output(job_id: str) -> dict[str, Any] | None:
    """Return one analysis job/output bundle by id."""

    normalized_id = str(job_id)
    jobs = list_analysis_outputs()
    for job in jobs:
        if str(job.get("job_id")) == normalized_id:
            return job
    db_matches = [job for job in jobs if str(job.get("db_job_id") or "") == normalized_id]
    if len(db_matches) == 1:
        return db_matches[0]
    return None


def canonical_analysis_job_id(result: dict[str, Any]) -> str:
    """Return the canonical public id for a freshly created analysis result."""

    raw_job_id = str(result.get("job_id") or "")
    if not raw_job_id:
        return ""
    jobs = list_analysis_outputs()
    workflow_source_matches = [
        job for job in jobs
        if str(job.get("db_source") or "") == "workflow"
        and str(job.get("source_job_id") or "") == raw_job_id
    ]
    if len(workflow_source_matches) == 1:
        return str(workflow_source_matches[0].get("job_id") or raw_job_id)

    exact = get_analysis_output(raw_job_id)
    if exact:
        return str(exact.get("job_id") or raw_job_id)

    for preferred in (f"workflow:{raw_job_id}", f"local:{raw_job_id}"):
        if any(str(job.get("job_id") or "") == preferred for job in jobs):
            return preferred
    return raw_job_id


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
        output_rows = _analysis_output_rows(conn)
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    outputs_by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for output in output_rows:
        outputs_by_job[str(output.get("job_id"))].append(output)

    source_key = _db_source_key(db_path)
    jobs = []
    for row in job_rows:
        db_job_id = row.get("job_id") or row.get("id")
        if not db_job_id:
            continue
        row["db_job_id"] = db_job_id
        row["db_source"] = source_key
        row["job_id"] = f"{source_key}:{db_job_id}"
        row["db_outputs"] = outputs_by_job.get(str(db_job_id), [])
        for output in row["db_outputs"]:
            _merge_db_output(row, output)
        _load_prompt_snapshot(row)
        jobs.append(row)
    return jobs


def _db_source_key(db_path: Path) -> str:
    if db_path == paths.ANALYSIS_WORKFLOW_DB:
        return "workflow"
    if db_path == paths.LOCAL_INDEX_DB:
        return "local"
    return db_path.stem.replace("_index", "").replace("analysis_", "") or "db"


def _analysis_output_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    columns = _table_columns(conn, "analysis_outputs")
    if {"job_id", "output_format", "content", "created_at"} <= columns:
        selected = [
            column
            for column in ("id", "job_id", "output_format", "content", "created_at")
            if column in columns
        ]
        order_column = "id" if "id" in columns else "created_at"
        return [
            dict(row)
            for row in conn.execute(
                f"SELECT {', '.join(selected)} FROM analysis_outputs ORDER BY {order_column}"
            ).fetchall()
        ]
    if {"job_id", "output_type", "json_path", "markdown_path"} <= columns:
        selected = [
            column
            for column in (
                "output_id",
                "job_id",
                "output_type",
                "schema_version",
                "json_path",
                "markdown_path",
                "status",
                "created_at",
            )
            if column in columns
        ]
        order_column = "output_id" if "output_id" in columns else "created_at"
        return [
            dict(row)
            for row in conn.execute(
                f"SELECT {', '.join(selected)} FROM analysis_outputs ORDER BY {order_column}"
            ).fetchall()
        ]
    return []


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _merge_db_output(job: dict[str, Any], output: dict[str, Any]) -> None:
    fmt = str(output.get("output_format") or "").lower()
    content = str(output.get("content") or "")
    if fmt in {"markdown", "md"}:
        job.setdefault("markdown", content)
    elif fmt in {"ki_response", "text"}:
        job.setdefault("ki_response", content)

    output_type = str(output.get("output_type") or "").strip()
    if output_type:
        job.setdefault("output_type", output_type)
    schema_version = str(output.get("schema_version") or "").strip()
    if schema_version:
        job.setdefault("schema_version", schema_version)
    output_status = str(output.get("status") or "").strip()
    if output_status:
        job.setdefault("status", output_status)

    for key in ("json_path", "markdown_path"):
        output_path = _resolve_output_path(output.get(key))
        if output_path is None:
            continue
        _add_file_source(job, output_path)
        if key == "json_path":
            job.setdefault("warnings", [])
            job.setdefault("structured_outputs", [])
            _read_json_output(output_path, job, preserve_job_id=True)
        elif key == "markdown_path" and not job.get("markdown"):
            job["markdown"] = _read_text(output_path)


def _resolve_output_path(value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace("\\", "/")
    path = Path(raw)
    if not path.is_absolute():
        path = paths.REPO_ROOT / path
    return path


def _add_file_source(job: dict[str, Any], path: Path) -> None:
    try:
        rel_path = path.relative_to(paths.REPO_ROOT).as_posix()
    except ValueError:
        rel_path = str(path)
    job.setdefault("files", []).append(rel_path)
    job.setdefault("sources", set()).add(rel_path)


def _analysis_jobs_from_files() -> list[dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for root in _analysis_artifact_roots():
        if not root.exists():
            continue
        is_prompt_root = root == paths.ANALYSIS_PROMPTS_DIR
        for path in root.rglob("*"):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            job_id = _job_id_from_path(path)
            if not job_id:
                continue
            job = jobs.setdefault(job_id, _empty_job(job_id))
            try:
                rel_path = path.relative_to(paths.REPO_ROOT).as_posix()
            except ValueError:
                rel_path = str(path)
            job["files"].append(rel_path)
            job["sources"].add(rel_path)
            suffix = path.suffix.lower()
            if suffix == ".json":
                _read_json_output(path, job)
            elif suffix == ".md" and not job.get("markdown"):
                job["markdown"] = _read_text(path)
            elif suffix == ".txt" and is_prompt_root:
                job["prompt_text"] = _read_text(path).strip()

    return list(jobs.values())


def _analysis_artifact_roots() -> list[Path]:
    roots = [paths.ANALYSIS_OUTPUTS_DIR, paths.ANALYSIS_PROMPTS_DIR]
    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)
    return unique_roots


def _read_json_output(path: Path, job: dict[str, Any], *, preserve_job_id: bool = False) -> None:
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
        "prompt_template_id",
        "prompt_template_revision",
        "prompt_template_label",
        "rendered_prompt_snapshot_path",
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
        if preserve_job_id and key == "job_id":
            continue
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


def _load_prompt_snapshot(job: dict[str, Any]) -> None:
    if job.get("prompt_text"):
        return
    snapshot_path = _resolve_output_path(job.get("rendered_prompt_snapshot_path"))
    if snapshot_path is None or not snapshot_path.is_file():
        return
    job["prompt_text"] = _read_text(snapshot_path).strip()


def _empty_job(job_id: str) -> dict[str, Any]:
    return {
        "job_id": str(job_id),
        "created_at": "",
        "session_id": "",
        "scope": "",
        "purpose": "",
        "model_name": "",
        "prompt_version": "",
        "prompt_template_id": "",
        "prompt_template_revision": None,
        "prompt_template_label": "",
        "rendered_prompt_snapshot_path": "",
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
    public["sources"] = sorted(
        source for source in public.get("sources", [])
        if not _is_private_prompt_artifact_source(source, public)
    )
    public["files"] = sorted(
        {
            file_path for file_path in public.get("files", [])
            if not _is_private_prompt_artifact_source(file_path, public)
        }
    )
    public["has_content"] = any(
        public.get(key) for key in ("markdown", "ki_response", "prompt_text", "structured_outputs")
    )
    return public


def _is_private_prompt_artifact_source(value: Any, job: dict[str, Any]) -> bool:
    raw = str(value or "")
    if not raw:
        return False
    raw_normalized = raw.replace("\\", "/")
    snapshot = str(job.get("rendered_prompt_snapshot_path") or "")
    snapshot_normalized = snapshot.replace("\\", "/")
    if snapshot_normalized and raw_normalized == snapshot_normalized:
        return True
    if snapshot and Path(snapshot).is_absolute():
        try:
            if Path(raw).resolve() == Path(snapshot).resolve():
                return True
        except OSError:
            pass
    return _path_points_to_private_prompt_artifact(raw)


def _path_points_to_private_prompt_artifact(value: str) -> bool:
    candidate = Path(value)
    candidates = [candidate]
    if not candidate.is_absolute():
        candidates.append(paths.REPO_ROOT / candidate)

    private_roots = (
        paths.PRIVATE_DATA_DIR,
        paths.PROMPT_SNAPSHOTS_DIR,
        paths.ANALYSIS_PROMPTS_DIR,
        paths.PROMPT_TEMPLATES_PATH.parent,
    )
    for candidate_path in candidates:
        if any(_path_is_relative_to(candidate_path, root) for root in private_roots):
            return True

    normalized = value.replace("\\", "/")
    for root in private_roots:
        try:
            relative_root = root.relative_to(paths.REPO_ROOT).as_posix()
        except ValueError:
            continue
        if normalized == relative_root or normalized.startswith(f"{relative_root}/"):
            return True
    return False


def _path_is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return True
