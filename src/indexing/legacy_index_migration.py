"""Explicitly release a verified legacy collection without changing vectors."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path

from src.config.index_compatibility import IndexCompatibility
from src.indexing.legacy_index_inspection import (
    SAMPLE_SIZE,
    LegacyInspectionError,
    _check_hints,
    _point_ids_sha256,
    inspect_legacy_collection,
    target_sha256,
)
from src.indexing.legacy_inspection_report import REPORT_VERSION, report_tolerances
from src.paths import LOCAL_INDEX_DB
from src.qdrant_connection import QdrantConnection
from src.model_operations import locked_model_operation


BACKFILL_SIZE = 256
PROVENANCE_KEY = "index_provenance"
LEGACY_PROVENANCE = "legacy_verified"


class LegacyMigrationError(ValueError):
    """The confirmed release cannot use this report or collection state."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@contextmanager
def _migration_lock(connection: QdrantConnection, collection: str):
    """Serialize releases for one target and collection across processes."""

    path = connection.release_path(collection).with_suffix(".migration.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the lock file: removing it could let a third process lock a new inode
    # while another process is still waiting on the old one.
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _read_report(path: Path) -> dict:
    if path.is_symlink():
        raise LegacyMigrationError("report_invalid", "Pruefprotokoll darf kein Symlink sein.")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise LegacyMigrationError("report_invalid", "Pruefprotokoll ist nicht lesbar.") from error
    if not isinstance(report, dict) or type(report.get("report_version")) is not int or report["report_version"] != REPORT_VERSION:
        raise LegacyMigrationError("report_invalid", "Pruefprotokoll hat ein unbekanntes Format.")
    try:
        checked_at = datetime.fromisoformat(report["checked_at"])
    except (KeyError, TypeError, ValueError) as error:
        raise LegacyMigrationError("report_invalid", "Pruefzeitpunkt ist ungueltig.") from error
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise LegacyMigrationError("report_invalid", "Pruefzeitpunkt muss eine Zeitzone enthalten.")
    if report.get("result") != "verified" or report.get("abort_code") is not None:
        raise LegacyMigrationError("report_not_verified", "Pruefprotokoll belegt keine erfolgreiche Pruefung.")
    if report.get("sample_limit") != SAMPLE_SIZE or report.get("tolerances") != report_tolerances():
        raise LegacyMigrationError("report_invalid", "Pruefprotokoll hat andere Stichproben- oder Vergleichsregeln.")
    return report


def _check_marker_unreleased(connection: QdrantConnection, collection: str) -> None:
    path = connection.release_path(collection)
    if path.is_symlink():
        raise LegacyMigrationError("marker_invalid", "Freigabemarker darf kein Symlink sein.")
    if not path.exists():
        return
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise LegacyMigrationError("marker_invalid", "Freigabemarker ist nicht lesbar.") from error
    if not isinstance(marker, dict):
        raise LegacyMigrationError("marker_invalid", "Freigabemarker ist ungueltig.")
    if "compatibility" in marker or "provenance" in marker:
        raise LegacyMigrationError("already_released", "Collection besitzt bereits eine Freigabe.")


def _all_points(client, collection: str) -> dict[int, dict]:
    points: dict[int, dict] = {}
    offset = None
    while True:
        records, next_offset = client.scroll(
            collection_name=collection, with_payload=True, with_vectors=False,
            limit=BACKFILL_SIZE, offset=offset,
        )
        for record in records:
            if type(record.id) is not int or record.id in points or not isinstance(record.payload, dict):
                raise LegacyMigrationError("collection_changed", "Punktliste oder Payload ist nicht mehr eindeutig.")
            points[record.id] = record.payload
        if next_offset is None:
            return points
        if next_offset == offset or not records:
            raise LegacyMigrationError("collection_changed", "Punktliste ist unvollstaendig.")
        offset = next_offset


def _check_identity(points: dict[int, dict], report: dict, client, collection: str) -> None:
    count = client.count(collection_name=collection, exact=True).count
    if (type(count) is not int or count != report["point_count"]
            or len(points) != count
            or _point_ids_sha256(list(points)) != report["point_ids_sha256"]):
        raise LegacyMigrationError("collection_changed", "Collection passt nicht mehr zum Pruefprotokoll.")


@locked_model_operation
def apply_verified_legacy_report(
    connection: QdrantConnection, client, collection: str, report_path: Path, *,
    confirm_collection: str, inspection_options: dict | None = None,
) -> dict:
    """Recheck a report, backfill payloads and atomically publish the release marker.

    The caller must explicitly repeat the collection name. No vector write API
    is used. A failed backfill attempts to remove only keys added by this run.
    """

    if confirm_collection != collection:
        raise LegacyMigrationError("confirmation_required", "Collection muss ausdruecklich bestaetigt werden.")
    if collection == "landkreis_publications":
        raise LegacyMigrationError("rebuild_required", "Landkreis-Collection muss getrennt neu aufgebaut werden.")
    with _migration_lock(connection, collection):
        return _apply_verified_legacy_report(
            connection, client, collection, report_path, inspection_options=inspection_options,
        )


def _apply_verified_legacy_report(
    connection: QdrantConnection, client, collection: str, report_path: Path, *,
    inspection_options: dict | None,
) -> dict:
    """Keep the lock through marker publication or payload rollback."""

    report = _read_report(Path(report_path))
    if report.get("collection") != collection or report.get("target_sha256") != target_sha256(connection):
        raise LegacyMigrationError("report_target_mismatch", "Pruefprotokoll gehoert zu einem anderen Ziel.")
    expected_source = (str(Path((inspection_options or {}).get("ratsinfo_db", LOCAL_INDEX_DB)).resolve())
                       if collection == "ratsi_documents" else None)
    if report.get("source_db") != expected_source:
        raise LegacyMigrationError("source_mismatch", "Pruefprotokoll gehoert zu einer anderen Quelldatenbank.")
    _check_marker_unreleased(connection, collection)
    inspection = inspect_legacy_collection(connection, client, collection, **(inspection_options or {}))
    expected = {
        "target": inspection.target,
        "target_sha256": inspection.target_sha256,
        "collection": inspection.collection,
        "point_count": inspection.point_count,
        "point_ids_sha256": inspection.point_ids_sha256,
        "sample_count": len(inspection.sample_ids),
        "sample_ids": list(inspection.sample_ids),
        "compatibility": inspection.compatibility.as_dict(),
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise LegacyMigrationError("report_stale", "Pruefprotokoll passt nicht zur erneuten Bestandspruefung.")
    points = _all_points(client, collection)
    _check_identity(points, report, client, collection)
    compatibility = inspection.compatibility.as_dict()
    missing: list[int] = []
    had_provenance: set[int] = set()
    for point_id, payload in points.items():
        _check_hints(payload, inspection.compatibility)
        provenance = payload.get(PROVENANCE_KEY)
        if provenance not in (None, LEGACY_PROVENANCE):
            raise LegacyMigrationError("provenance_mismatch", "Punkt besitzt eine widerspruechliche Herkunft.")
        if "index_compatibility" not in payload:
            missing.append(point_id)
            if PROVENANCE_KEY in payload:
                had_provenance.add(point_id)
    changed: list[int] = []
    try:
        for start in range(0, len(missing), BACKFILL_SIZE):
            batch = missing[start:start + BACKFILL_SIZE]
            changed.extend(batch)  # Include a partly completed Qdrant request in rollback.
            client.set_payload(
                collection_name=collection, points=batch, wait=True,
                payload={"index_compatibility": compatibility, PROVENANCE_KEY: LEGACY_PROVENANCE},
            )
        updated = _all_points(client, collection)
        _check_identity(updated, report, client, collection)
        for point_id, payload in updated.items():
            _check_hints(payload, inspection.compatibility)
            try:
                stored = IndexCompatibility.from_dict(payload.get("index_compatibility"))
            except (TypeError, ValueError) as error:
                raise LegacyMigrationError("backfill_incomplete", "Kompatibilitaets-Payload ist ungueltig.") from error
            if stored != inspection.compatibility:
                raise LegacyMigrationError("backfill_incomplete", "Kompatibilitaets-Payload ist unvollstaendig.")
            if point_id in missing and payload.get(PROVENANCE_KEY) != LEGACY_PROVENANCE:
                raise LegacyMigrationError("backfill_incomplete", "Herkunfts-Payload ist unvollstaendig.")
        _check_marker_unreleased(connection, collection)
        metadata = {"ready": True, "provenance": LEGACY_PROVENANCE,
                    "points_count": inspection.point_count,
                    "inspection_sha256": inspection.point_ids_sha256,
                    "inspection_checked_at": report["checked_at"]}
        if collection == "landkreis_publications":
            from scripts.build_landkreis_vector_index import DEFAULT_MAX_TEXT_CHARS

            # Legacy inspection recalculates Landkreis vectors with this default.
            metadata["build_options"] = {"max_text_chars": DEFAULT_MAX_TEXT_CHARS}
        connection.write_readiness(
            client,
            metadata,
            collection=collection, compatibility=inspection.compatibility,
        )
    except BaseException as operation_error:
        # Also compensate an operator interrupt before the release marker commits.
        try:
            for start in range(0, len(changed), BACKFILL_SIZE):
                batch = changed[start:start + BACKFILL_SIZE]
                client.delete_payload(collection_name=collection, points=batch,
                                      keys=["index_compatibility"], wait=True)
                without_provenance = [point_id for point_id in batch if point_id not in had_provenance]
                if without_provenance:
                    client.delete_payload(collection_name=collection, points=without_provenance,
                                          keys=[PROVENANCE_KEY], wait=True)
            reverted = _all_points(client, collection)
            for point_id in changed:
                if "index_compatibility" in reverted[point_id]:
                    raise ValueError("Compatibility payload was not removed")
                if point_id not in had_provenance and PROVENANCE_KEY in reverted[point_id]:
                    raise ValueError("Provenance payload was not removed")
        except BaseException as error:
            raise LegacyMigrationError("rollback_incomplete", "Payload-Ruecknahme ist unvollstaendig; Marker blieb unveraendert.") from error
        if isinstance(operation_error, (LegacyMigrationError, LegacyInspectionError, KeyboardInterrupt, SystemExit)):
            raise
        raise LegacyMigrationError("release_failed", "Freigabe wurde vor dem Marker-Abschluss abgebrochen.") from operation_error
    return {"collection": collection, "provenance": LEGACY_PROVENANCE,
            "point_count": inspection.point_count, "backfilled_points": len(missing)}
