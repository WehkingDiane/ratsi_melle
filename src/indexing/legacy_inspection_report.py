"""Persist a bounded audit record for the read-only legacy inspection."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import grpc
import httpx
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from src.indexing.legacy_index_inspection import (
    DENSE_ABS_TOLERANCE,
    DENSE_REL_TOLERANCE,
    SAMPLE_SIZE,
    SPARSE_ABS_TOLERANCE,
    SPARSE_REL_TOLERANCE,
    LegacyInspectionError,
    inspect_legacy_collection,
    target_sha256,
)
from src.paths import LOCAL_INDEX_DB
from src.qdrant_connection import QdrantConnection


REPORT_VERSION = 2


def report_tolerances() -> dict:
    """Return the fixed numerical comparison contract of a legacy inspection."""

    return {
        "dense_abs": DENSE_ABS_TOLERANCE,
        "dense_rel": DENSE_REL_TOLERANCE,
        "sparse_abs": SPARSE_ABS_TOLERANCE,
        "sparse_rel": SPARSE_REL_TOLERANCE,
        "sparse_indices": "exact",
    }


def inspect_and_write_report(
    connection: QdrantConnection, client, collection: str, report_path: Path, *,
    abort_code: str | None = None, **inspection_options,
) -> dict:
    """Inspect without Qdrant writes and atomically save success or a known abort reason.

    The report is evidence for a later confirmation, never an automatic release.
    ``inspection_options`` passes source paths and the vectorizer factory through
    to ``inspect_legacy_collection``.
    """

    report = {
        "report_version": REPORT_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "target": connection.target,
        "target_sha256": target_sha256(connection),
        "collection": collection,
        "source_db": (str(Path(inspection_options.get("ratsinfo_db", LOCAL_INDEX_DB)).resolve())
                      if collection == "ratsi_documents" else None),
        "point_count": None,
        "point_ids_sha256": None,
        "sample_limit": SAMPLE_SIZE,
        "sample_count": 0,
        "sample_ids": [],
        "tolerances": report_tolerances(),
        "compatibility": None,
        "result": "aborted",
        "abort_code": None,
    }
    if collection == "landkreis_publications":
        report["abort_code"] = "rebuild_required"
    elif abort_code is not None:
        report["abort_code"] = abort_code
    else:
        try:
            inspection = inspect_legacy_collection(connection, client, collection, **inspection_options)
        except LegacyInspectionError as error:
            report["abort_code"] = error.code
        except (ResponseHandlingException, httpx.TransportError, grpc.RpcError, OSError):
            report["abort_code"] = "qdrant_unavailable"
        except UnexpectedResponse as error:
            if error.status_code is None or error.status_code < 500:
                raise
            report["abort_code"] = "qdrant_unavailable"
        else:
            report.update(
                point_count=inspection.point_count,
                point_ids_sha256=inspection.point_ids_sha256,
                sample_count=len(inspection.sample_ids),
                sample_ids=list(inspection.sample_ids),
                compatibility=inspection.compatibility.as_dict(),
                result="verified",
            )

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return report


ABORT_CODES = frozenset({
    "rebuild_required", "store_missing", "qdrant_unavailable", "collection_changed",
    "collection_empty", "collection_missing", "contract_invalid", "contract_mismatch",
    "dense_mismatch", "marker_collection_mismatch", "marker_count_mismatch",
    "marker_invalid", "marker_target_mismatch", "model_mismatch", "model_unavailable",
    "payload_missing", "pipeline_mismatch", "point_count_mismatch", "point_ids_invalid",
    "sample_incomplete", "schema_mismatch", "scroll_incomplete", "source_ambiguous",
    "source_missing", "sparse_indices_mismatch", "sparse_values_mismatch",
    "text_mismatch", "text_unavailable", "vector_invalid",
})


def validate_inspection_report_envelope(report: object) -> dict:
    """Validate the common report format, timestamp and comparison contract."""
    if not isinstance(report, dict) or type(report.get("report_version")) is not int or report["report_version"] != REPORT_VERSION:
        raise ValueError("Prüfprotokoll hat ein unbekanntes Format.")
    try:
        checked = datetime.fromisoformat(report["checked_at"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Prüfzeitpunkt ist ungültig.") from None
    if checked.tzinfo is None or checked.utcoffset() is None:
        raise ValueError("Prüfzeitpunkt muss eine Zeitzone enthalten.")
    if report.get("sample_limit") != SAMPLE_SIZE or report.get("tolerances") != report_tolerances():
        raise ValueError("Prüfprotokoll hat andere Stichproben- oder Vergleichsregeln.")
    return report


def validate_inspection_report(report: object) -> dict:
    """Validate both verified evidence and bounded, known abort reports."""
    from src.config.index_compatibility import IndexCompatibility

    report = validate_inspection_report_envelope(report)
    if report.get("collection") not in {"ratsi_passages", "ratsi_documents", "landkreis_publications"}:
        raise ValueError("Prüfcollection ist ungültig.")
    def digest(value):
        return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    if not isinstance(report.get("target"), str) or not digest(report.get("target_sha256")):
        raise ValueError("Prüfziel ist ungültig.")
    source = report.get("source_db")
    if (report["collection"] == "ratsi_documents" and not isinstance(source, str)) or (report["collection"] != "ratsi_documents" and source is not None):
        raise ValueError("Prüfquelle ist ungültig.")
    if report.get("result") == "aborted":
        if report.get("abort_code") not in ABORT_CODES:
            raise ValueError("Abbruchgrund ist ungültig.")
        if any(report.get(key) is not None for key in ("point_count", "point_ids_sha256", "compatibility")) or report.get("sample_count") != 0 or report.get("sample_ids") != []:
            raise ValueError("Abbruchprotokoll enthält widersprüchliche Ergebnisse.")
    elif report.get("result") == "verified":
        ids = report.get("sample_ids")
        count = report.get("point_count")
        samples = report.get("sample_count")
        if (report.get("abort_code") is not None or type(count) is not int or count < 1
                or not digest(report.get("point_ids_sha256")) or not isinstance(ids, list)
                or type(samples) is not int or samples != min(count, SAMPLE_SIZE)
                or len(ids) != samples or any(type(item) is not int for item in ids) or len(set(ids)) != samples):
            raise ValueError("Erfolgsprotokoll ist unvollständig.")
        IndexCompatibility.from_dict(report.get("compatibility"))
        if report["collection"] == "landkreis_publications":
            raise ValueError("Landkreis benötigt einen Neuaufbau.")
    else:
        raise ValueError("Prüfergebnis ist ungültig.")
    return report


def read_inspection_report(path: Path) -> tuple[dict, bytes]:
    """Read one bounded, non-symlink audit snapshot for display and release."""
    if path.is_symlink():
        raise ValueError("Prüfprotokoll darf kein Symlink sein.")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        content = stream.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise ValueError("Prüfprotokoll ist zu groß.")
    return validate_inspection_report(json.loads(content)), content
