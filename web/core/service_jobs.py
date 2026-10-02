"""Persistent background jobs for service script execution."""

from __future__ import annotations

import json
import logging
import os
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

from src.observability import RUN_ID_ENV

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
LOGGER = logging.getLogger(__name__)


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
    owner_pid: int = 0
    child_pid: int = 0
    models_dir: str = ""
    preparation_binding: str = ""
    inspection_context: str = ""
    report_sha256: str = ""
    application_context: str = ""
    model_binding: str = ""
    model_manifest_sha256: str = ""
    completed_at: str = ""

    @property
    def progress(self) -> dict[str, object]:
        """Report real lifecycle states without inventing a percentage."""
        active = self.status in {"queued", "running"}
        return {"phase": self.status, "indeterminate": active,
                "message": "Wartet auf Ausführung." if self.status == "queued" else
                "Wird ausgeführt; ein Prozentfortschritt ist nicht verfügbar." if active else
                "Erfolgreich abgeschlossen." if self.status == "ok" else "Fehlgeschlagen oder unterbrochen."}

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
            "progress": self.progress,
        }


_jobs: dict[str, ServiceJob] = {}
_lock = threading.Lock()
_loaded_db_path: Path | None = None
_last_persist_monotonic = 0.0
_dirty_ids: set[str] = set()
_seen_ids: set[str] = set()
MODEL_ACTIONS = {"prepare_embedding_models", "build_vector_index", "build_landkreis_vector_index", "inspect_legacy_index", "apply_legacy_index"}


class ServiceJobStartError(ValueError):
    """A job cannot safely be persisted or reserved before starting."""


def start_service_job(action: str, command: list[str], cwd: Path, *, preparation_binding: str | None = None,
                      inspection_context: dict | None = None, application_context: dict | None = None) -> ServiceJob:
    """Atomically reserve colliding web actions before creating their worker."""

    from src.model_operations import model_operation_lock, model_preparation_binding
    from src.config.settings import load_embedding_model_settings

    job = ServiceJob(job_id=uuid.uuid4().hex[:12], action=action, command=command,
                     created_at=_storage_now(), owner_pid=os.getpid())
    try:
        if action == "check_embedding_models":
            try:
                root = load_embedding_model_settings().models_dir.resolve()
                job.models_dir = str(root)
                job.model_binding = model_preparation_binding(root)
            except (OSError, RuntimeError, ValueError):
                # An invalid configuration must still produce an offline CLI
                # diagnostic, but its history cannot claim a known identity.
                pass
        if action in MODEL_ACTIONS:
            root = load_embedding_model_settings().models_dir.resolve()
            # This preflight rejects an already running direct CLI operation.
            # The child acquires the same lock for its entire actual operation.
            with model_operation_lock(root, blocking=False):
                job.models_dir = str(root)
                job.model_binding = model_preparation_binding(root)
                if action == "prepare_embedding_models":
                    if preparation_binding != model_preparation_binding(root):
                        raise ServiceJobStartError("Modellkonfiguration wurde geändert. Vorbereitung erneut bestätigen.")
                    job.preparation_binding = preparation_binding
                if action == "inspect_legacy_index":
                    from .services.legacy_inspection import inspection_context as current_context, inspection_command
                    if not isinstance(inspection_context, dict) or inspection_context != current_context(inspection_context.get("collection")):
                        raise ServiceJobStartError("Prüfkonfiguration wurde geändert. Seite neu laden.")
                    job.inspection_context = json.dumps(inspection_context, sort_keys=True)
                    job.command = inspection_command(inspection_context, job.job_id)
                if action == "apply_legacy_index" and not isinstance(application_context, dict):
                    raise ServiceJobStartError("Übernahme benötigt einen bestätigten Prüfjob.")
        with _lock:
            _ensure_loaded_locked()
            with sqlite3.connect(SERVICE_JOBS_DB) as conn:
                conn.execute("BEGIN IMMEDIATE")
                if action == "apply_legacy_index":
                    from .services.legacy_inspection import application_payload, application_command
                    conn.row_factory = sqlite3.Row
                    source = conn.execute("SELECT * FROM service_jobs WHERE job_id=?", (application_context["inspection_job_id"],)).fetchone()
                    if application_context != application_payload(_job_from_row(source) if source is not None else None):
                        raise ServiceJobStartError("Bestätigtes Prüfergebnis wurde geändert.")
                    job.application_context = json.dumps(application_context, sort_keys=True)
                    job.inspection_context = json.dumps(application_context["inspection_context"], sort_keys=True)
                    job.report_sha256 = application_context["report_sha256"]
                    from .services.legacy_inspection import bound_report
                    job.model_manifest_sha256 = bound_report(_job_from_row(source))["compatibility"]["manifest_sha256"]
                    job.command = application_command(application_context)
                if action in MODEL_ACTIONS:
                    placeholders = ",".join("?" for _ in MODEL_ACTIONS)
                    active = conn.execute(
                        f"SELECT job_id FROM service_jobs WHERE status IN ('queued', 'running') AND action IN ({placeholders})",
                        tuple(MODEL_ACTIONS),
                    ).fetchone()
                    if active:
                        raise ServiceJobStartError("Modellvorbereitung oder Indexjob ist bereits aktiv.")
                _store_job(conn, job)
                _prune_database(conn)
            _jobs[job.job_id] = job
    except ServiceJobStartError:
        raise
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, sqlite3.Error):
        raise ServiceJobStartError("Datenjob kann nicht sicher gestartet werden. Modell- und Jobablage prüfen; möglicherweise ist ein Indexjob aktiv.") from None
    try:
        thread = threading.Thread(target=_run_job, args=(job.job_id, cwd), daemon=True)
        thread.start()
    except Exception:
        _update_job(job.job_id, status="error", summary="Datenjob konnte nicht gestartet werden.", finished_at=_now())
        raise ServiceJobStartError("Datenjob konnte nicht gestartet werden.") from None
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
    try:
        _execute_job(job_id, cwd)
    except Exception:
        LOGGER.error("event=service_job_failed phase=worker", extra={"run_id": job_id})
        try:
            _update_job(job_id, status="error", output="Datenjob abgebrochen. Jobablage prüfen.",
                        summary="Datenjob abgebrochen. Jobablage prüfen.", finished_at=_now())
        except (OSError, sqlite3.Error):
            pass


