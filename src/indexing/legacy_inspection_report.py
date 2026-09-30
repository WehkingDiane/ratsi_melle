"""Persist a bounded audit record for the read-only legacy inspection."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

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
from src.qdrant_connection import QdrantConnection


REPORT_VERSION = 1


def inspect_and_write_report(
    connection: QdrantConnection, client, collection: str, report_path: Path, **inspection_options,
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
        "point_count": None,
        "point_ids_sha256": None,
        "sample_limit": SAMPLE_SIZE,
        "sample_count": 0,
        "sample_ids": [],
        "tolerances": {
            "dense_abs": DENSE_ABS_TOLERANCE,
            "dense_rel": DENSE_REL_TOLERANCE,
            "sparse_abs": SPARSE_ABS_TOLERANCE,
            "sparse_rel": SPARSE_REL_TOLERANCE,
            "sparse_indices": "exact",
        },
        "compatibility": None,
        "result": "aborted",
        "abort_code": None,
    }
    try:
        inspection = inspect_legacy_collection(connection, client, collection, **inspection_options)
    except LegacyInspectionError as error:
        report["abort_code"] = error.code
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
