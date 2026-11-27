"""Persist document coverage so status pages need no passage scan."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from src.indexing.passage_inventory import complete_document_ids


def database_stamp(db_path: Path) -> dict:
    """Identify a source SQLite file and its optional WAL without querying it."""
    path = db_path.resolve()
    def stamp(file, *, empty_is_absent=False):
        try:
            info = file.stat()
            # Opening a WAL-mode reader may create a zero-byte WAL. It holds
            # no data changes and is equivalent to a missing WAL for coverage.
            if empty_is_absent and info.st_size == 0:
                return None
            return [info.st_size, info.st_mtime_ns]
        except FileNotFoundError:
            return None
    return {"path": str(path), "database": stamp(path),
            "wal": stamp(Path(str(path) + "-wal"), empty_is_absent=True)}


def _marker_digest(connection):
    return sha256(connection.release_path("ratsi_passages").read_bytes()).hexdigest()


def write_coverage(connection, db_path, source_stamp, expected, inventory):
    """Save build results only while the source database is unchanged."""
    path = connection.release_path("ratsi_passages").with_suffix(".coverage.json")
    if (database_stamp(db_path) != source_stamp
            or not connection.release_path("ratsi_passages").is_file()):
        path.unlink(missing_ok=True)
        return
    complete = complete_document_ids(inventory)
    record = {"format_version": 1, "source": source_stamp,
              "marker_sha256": _marker_digest(connection),
              "updated_at": datetime.now(timezone.utc).isoformat(),
              "points": len(inventory), "total_documents": len(expected),
              "complete_documents": len(expected & complete),
              "missing_documents": len(expected - complete)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_coverage(connection, db_path, point_count):
    """Return current cached coverage, or None for missing/stale/invalid data."""
    try:
        path = connection.release_path("ratsi_passages").with_suffix(".coverage.json")
        record = json.loads(path.read_text(encoding="utf-8"))
        source = record["source"]
        # Older cache files may have recorded an empty WAL with its mtime.
        wal = source.get("wal")
        if isinstance(wal, list) and len(wal) == 2 and type(wal[0]) is int and wal[0] == 0:
            source = {**source, "wal": None}
        fields = ("points", "total_documents", "complete_documents", "missing_documents")
        if (record.get("format_version") != 1
                or any(type(record.get(k)) is not int or record[k] < 0 for k in fields)
                or record["complete_documents"] + record["missing_documents"] != record["total_documents"]
                or record["points"] != point_count
                or source != database_stamp(db_path)
                or source["database"] is None
                or record["marker_sha256"] != _marker_digest(connection)):
            return None
        return record
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
