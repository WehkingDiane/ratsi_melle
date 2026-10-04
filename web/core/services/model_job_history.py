"""Bound model job history projected independently of current readiness."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3

from src.model_operations import model_preparation_binding

SCOPES = (
    ("check_embedding_models", None, "Lokale Modellprüfung"),
    ("prepare_embedding_models", None, "Modellvorbereitung"),
    ("inspect_legacy_index", "ratsi_passages", "Legacy-Prüfung: ratsi_passages"),
    ("inspect_legacy_index", "ratsi_documents", "Legacy-Prüfung: ratsi_documents"),
    ("apply_legacy_index", "ratsi_passages", "Legacy-Übernahme: ratsi_passages"),
    ("apply_legacy_index", "ratsi_documents", "Legacy-Übernahme: ratsi_documents"),
)


def _context(job):
    try:
        context = json.loads(job.inspection_context or "{}")
        return context if isinstance(context, dict) else {}
    except (ValueError, TypeError):
        return {}


def _result(job):
    """Expose whitelisted outcome words, never arbitrary old job messages."""
    try:
        value = json.loads(job.output.splitlines()[-1])
        if not isinstance(value, dict):
            return None
        result = value.get("status", value.get("result"))
        if job.status != "ok" and result in ("bereit", "verified", "released"):
            return "fehlgeschlagen" if job.status == "error" else None
        return result if isinstance(result, str) and result in {
            "bereit", "fehlt", "unvollstaendig", "inkompatibel", "fehlgeschlagen", "verified", "aborted", "released",
        } else None
    except (ValueError, TypeError, IndexError):
        return None


def job_evidence(job, models, binding=None):
    """Associate one result with its original path, model contract and snapshot."""
    context = _context(job)
    identity = job.model_binding or job.preparation_binding or context.get("model_binding")
    association = "unknown"
    if identity and job.models_dir:
        try:
            same_path = models.get("models_dir") and Path(job.models_dir).resolve() == Path(models["models_dir"]).resolve()
        except (OSError, RuntimeError):
            same_path = False
        association = "current" if binding and identity == binding and same_path else "historical"
    manifest = job.model_manifest_sha256 or None
    if job.action in {"inspect_legacy_index", "apply_legacy_index"}:
        from .legacy_inspection import inspection_context, bound_report
        try:
            if context != inspection_context(context.get("collection")):
                association = "historical"
            if job.action == "inspect_legacy_index" and job.status not in {"queued", "running"} and job.report_sha256:
                report = bound_report(job)
                if report["result"] == "verified":
                    manifest = report["compatibility"]["manifest_sha256"]
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            association = "unknown"
    if manifest and (models.get("status") != "bereit" or manifest != models.get("manifest_sha256")):
        association = "historical"
    elif job.status == "ok" and not manifest:
        association = "unknown"
    state = {"current": "Zum aktuellen Bestand zugeordnet", "historical": "Historisches Ergebnis",
             "unknown": "Zuordnung nicht nachgewiesen"}[association]
    return {"job_id": job.job_id, "action": job.action, "status": job.status,
            "status_label": job.status_label, "finished_at": job.finished_at or None,
            "completed_at": job.completed_at or None, "started_at": job.started_at or None,
            "models_dir": job.models_dir or None, "manifest_sha256": manifest,
            "collection": context.get("collection"), "target": context.get("target"),
            "result": _result(job), "association": association, "association_label": state,
            "historical": association != "current", "progress": job.progress}


def _completed_order(job):
    for value, local_format in ((job.completed_at, False), (job.finished_at, True), (job.created_at, False)):
        if not value:
            continue
        try:
            timestamp = datetime.strptime(value, "%d.%m.%Y %H:%M:%S").astimezone() if local_format else datetime.fromisoformat(value)
            if timestamp.tzinfo is not None:
                return timestamp.timestamp()
        except (ValueError, TypeError):
            continue
    return float("-inf")


def current_binding():
    try:
        return model_preparation_binding()
    except (OSError, RuntimeError, ValueError):
        return None


def model_job_history(models):
    """Choose the latest completed attempt, including failure, for each action."""
    from core import service_jobs
    try:
        jobs = service_jobs.list_service_jobs(limit=service_jobs.MAX_RETAINED_JOBS)
    except (OSError, sqlite3.Error):
        return {"available": False, "message": "Prüfhistorie kann nicht gelesen werden.",
                "entries": [{"scope": action + (":" + collection if collection else ""),
                             "label": label, "last_finished": None, "active": []}
                            for action, collection, label in SCOPES]}
    binding = current_binding()
    entries = []
    for action, collection, label in SCOPES:
        matching = [job for job in jobs if job.action == action and (collection is None or _context(job).get("collection") == collection)]
        finished = [job for job in matching if job.status not in {"queued", "running"}]
        latest = max(finished, key=_completed_order) if finished else None
        entries.append({"scope": action + (":" + collection if collection else ""), "label": label,
                        "last_finished": job_evidence(latest, models, binding) if latest else None,
                        "active": [job_evidence(job, models, binding) for job in matching if job.status in {"queued", "running"}]})
    return {"available": True, "message": None, "entries": entries}


def model_job_detail(job, models):
    if job is None or getattr(job, "action", None) not in {scope[0] for scope in SCOPES}:
        return None
    return job_evidence(job, models, current_binding())
