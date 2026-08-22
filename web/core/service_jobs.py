"""Persistent background jobs for service script execution."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path

from .services.paths import SERVICE_JOBS_DB as DEFAULT_SERVICE_JOBS_DB


MAX_OUTPUT_LINES = 500
MAX_RETAINED_JOBS = 50
SERVICE_JOBS_DB = DEFAULT_SERVICE_JOBS_DB
STATUS_LABELS = {
    "queued": "wartet",
    "running": "läuft",
    "ok": "erfolgreich",
    "error": "fehlgeschlagen",
}


@dataclass
class ServiceJob:
    job_id: str
    action: str
    command: list[str]
    status: str = "queued"
    exit_code: int | None = None
    output: str = ""
    started_at: str = ""
    finished_at: str = ""
    summary: str = ""
    created_at: str = ""

    @property
    def command_text(self) -> str:
        return " ".join(self.command)

    @property
    def status_label(self) -> str:
        """Return a user-facing German status label."""

        return STATUS_LABELS.get(self.status, self.status)

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "action": self.action,
            "command": self.command,
            "command_text": self.command_text,
            "status": self.status,
            "status_label": self.status_label,
            "exit_code": self.exit_code,
            "output": self.output,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
            "created_at": self.created_at,
            "running": self.status in {"queued", "running"},
        }


_jobs: dict[str, ServiceJob] = {}
_lock = threading.Lock()
_loaded_db_path: Path | None = None
_last_persist_monotonic = 0.0


def start_service_job(action: str, command: list[str], cwd: Path) -> ServiceJob:
    """Start a service script in the background and return its job record."""

    job = ServiceJob(
        job_id=uuid.uuid4().hex[:12],
        action=action,
        command=command,
        created_at=_storage_now(),
    )
    with _lock:
        _ensure_loaded_locked()
        _jobs[job.job_id] = job
        _prune_jobs_locked()
        _persist_snapshot_locked()
    thread = threading.Thread(target=_run_job, args=(job.job_id, cwd), daemon=True)
    thread.start()
    return job


def get_service_job(job_id: str) -> ServiceJob | None:
    with _lock:
        _ensure_loaded_locked()
        return _jobs.get(job_id)


def list_service_jobs(limit: int = 20) -> list[ServiceJob]:
    with _lock:
        _ensure_loaded_locked()
        jobs = list(_jobs.values())
    return list(reversed(jobs[-limit:]))


def active_service_jobs() -> list[ServiceJob]:
    with _lock:
        _ensure_loaded_locked()
        return [job for job in _jobs.values() if job.status in {"queued", "running"}]


def _run_job(job_id: str, cwd: Path) -> None:
    job = get_service_job(job_id)
    if job is None:
        return
    _update_job(job_id, status="running", started_at=_now())
    try:
        process = subprocess.Popen(
            job.command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        message = f"Service konnte nicht gestartet werden: {exc}"
        _update_job(
            job_id,
            status="error",
            output=message,
            summary=message,
            finished_at=_now(),
        )
        return

    lines: deque[str] = deque(maxlen=MAX_OUTPUT_LINES)
    assert process.stdout is not None
    for line in process.stdout:
        stripped = line.rstrip()
        lines.append(stripped)
        _update_job(job_id, output="\n".join(lines), summary=stripped)
    process.wait()
    _update_job(
        job_id,
        status="ok" if process.returncode == 0 else "error",
        exit_code=int(process.returncode or 0),
        output="\n".join(lines),
        finished_at=_now(),
    )


def _update_job(job_id: str, **updates: object) -> None:
    global _last_persist_monotonic

    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        for key, value in updates.items():
            setattr(job, key, value)
        if job.status not in {"queued", "running"}:
            _prune_jobs_locked()
        now = time.monotonic()
        if job.status not in {"queued", "running"} or now - _last_persist_monotonic >= 0.5:
            _persist_snapshot_locked()
            _last_persist_monotonic = now


def _prune_jobs_locked() -> None:
    terminal_jobs = [
        job_id
        for job_id, job in _jobs.items()
        if job.status not in {"queued", "running"}
    ]
    while len(_jobs) > MAX_RETAINED_JOBS and terminal_jobs:
        job_id = terminal_jobs.pop(0)
        _jobs.pop(job_id, None)


def _ensure_loaded_locked() -> None:
    global _loaded_db_path

    db_path = Path(SERVICE_JOBS_DB)
    if _loaded_db_path == db_path:
        return
    _jobs.clear()
    try:
        _initialize_db(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM service_jobs ORDER BY created_at ASC, rowid ASC"
            ).fetchall()
        for row in rows:
            job = _job_from_row(row)
            if job.status in {"queued", "running"}:
                job.status = "error"
                job.finished_at = _now()
                job.summary = "Datenjob wurde durch einen Serverneustart unterbrochen."
            _jobs[job.job_id] = job
        _prune_jobs_locked()
        _loaded_db_path = db_path
        _persist_snapshot_locked()
    except (OSError, sqlite3.Error, ValueError, TypeError):
        # Job execution remains available in memory if persistence is unavailable.
        _loaded_db_path = db_path


def _initialize_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_jobs (
                job_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                command_json TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER,
                output TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _persist_snapshot_locked() -> None:
    if _loaded_db_path is None:
        return
    try:
        _initialize_db(_loaded_db_path)
        with sqlite3.connect(_loaded_db_path) as conn:
            conn.execute("DELETE FROM service_jobs")
            conn.executemany(
                """
                INSERT INTO service_jobs
                    (job_id, action, command_json, status, exit_code, output,
                     started_at, finished_at, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job.job_id,
                        job.action,
                        json.dumps(job.command, ensure_ascii=False),
                        job.status,
                        job.exit_code,
                        job.output,
                        job.started_at,
                        job.finished_at,
                        job.summary,
                        job.created_at or job.started_at or _now(),
                    )
                    for job in _jobs.values()
                ],
            )
    except (OSError, sqlite3.Error):
        pass


def _job_from_row(row: sqlite3.Row) -> ServiceJob:
    command = json.loads(str(row["command_json"] or "[]"))
    if not isinstance(command, list):
        command = []
    return ServiceJob(
        job_id=str(row["job_id"]),
        action=str(row["action"]),
        command=[str(part) for part in command],
        status=str(row["status"]),
        exit_code=row["exit_code"],
        output=str(row["output"] or ""),
        started_at=str(row["started_at"] or ""),
        finished_at=str(row["finished_at"] or ""),
        summary=str(row["summary"] or ""),
        created_at=str(row["created_at"] or ""),
    )


def _now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def _storage_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
