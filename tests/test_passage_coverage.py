"""Cached coverage stays cheap to read and does not pretend stale data is current."""

import json

import pytest

from src.indexing.passage_coverage import database_stamp, read_coverage, write_coverage
from src.qdrant_connection import QdrantConnection

pytestmark = pytest.mark.integration


@pytest.fixture
def coverage(tmp_path):
    connection = QdrantConnection(tmp_path / "qdrant")
    connection.path.mkdir()
    connection.ready_path.write_text('{"ready": false}')
    db = tmp_path / "source.sqlite"
    db.write_bytes(b"source")
    inventory = {1: {"document_id": 1, "chunk_count": 1, "chunk_index": 0,
                     "committed": True, "generation": "a"},
                 2: {"document_id": 2, "chunk_count": 2, "chunk_index": 0,
                     "committed": True, "generation": "b"}}
    write_coverage(connection, db, database_stamp(db), {1, 2, 3}, inventory)
    return connection, db


def test_counts_include_only_complete_expected_documents(coverage):
    connection, db = coverage
    result = read_coverage(connection, db, 2)
    assert result["total_documents"] == 3
    assert result["complete_documents"] == 1
    assert result["missing_documents"] == 2
    assert read_coverage(connection, db, 3) is None


@pytest.mark.parametrize("change", ["db", "wal", "marker", "invalid", "missing"])
def test_stale_or_invalid_cache_is_not_displayed(coverage, change):
    connection, db = coverage
    path = connection.ready_path.with_suffix(".coverage.json")
    if change == "db":
        db.write_bytes(b"new source")
    elif change == "wal":
        db.with_name(db.name + "-wal").write_bytes(b"pending transaction")
    elif change == "marker":
        connection.ready_path.write_text('{"ready": true}')
    elif change == "invalid":
        result = json.loads(path.read_text())
        result["missing_documents"] = -1
        path.write_text(json.dumps(result))
    else:
        path.unlink()
    assert read_coverage(connection, db, 2) is None


def test_changed_source_during_build_discards_old_cache(coverage):
    connection, db = coverage
    before = database_stamp(db)
    db.write_bytes(b"changed")
    write_coverage(connection, db, before, set(), {})
    assert not connection.ready_path.with_suffix(".coverage.json").exists()