def _safe_preparation_output(line: str) -> str | None:
    """Accept only fixed diagnostic codes and a validated manifest digest."""
    try:
        payload = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("operation") != "download":
        return None
    if payload.get("status") == "bereit":
        digest = payload.get("manifest_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return None
        return json.dumps({"operation": "download", "status": "bereit", "manifest_sha256": digest,
                           "message": "Lokale Embedding-Modelle sind geprueft und freigegeben."}, ensure_ascii=False)
    codes = {
        "disk_full": "Nicht genug lokaler Speicherplatz.",
        "permission_denied": "Verzeichnisrechte prüfen.",
        "network_unavailable": "Modellquelle nicht erreichbar.",
        "source_unavailable": "Modellquelle lehnt die Anfrage ab.",
        "dependency_missing": "Modellbibliotheken fehlen.",
        "incomplete_artifacts": "Modellartefakte sind unvollständig oder ungültig.",
        "download_failed": "Modelldownload fehlgeschlagen.",
        "preparation_failed": "Modellvorbereitung fehlgeschlagen.",
        "configuration_error": "Modellkonfiguration ist ungültig.",
        "confirmation_changed": "Modellkonfiguration wurde geändert. Vorbereitung erneut bestätigen.",
    }
    code = payload.get("error_code")
    if payload.get("status") != "fehlgeschlagen" or not isinstance(code, str) or code not in codes:
        return None
    return json.dumps({"operation": "download", "status": "fehlgeschlagen", "error_code": code,
                       "message": codes[code]}, ensure_ascii=False)


def _safe_legacy_apply_output(line: str, collection: str) -> str | None:
    """Keep only fixed outcome codes and bounded counts from a release process."""
    from src.indexing.legacy_inspection_report import ABORT_CODES

    try:
        payload = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    codes = ABORT_CODES | {"configuration_changed", "already_released", "backfill_incomplete",
                         "confirmation_required", "provenance_mismatch", "release_failed", "report_changed",
                         "report_invalid", "report_not_verified", "report_stale", "report_target_mismatch",
                         "rollback_incomplete", "source_mismatch"}
    if payload.get("result") == "aborted" and isinstance(payload.get("abort_code"), str) and payload["abort_code"] in codes:
        return json.dumps({"result": "aborted", "abort_code": payload["abort_code"]})
    count, backfilled = payload.get("point_count"), payload.get("backfilled_points")
    if (payload.get("collection") == collection and payload.get("provenance") == "legacy_verified"
            and type(count) is int and count > 0 and type(backfilled) is int and 0 <= backfilled <= count):
        return json.dumps({"result": "released", "collection": collection, "provenance": "legacy_verified",
                           "point_count": count, "backfilled_points": backfilled})
    return None


def _safe_model_check_output(line: str) -> str | None:
    try:
        payload = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    messages = {"bereit": "Lokale Embedding-Modelle sind bereit.", "fehlt": "Lokale Embedding-Modelle fehlen.",
                "unvollstaendig": "Lokale Embedding-Modelle sind unvollständig.",
                "inkompatibel": "Lokale Embedding-Modelle oder die Konfiguration sind inkompatibel."}
    state = payload.get("status")
    if not isinstance(state, str) or state not in messages or not isinstance(payload.get("check_level"), str) or payload["check_level"] not in {"fast", "deep"}:
        return None
    digest = payload.get("manifest_sha256")
    if state == "bereit" and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
        return None
    return json.dumps({"status": state, "check_level": payload["check_level"], "message": messages[state],
                       "manifest_sha256": digest if state == "bereit" else None}, ensure_ascii=False)


def _execute_job(job_id: str, cwd: Path) -> None:
    job = get_service_job(job_id)
    if job is None:
        return
    _update_job(job_id, status="running", started_at=_now())
    LOGGER.info(
        "event=service_job_started action=%s",
        job.action,
        extra={"run_id": job_id},
    )
    preparation_output = job.action == "prepare_embedding_models"
    check_output = job.action == "check_embedding_models"
    legacy_output = job.action == "inspect_legacy_index"
    application_output = job.action == "apply_legacy_index"
    private_output = preparation_output or legacy_output or application_output or check_output
    environment = {**os.environ, RUN_ID_ENV: job.job_id}
    if job.models_dir:
        environment["RATSI_MODELS_DIR"] = job.models_dir
    environment.pop("RATSI_MODEL_CHECK_BINDING", None)
    if check_output and job.model_binding:
        environment["RATSI_MODEL_CHECK_BINDING"] = job.model_binding
    if preparation_output:
        environment["RATSI_MODEL_PREPARATION_BINDING"] = job.preparation_binding
    else:
        environment.pop("RATSI_MODEL_PREPARATION_BINDING", None)
    environment.pop("RATSI_LEGACY_INSPECTION_CONTEXT", None)
    if legacy_output:
        environment["RATSI_LEGACY_INSPECTION_CONTEXT"] = job.inspection_context
    environment.pop("RATSI_LEGACY_APPLY_CONTEXT", None)
    if application_output:
        environment["RATSI_LEGACY_APPLY_CONTEXT"] = job.application_context
    try:
        process = subprocess.Popen(
            job.command,
            cwd=str(cwd),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL if private_output else subprocess.STDOUT,
            text=True,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        message = "Service konnte nicht gestartet werden." if private_output else f"Service konnte nicht gestartet werden: {exc}"
        log_launch = LOGGER.error if private_output else LOGGER.exception
        log_launch(
            "event=service_job_failed action=%s phase=launch",
            job.action,
            extra={"run_id": job_id},
        )
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
    try:
        _update_job(job_id, child_pid=getattr(process, "pid", 0))
        for line in process.stdout:
            if application_output:
                stripped = _safe_legacy_apply_output(line, json.loads(job.inspection_context)["collection"])
            elif check_output:
                stripped = _safe_model_check_output(line)
            else:
                stripped = None if legacy_output else (_safe_preparation_output(line) if preparation_output else line.rstrip())
            if stripped is not None:
                lines.append(stripped)
                _update_job(job_id, output="\n".join(lines), summary=stripped)
        process.wait()
    except BaseException:
        process.terminate()
        process.wait()
        raise
    status = "ok" if process.returncode == 0 else "error"
    report_digest = ""
    manifest_digest = job.model_manifest_sha256
    if check_output:
        if not lines:
            lines.append("Modellprüfung beendet; kein auswertbarer Status verfügbar.")
            status = "error"
        elif json.loads(lines[-1])["status"] != "bereit":
            status = "error"
        elif status == "ok":
            manifest_digest = json.loads(lines[-1])["manifest_sha256"]
        else:
            lines.append("Modellprüfung abgebrochen; erfolgreicher Abschluss nicht bestätigt.")
    if application_output:
        report_digest = job.report_sha256
        if not lines:
            lines.append("Legacy-Übernahme abgebrochen; keine bestätigte Freigabe verfügbar.")
            status = "error"
        elif json.loads(lines[-1])["result"] != "released":
            status = "error"
        elif process.returncode != 0:
            lines.append("Legacy-Übernahme abgebrochen; erfolgreicher Abschluss nicht bestätigt.")
    if legacy_output:
        from .services.legacy_inspection import bound_report
        try:
            report = bound_report(job)
        except (OSError, ValueError, TypeError, KeyError):
            lines.append("Legacy-Prüfung ohne gültiges, zugeordnetes Protokoll beendet.")
            status = "error"
        else:
            report_digest = report["report_sha256"]
            if report["result"] == "verified":
                manifest_digest = report["compatibility"]["manifest_sha256"]
            status = "ok" if process.returncode == 0 and report["result"] == "verified" else "error"
            lines.append(json.dumps({"result": report["result"], "abort_code": report["abort_code"],
                                     "report_sha256": report_digest}))
    if preparation_output and (not lines or json.loads(lines[-1])["status"] != "bereit"):
        status = "error"
    if preparation_output and not lines:
        lines.append("Modellvorbereitung abgebrochen; kein verifizierbares Ergebnis verfügbar.")
    elif preparation_output and process.returncode != 0 and json.loads(lines[-1])["status"] == "bereit":
        lines.append("Modellvorbereitung abgebrochen; erfolgreicher Abschluss nicht bestätigt.")
    if preparation_output and status == "ok":
        manifest_digest = json.loads(lines[-1])["manifest_sha256"]
    _update_job(
        job_id,
        status=status,
        exit_code=int(process.returncode or 0),
        output="\n".join(lines),
        summary=lines[-1] if lines else job.summary,
        report_sha256=report_digest,
        model_manifest_sha256=manifest_digest,
        finished_at=_now(),
    )
    log_method = LOGGER.info if status == "ok" else LOGGER.error
    log_method(
        "event=service_job_completed action=%s status=%s exit_code=%d",
        job.action,
        status,
        int(process.returncode or 0),
        extra={"run_id": job_id},
    )


def _update_job(job_id: str, **updates: object) -> None:
    global _last_persist_monotonic

    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        if updates.get("status") in {"ok", "error"} and (job.status in {"queued", "running"} or not job.completed_at):
            updates.setdefault("completed_at", _storage_now())
        for key, value in updates.items():
            setattr(job, key, value)
        _dirty_ids.add(job_id)
        if job.status not in {"queued", "running"}:
            _prune_jobs_locked()
        now = time.monotonic()
        if "child_pid" in updates or job.status not in {"queued", "running"} or now - _last_persist_monotonic >= 0.5:
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


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows os.kill(pid, 0) is not a harmless existence probe.
        return _windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_pid_alive(pid: int) -> bool:
    """Query process state without sending a signal or terminating a process."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        # Invalid PID means absent; access denied and other unknown failures
        # conservatively keep the reservation instead of allowing concurrency.
        return ctypes.get_last_error() != 87
    try:
        code = wintypes.DWORD()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


def _ensure_loaded_locked() -> None:
    """Refresh from SQLite without overwriting another process's active jobs."""
    global _loaded_db_path

    db_path = Path(SERVICE_JOBS_DB)
    if _loaded_db_path != db_path:
        _jobs.clear()
        _dirty_ids.clear()
        _seen_ids.clear()
        _loaded_db_path = db_path
    _initialize_db(db_path)
    # Retry terminal updates after a transient storage failure before deciding
    # whether a persisted reservation still blocks another job.
    if _dirty_ids:
        _persist_snapshot_locked()
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM service_jobs ORDER BY created_at ASC, rowid ASC").fetchall()
        known = set()
        for row in rows:
            job = _job_from_row(row)
            known.add(job.job_id)
            _seen_ids.add(job.job_id)
            if job.job_id in _dirty_ids:
                continue
            if job.status in {"queued", "running"} and not _pid_alive(job.owner_pid) and not _pid_alive(job.child_pid):
                job.status = "error"
                job.finished_at = _now()
                job.completed_at = _storage_now()
                job.summary = "Datenjob wurde durch einen Serverneustart unterbrochen."
                _store_job(conn, job)
            existing = _jobs.get(job.job_id)
            if existing is not None:
                existing.__dict__.update(job.__dict__)
            else:
                _jobs[job.job_id] = job
        for job_id in set(_jobs) - known - _dirty_ids:
            _jobs.pop(job_id, None)
    _prune_jobs_locked()


def _initialize_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_jobs (
                job_id TEXT PRIMARY KEY, action TEXT NOT NULL, command_json TEXT NOT NULL,
                status TEXT NOT NULL, exit_code INTEGER, output TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT NOT NULL, summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(service_jobs)")}
        for name, sql_type, default in (
            ("owner_pid", "INTEGER", "0"), ("child_pid", "INTEGER", "0"),
            ("models_dir", "TEXT", "''"), ("preparation_binding", "TEXT", "''"),
            ("inspection_context", "TEXT", "''"), ("report_sha256", "TEXT", "''"),
            ("application_context", "TEXT", "''"),
            ("model_binding", "TEXT", "''"), ("model_manifest_sha256", "TEXT", "''"), ("completed_at", "TEXT", "''"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE service_jobs ADD COLUMN {name} {sql_type} NOT NULL DEFAULT {default}")


def _store_job(conn, job: ServiceJob) -> None:
    fields = ["job_id", "action", "command_json", "status", "exit_code", "output", "started_at",
              "finished_at", "summary", "created_at", "owner_pid", "child_pid", "models_dir", "preparation_binding",
              "inspection_context", "report_sha256", "application_context", "model_binding", "model_manifest_sha256", "completed_at"]
    values = [job.job_id, job.action, json.dumps(job.command), job.status, job.exit_code, job.output,
              job.started_at, job.finished_at, job.summary, job.created_at or _storage_now(),
              job.owner_pid, job.child_pid, job.models_dir, job.preparation_binding, job.inspection_context, job.report_sha256,
              job.application_context, job.model_binding, job.model_manifest_sha256, job.completed_at]
    conn.execute(
        f"INSERT INTO service_jobs ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)}) "
        "ON CONFLICT(job_id) DO UPDATE SET " + ','.join(f"{name}=excluded.{name}" for name in fields[1:]),
        values,
    )


def _prune_database(conn) -> None:
    count = conn.execute("SELECT COUNT(*) FROM service_jobs").fetchone()[0]
    if count > MAX_RETAINED_JOBS:
        conn.execute("DELETE FROM service_jobs WHERE job_id IN (SELECT job_id FROM service_jobs "
                     "WHERE status NOT IN ('queued','running') ORDER BY created_at ASC, rowid ASC LIMIT ?)",
                     (count - MAX_RETAINED_JOBS,))


def _persist_snapshot_locked() -> None:
    """Write only locally changed or new rows; never rewrite the entire table."""
    if _loaded_db_path is None:
        return
    _initialize_db(_loaded_db_path)
    with sqlite3.connect(_loaded_db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        known = {row[0] for row in conn.execute("SELECT job_id FROM service_jobs")}
        for job_id in _dirty_ids | (set(_jobs) - known - _seen_ids):
            if job_id in _jobs:
                _store_job(conn, _jobs[job_id])
        _prune_database(conn)
        _seen_ids.update(_jobs)
    _dirty_ids.clear()


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
        owner_pid=int(row["owner_pid"]), child_pid=int(row["child_pid"]),
        models_dir=str(row["models_dir"]), preparation_binding=str(row["preparation_binding"]),
        inspection_context=str(row["inspection_context"]), report_sha256=str(row["report_sha256"]),
        application_context=str(row["application_context"]),
        model_binding=str(row["model_binding"]), model_manifest_sha256=str(row["model_manifest_sha256"]),
        completed_at=str(row["completed_at"]),
    )


def _now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def _storage_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
