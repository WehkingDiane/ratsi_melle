"""Server-bound, read-only legacy inspection commands and audit projections."""

from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4

from django.core import signing

from src.indexing.legacy_index_inspection import target_sha256
from src.indexing.legacy_inspection_report import read_inspection_report
from src.model_operations import model_preparation_binding
from src.qdrant_connection import QdrantConnection
from . import paths

COLLECTIONS = ("ratsi_passages", "ratsi_documents")
SALT = "data-tools-legacy-inspection"


def inspection_context(collection: str) -> dict:
    """Capture configuration without storing the credential-bearing server URL."""
    if collection not in COLLECTIONS:
        raise ValueError("Nur die beiden Melle-Collections können geprüft werden.")
    connection = QdrantConnection.from_env(paths.QDRANT_DIR)
    return {
        "collection": collection,
        "target": connection.target,
        "target_sha256": target_sha256(connection),
        "qdrant_dir": str(paths.QDRANT_DIR.resolve()),
        "source_db": str(paths.LOCAL_INDEX_DB.resolve()) if collection == "ratsi_documents" else None,
        "report_root": str((paths.PRIVATE_DATA_DIR / "legacy_inspections").resolve()),
        "model_binding": model_preparation_binding(),
    }


def inspection_forms() -> list[dict]:
    forms = []
    for collection in COLLECTIONS:
        context = inspection_context(collection)
        forms.append({**context, "binding": signing.dumps(context, salt=SALT)})
    return forms


def confirmed_inspection_context(data) -> dict:
    try:
        expected = signing.loads(str(data.get("inspection_binding") or ""), salt=SALT, max_age=900)
        actual = inspection_context(data.get("collection"))
    except (signing.BadSignature, OSError, RuntimeError, ValueError):
        raise ValueError("Prüfziel ist ungültig oder abgelaufen. Seite neu laden und erneut prüfen.") from None
    if expected != actual:
        raise ValueError("Prüfkonfiguration wurde geändert. Seite neu laden und erneut prüfen.")
    return actual


def inspection_command(context: dict, job_id: str | None = None) -> list[str]:
    """Use a private, unique report path; no report path comes from POST."""
    identifier = job_id or uuid4().hex
    command = [sys.executable, "scripts/migrate_legacy_index.py", "--inspect",
               "--collection", context["collection"], "--qdrant-dir", context["qdrant_dir"],
               "--report", str(Path(context["report_root"]) / f"{identifier}.json")]
    if context["source_db"] is not None:
        command.extend(["--source-db", context["source_db"]])
    return command


def bound_report(job) -> dict:
    """Read the job's own report and check target, source, format and digest."""
    context = json.loads(job.inspection_context)
    path = Path(context["report_root"]) / f"{job.job_id}.json"
    if path.resolve().parent != Path(context["report_root"]):
        raise ValueError("Prüfprotokoll ist ungültig.")
    report, content = read_inspection_report(path)
    if any(report[key] != context[key] for key in ("collection", "target", "target_sha256", "source_db")):
        raise ValueError("Prüfprotokoll gehört zu einem anderen Ziel.")
    digest = sha256(content).hexdigest()
    if job.report_sha256 and digest != job.report_sha256:
        raise ValueError("Prüfprotokoll wurde nach Abschluss verändert.")
    return {**report, "report_sha256": digest}


def inspection_result(job) -> dict | None:
    """Project validated historical evidence without exposing provider output."""
    if job is None or getattr(job, "action", None) != "inspect_legacy_index":
        return None
    if job.status in {"queued", "running"}:
        return {"pending": True}
    try:
        if not job.report_sha256:
            raise ValueError("Kein geprüftes Protokoll.")
        report = bound_report(job)
        context = json.loads(job.inspection_context)
        try:
            historical = context != inspection_context(context["collection"])
        except (OSError, RuntimeError, ValueError):
            historical = True
        return {key: report[key] for key in (
            "collection", "target", "source_db", "checked_at", "result", "abort_code",
            "point_count", "sample_count", "sample_limit", "report_sha256",
        )} | {"historical": historical, "pending": False}
    except (OSError, ValueError, TypeError, KeyError):
        return {"invalid": True, "pending": False}


APPLY_SALT = "data-tools-legacy-apply"


def application_payload(job) -> dict:
    """Require a successful retained job, unchanged report and active contract."""
    from src.config.index_compatibility import current_index_compatibility
    from src.indexing.legacy_index_migration import _check_marker_unreleased

    if (job is None or job.action != "inspect_legacy_index" or job.status != "ok"
            or job.exit_code != 0 or not job.report_sha256):
        raise ValueError("Nur ein erfolgreich abgeschlossener Prüfjob kann übernommen werden.")
    try:
        context = json.loads(job.inspection_context)
        if context != inspection_context(context["collection"]):
            raise ValueError("Configuration changed")
        _check_marker_unreleased(QdrantConnection.from_env(Path(context["qdrant_dir"])), context["collection"])
        report = bound_report(job)
        if report["result"] != "verified" or report["compatibility"] != current_index_compatibility().as_dict():
            raise ValueError("Active model contract changed")
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        raise ValueError("Prüfergebnis ist nicht mehr aktuell. Bestand erneut prüfen.") from None
    return {"inspection_job_id": job.job_id, "inspection_context": context, "report_sha256": job.report_sha256}


def application_confirmation(job) -> str | None:
    """Issue a short-lived consent token only for eligible inspection evidence."""
    try:
        return signing.dumps(application_payload(job), salt=APPLY_SALT)
    except ValueError:
        return None


def confirmed_application_payload(data) -> dict:
    """Resolve evidence by job identity, never by a POST-supplied report path."""
    from core import service_jobs

    if data.get("confirmation") != "apply":
        raise ValueError("Bitte die Übernahme ausdrücklich bestätigen.")
    try:
        expected = signing.loads(str(data.get("apply_binding") or ""), salt=APPLY_SALT, max_age=900)
        actual = application_payload(service_jobs.get_service_job(data.get("inspection_job_id", "")))
    except (signing.BadSignature, OSError, RuntimeError, ValueError, TypeError):
        raise ValueError("Übernahmebestätigung ist ungültig oder veraltet. Bestand erneut prüfen.") from None
    if expected != actual:
        raise ValueError("Prüfprotokoll wurde geändert. Bestand erneut prüfen und bestätigen.")
    return actual


def application_command(payload: dict) -> list[str]:
    context = payload["inspection_context"]
    command = inspection_command(context, payload["inspection_job_id"])
    command[command.index("--inspect")] = "--apply"
    return command + ["--confirm-collection", context["collection"]]
