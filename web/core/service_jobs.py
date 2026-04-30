"""In-process background jobs for service script execution."""

from __future__ import annotations

import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


MAX_OUTPUT_LINES = 500


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

    @property
    def command_text(self) -> str:
        return " ".join(self.command)

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "action": self.action,
            "command": self.command,
            "command_text": self.command_text,
            "status": self.status,
            "exit_code": self.exit_code,
            "output": self.output,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
            "running": self.status in {"queued", "running"},
        }


_jobs: dict[str, ServiceJob] = {}
_lock = threading.Lock()


def start_service_job(action: str, command: list[str], cwd: Path) -> ServiceJob:
    """Start a service script in the background and return its job record."""

    job = ServiceJob(job_id=uuid.uuid4().hex[:12], action=action, command=command)
    with _lock:
        _jobs[job.job_id] = job
    thread = threading.Thread(target=_run_job, args=(job.job_id, cwd), daemon=True)
    thread.start()
    return job


def get_service_job(job_id: str) -> ServiceJob | None:
    with _lock:
        return _jobs.get(job_id)


def list_service_jobs(limit: int = 20) -> list[ServiceJob]:
    with _lock:
        jobs = list(_jobs.values())
    return list(reversed(jobs[-limit:]))


def active_service_jobs() -> list[ServiceJob]:
    with _lock:
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
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        for key, value in updates.items():
            setattr(job, key, value)


def _now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")
