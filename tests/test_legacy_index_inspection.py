"""Read-only, deterministic legacy vector inspection with a tiny local store."""

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER
from src.config.embedding_model_status import PreparedModelUnavailableError
from src.config.index_compatibility import IndexCompatibility
from src.indexing.legacy_index_inspection import (
    LegacyInspectionError,
    SAMPLE_SIZE,
    _compare_vectors,
    inspect_legacy_collection,
    select_sample_ids,
    target_sha256,
)
from src.indexing.legacy_inspection_report import inspect_and_write_report
from src.indexing.legacy_index_migration import LegacyMigrationError, apply_verified_legacy_report
from src.qdrant_connection import QdrantConnection


@pytest.fixture
def compatibility() -> IndexCompatibility:
    return IndexCompatibility(
        dense_model_id=HARRIER_MODEL.model_id,
        dense_revision=HARRIER_MODEL.revision,
        sparse_model_id=BM25_MODEL.model_id,
        sparse_revision=BM25_MODEL.revision,
        tokenizer_model_id=HARRIER_TOKENIZER.model_id,
        tokenizer_revision=HARRIER_TOKENIZER.revision,
        manifest_sha256="a" * 64,
        vector_dimension=3,
        pipeline_version="passages-1",
    )


class Vectorizer:
    def encode_documents(self, texts):
        return [
            {
                "dense_vector": [1.0, 0.0, 0.0],
                "sparse_vector": {"indices": [sum(text.encode()) % 1000 + 1], "values": [1.0]},
            }
            for text in texts
        ]


def _point(point_id, text, payload):
    from qdrant_client.models import PointStruct, SparseVector

    vectors = Vectorizer().encode_documents([text])[0]
    return PointStruct(
        id=point_id,
        vector={
            "harrier": vectors["dense_vector"],
            "bm25": SparseVector(**vectors["sparse_vector"]),
        },
        payload=payload,
    )


def _client(collection="ratsi_passages", *, dimension=3):
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, SparseVectorParams, VectorParams

    client = QdrantClient(":memory:")
    client.create_collection(
        collection,
        vectors_config={"harrier": VectorParams(size=dimension, distance=Distance.COSINE)},
        sparse_vectors_config={"bm25": SparseVectorParams()},
    )
    return client


def _inspect(tmp_path, monkeypatch, client, compatibility, collection="ratsi_passages", **kwargs):
    calls = []

    def current(*, deep):
        calls.append(deep)
        return compatibility

    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility", current)
    result = inspect_legacy_collection(
        QdrantConnection(tmp_path / "unused"), client, collection,
        vectorizer_factory=Vectorizer, **kwargs,
    )
    assert calls == [True]
    return result


def test_sample_selection_is_order_independent_and_contract_bound(compatibility):
    ids = list(range(1, 61))
    first = select_sample_ids("ratsi_passages", ids, compatibility)

    assert len(first) == SAMPLE_SIZE
    assert first == select_sample_ids("ratsi_passages", list(reversed(ids)), compatibility)
    assert first != select_sample_ids("landkreis_publications", ids, compatibility)
    assert first != select_sample_ids(
        "ratsi_passages", ids, replace(compatibility, manifest_sha256="b" * 64),
    )


def test_target_digest_distinguishes_full_urls_and_local_paths(tmp_path):
    first = QdrantConnection(tmp_path / "one", "https://user:secret@example.test/one")
    second = QdrantConnection(tmp_path / "one", "https://user:secret@example.test/two")
    assert first.target == second.target == "https://example.test"
    assert target_sha256(first) != target_sha256(second)
    assert target_sha256(QdrantConnection(tmp_path / "one")) != target_sha256(
        QdrantConnection(tmp_path / "two")
    )


def test_vector_tolerances_are_fixed_and_sparse_indices_exact():
    stored = {"harrier": [1.0, 0.0], "bm25": {"indices": [2], "values": [1.0]}}
    near = {"dense_vector": [1.00001, 0.00001],
            "sparse_vector": {"indices": [2], "values": [1.00001]}}
    _compare_vectors(stored, near, 2)
    with pytest.raises(LegacyInspectionError, match="Dense") as error:
        _compare_vectors(stored, {**near, "dense_vector": [1.0, 0.001]}, 2)
    assert error.value.code == "dense_mismatch"
    with pytest.raises(LegacyInspectionError) as error:
        _compare_vectors(stored, {**near, "sparse_vector": {"indices": [3], "values": [1.0]}}, 2)
    assert error.value.code == "sparse_indices_mismatch"


@pytest.mark.parametrize("scale", [0.9984797464, 1.0020625731])
@pytest.mark.integration
def test_cosine_comparison_matches_qdrant_normalization(scale):
    from qdrant_client.models import PointStruct, SparseVector

    client = _client()
    vector = [0.6 * scale, 0.8 * scale, 0.0]
    sparse = {"indices": [2], "values": [1.0]}
    try:
        client.upsert("ratsi_passages", [PointStruct(
            id=1, vector={"harrier": vector, "bm25": SparseVector(**sparse)},
        )])
        record = client.retrieve("ratsi_passages", ids=[1], with_vectors=True)[0]
        assert max(abs(old - new) for old, new in zip(record.vector["harrier"], vector)) > 1e-4
        _compare_vectors(record.vector, {"dense_vector": vector, "sparse_vector": sparse}, 3)
        with pytest.raises(LegacyInspectionError) as error:
            _compare_vectors(record.vector, {"dense_vector": [0.8, 0.6, 0.0],
                                            "sparse_vector": sparse}, 3)
        assert error.value.code == "dense_mismatch"
    finally:
        client.close()


@pytest.mark.parametrize("vector", [[0.0, 0.0], [float("nan"), 0.0], [float("inf"), 0.0]])
def test_cosine_comparison_rejects_invalid_recalculated_norm(vector):
    sparse = {"indices": [2], "values": [1.0]}
    with pytest.raises(LegacyInspectionError) as error:
        _compare_vectors({"harrier": [1.0, 0.0], "bm25": sparse},
                         {"dense_vector": vector, "sparse_vector": sparse}, 2)
    assert error.value.code == "vector_invalid"


def test_cosine_comparison_does_not_normalize_away_invalid_stored_magnitude():
    sparse = {"indices": [2], "values": [1.0]}
    with pytest.raises(LegacyInspectionError) as error:
        _compare_vectors({"harrier": [1.002, 0.0], "bm25": sparse},
                         {"dense_vector": [1.0, 0.0], "sparse_vector": sparse}, 2)
    assert error.value.code == "dense_mismatch"


def test_missing_model_inventory_has_a_persisted_abort_code(tmp_path, monkeypatch):
    def missing(*, deep):
        raise PreparedModelUnavailableError("Private model path")

    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility", missing)
    path = tmp_path / "inspection.json"
    report = inspect_and_write_report(
        QdrantConnection(tmp_path / "store"), None, "ratsi_passages", path,
    )
    assert report["result"] == "aborted"
    assert report["abort_code"] == "model_unavailable"
    assert "Private model path" not in path.read_text()


@pytest.mark.integration
def test_missing_collection_writes_structured_abort_without_traceback(
    tmp_path, monkeypatch, compatibility, capsys,
):
    from scripts.migrate_legacy_index import main

    monkeypatch.setenv("RATSI_QDRANT_MODE", "local")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client("ratsi_documents")
    monkeypatch.setattr(QdrantConnection, "create_client", lambda self: client)
    report_path = tmp_path / "missing.json"
    (tmp_path / "store").mkdir()
    (tmp_path / "store" / "meta.json").write_text(
        '{"collections":{},"aliases":{}}', encoding="utf-8",
    )

    result = main(["--inspect", "--collection", "ratsi_passages", "--report",
                   str(report_path), "--qdrant-dir", str(tmp_path / "store")])

    assert result == 1
    assert json.loads(report_path.read_text())["abort_code"] == "collection_missing"
    output = capsys.readouterr()
    assert json.loads(output.out)["abort_code"] == "collection_missing"
    assert "Traceback" not in output.out + output.err


def test_failed_report_replace_preserves_previous_report(tmp_path, monkeypatch):
    def missing(*, deep):
        raise PreparedModelUnavailableError("missing")

    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility", missing)
    path = tmp_path / "inspection.json"
    path.write_bytes(b"previous audit")
    original_replace = Path.replace

    def fail_replace(source, destination):
        if destination == path:
            raise OSError("injected atomic replace failure")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="atomic replace"):
        inspect_and_write_report(QdrantConnection(tmp_path / "store"), None,
                                 "ratsi_passages", path)
    assert path.read_bytes() == b"previous audit"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.integration
def test_report_persists_verified_evidence_without_text_or_vectors(tmp_path, monkeypatch, compatibility):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    try:
        client.upsert("ratsi_passages", [_point(1, "private source text", {
            "text": "private source text", "snippet": "private source text", "committed": True,
        })])
        path = tmp_path / "reports" / "inspection.json"
        report = inspect_and_write_report(
            QdrantConnection(tmp_path / "unused"), client, "ratsi_passages", path,
            vectorizer_factory=Vectorizer,
        )
        assert json.loads(path.read_text()) == report
        assert report["result"] == "verified"
        assert report["abort_code"] is None
        assert report["point_count"] == report["sample_count"] == 1
        assert report["sample_ids"] == [1]
        assert report["compatibility"] == compatibility.as_dict()
        assert report["tolerances"] == {
            "dense_abs": 1e-4, "dense_rel": 1e-4, "sparse_abs": 1e-4,
            "sparse_rel": 1e-4, "sparse_indices": "exact",
        }
        assert "private source text" not in path.read_text()
        assert not list(path.parent.glob("*.tmp"))
    finally:
        client.close()


@pytest.mark.integration
def test_report_persists_specific_abort_without_partial_release_evidence(
    tmp_path, monkeypatch, compatibility,
):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    try:
        client.upsert("ratsi_passages", [_point(1, "source", {
            "text": "source", "snippet": "changed", "committed": True,
        })])
        path = tmp_path / "inspection.json"
        report = inspect_and_write_report(
            QdrantConnection(tmp_path / "unused"), client, "ratsi_passages", path,
            vectorizer_factory=Vectorizer,
        )
        assert json.loads(path.read_text()) == report
        assert report["result"] == "aborted"
        assert report["abort_code"] == "text_mismatch"
        assert report["point_count"] is None
        assert report["point_ids_sha256"] is None
        assert report["compatibility"] is None
    finally:
        client.close()


@pytest.mark.integration
@pytest.mark.parametrize("server", [False, True])
def test_confirmed_release_backfills_only_legacy_points_and_preserves_vectors(
    tmp_path, monkeypatch, compatibility, server,
):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    connection = QdrantConnection(
        tmp_path / "store", "https://user:secret@example.test/qdrant" if server else "",
        tmp_path / "server_state",
    )
    try:
        legacy = _point(1, "old text", {"text": "old text", "snippet": "old text", "committed": True})
        native = _point(2, "new text", {"text": "new text", "snippet": "new text",
                                         "committed": True,
                                         "index_compatibility": compatibility.as_dict()})
        client.upsert("ratsi_passages", [legacy, native])
        before = {point.id: point.vector for point in client.retrieve(
            "ratsi_passages", ids=[1, 2], with_vectors=True,
        )}
        report_path = tmp_path / "inspection.json"
        inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                                 vectorizer_factory=Vectorizer)
        with pytest.raises(LegacyMigrationError) as error:
            apply_verified_legacy_report(connection, client, "ratsi_passages", report_path,
                                         confirm_collection="ratsi_documents",
                                         inspection_options={"vectorizer_factory": Vectorizer})
        assert error.value.code == "confirmation_required"
        assert not connection.release_path("ratsi_passages").exists()
        result = apply_verified_legacy_report(
            connection, client, "ratsi_passages", report_path,
            confirm_collection="ratsi_passages",
            inspection_options={"vectorizer_factory": Vectorizer},
        )
        assert result["backfilled_points"] == 1
        after = {point.id: point for point in client.retrieve(
            "ratsi_passages", ids=[1, 2], with_vectors=True,
        )}
        assert {point_id: point.vector for point_id, point in after.items()} == before
        assert after[1].payload["index_compatibility"] == compatibility.as_dict()
        assert after[1].payload["index_provenance"] == "legacy_verified"
        assert "index_provenance" not in after[2].payload
        marker = json.loads(connection.release_path("ratsi_passages").read_text())
        assert marker["provenance"] == "legacy_verified"
        assert marker["compatibility"] == compatibility.as_dict()
        assert marker["points_count"] == 2
        assert "secret" not in connection.release_path("ratsi_passages").read_text()
        if server:
            assert "url_sha256" in marker
        with pytest.raises(LegacyMigrationError) as error:
            apply_verified_legacy_report(connection, client, "ratsi_passages", report_path,
                                         confirm_collection="ratsi_passages",
                                         inspection_options={"vectorizer_factory": Vectorizer})
        assert error.value.code == "already_released"
    finally:
        client.close()


@pytest.mark.integration
def test_changed_point_ids_reject_release_before_payload_writes(tmp_path, monkeypatch, compatibility):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    try:
        client.upsert("ratsi_passages", [_point(1, "one", {
            "text": "one", "snippet": "one", "committed": True,
        })])
        report_path = tmp_path / "inspection.json"
        inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                                 vectorizer_factory=Vectorizer)
        client.upsert("ratsi_passages", [_point(2, "two", {
            "text": "two", "snippet": "two", "committed": True,
        })])
        with pytest.raises(LegacyMigrationError) as error:
            apply_verified_legacy_report(connection, client, "ratsi_passages", report_path,
                                         confirm_collection="ratsi_passages",
                                         inspection_options={"vectorizer_factory": Vectorizer})
        assert error.value.code == "report_stale"
        assert not connection.release_path("ratsi_passages").exists()
        assert all("index_compatibility" not in point.payload for point in client.retrieve(
            "ratsi_passages", ids=[1, 2], with_payload=True,
        ))
    finally:
        client.close()


@pytest.mark.integration
def test_changed_sample_vector_rejects_release_with_unchanged_point_ids(
    tmp_path, monkeypatch, compatibility,
):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    try:
        client.upsert("ratsi_passages", [
            _point(number, f"source-{number}", {
                "text": f"source-{number}", "snippet": f"source-{number}",
                "committed": True,
            })
            for number in range(1, 41)
        ])
        report_path = tmp_path / "inspection.json"
        report = inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                                          vectorizer_factory=Vectorizer)
        assert report["sample_count"] == SAMPLE_SIZE
        assert len(set(report["sample_ids"])) == SAMPLE_SIZE
        selected_id = report["sample_ids"][0]
        changed = client.retrieve("ratsi_passages", ids=[selected_id], with_vectors=True)[0]
        changed.vector["harrier"] = [0.0, 1.0, 0.0]
        client.upsert("ratsi_passages", [changed])
        with pytest.raises(LegacyInspectionError) as error:
            apply_verified_legacy_report(
                connection, client, "ratsi_passages", report_path,
                confirm_collection="ratsi_passages",
                inspection_options={"vectorizer_factory": Vectorizer},
            )
        assert error.value.code == "dense_mismatch"
        assert not connection.release_path("ratsi_passages").exists()
        assert all("index_compatibility" not in point.payload for point in client.retrieve(
            "ratsi_passages", ids=list(range(1, 41)), with_payload=True,
        ))
    finally:
        client.close()


@pytest.mark.integration
def test_unsampled_uncommitted_passage_rejects_legacy_report(
    tmp_path, monkeypatch, compatibility,
):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    try:
        ids = list(range(1, SAMPLE_SIZE + 9))
        sample = set(select_sample_ids("ratsi_passages", ids, compatibility))
        uncommitted_id = next(point_id for point_id in ids if point_id not in sample)
        client.upsert("ratsi_passages", [
            _point(point_id, f"source-{point_id}", {
                "text": f"source-{point_id}", "snippet": f"source-{point_id}",
                "committed": point_id != uncommitted_id,
            })
            for point_id in ids
        ])
        report = inspect_and_write_report(
            connection, client, "ratsi_passages", tmp_path / "inspection.json",
            vectorizer_factory=Vectorizer,
        )
        assert report["result"] == "aborted"
        assert report["abort_code"] == "text_unavailable"
        assert not connection.release_path("ratsi_passages").exists()
    finally:
        client.close()


def test_report_for_other_target_is_rejected_before_inspection(tmp_path, monkeypatch):
    first = QdrantConnection(tmp_path / "one")
    second = QdrantConnection(tmp_path / "two")
    report_path = tmp_path / "inspection.json"
    report_path.write_text(json.dumps({
        "report_version": 2, "checked_at": "2026-01-01T00:00:00+00:00",
        "result": "verified", "abort_code": None,
        "collection": "ratsi_passages", "target_sha256": target_sha256(first),
        "sample_limit": SAMPLE_SIZE,
        "tolerances": {"dense_abs": 1e-4, "dense_rel": 1e-4,
                       "sparse_abs": 1e-4, "sparse_rel": 1e-4,
                       "sparse_indices": "exact"},
    }))
    monkeypatch.setattr("src.indexing.legacy_index_migration.inspect_legacy_collection",
                        lambda *args, **kwargs: pytest.fail("Inspection should not start"))
    with pytest.raises(LegacyMigrationError) as error:
        apply_verified_legacy_report(second, None, "ratsi_passages", report_path,
                                     confirm_collection="ratsi_passages")
    assert error.value.code == "report_target_mismatch"


@pytest.mark.integration
@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_failed_marker_publication_rolls_back_payload(tmp_path, monkeypatch, compatibility, failure):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    try:
        client.upsert("ratsi_passages", [_point(1, "one", {
            "text": "one", "snippet": "one", "committed": True,
        })])
        report_path = tmp_path / "inspection.json"
        inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                                 vectorizer_factory=Vectorizer)
        def fail(*args, **kwargs):
            raise failure("injected marker failure")
        monkeypatch.setattr(QdrantConnection, "write_readiness", fail)
        expected_error = LegacyMigrationError if failure is OSError else KeyboardInterrupt
        with pytest.raises(expected_error) as error:
            apply_verified_legacy_report(connection, client, "ratsi_passages", report_path,
                                         confirm_collection="ratsi_passages",
                                         inspection_options={"vectorizer_factory": Vectorizer})
        if failure is OSError:
            assert error.value.code == "release_failed"
        payload = client.retrieve("ratsi_passages", ids=[1], with_payload=True)[0].payload
        assert "index_compatibility" not in payload
        assert "index_provenance" not in payload
        assert not connection.release_path("ratsi_passages").exists()
    finally:
        client.close()


@pytest.mark.integration
def test_partial_backfill_failure_rolls_back_and_can_resume_with_same_report(
    tmp_path, monkeypatch, compatibility,
):
    from src.indexing import legacy_index_migration

    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    monkeypatch.setattr(legacy_index_migration, "BACKFILL_SIZE", 2)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    marker_path = connection.release_path("ratsi_passages")
    marker_path.parent.mkdir(parents=True)
    original_marker = b'{"model":"' + compatibility.dense_model_id.encode() + b'"}'
    marker_path.write_bytes(original_marker)
    try:
        client.upsert("ratsi_passages", [
            _point(number, f"source-{number}", {
                "text": f"source-{number}", "snippet": f"source-{number}",
                "committed": True,
            })
            for number in range(1, 4)
        ])
        before = {point.id: point.vector for point in client.retrieve(
            "ratsi_passages", ids=[1, 2, 3], with_vectors=True,
        )}
        report_path = tmp_path / "inspection.json"
        inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                                 vectorizer_factory=Vectorizer)

        class FailAfterSecondBatch:
            writes = 0

            def __getattr__(self, name):
                return getattr(client, name)

            def set_payload(self, **kwargs):
                self.writes += 1
                result = client.set_payload(**kwargs)
                if self.writes == 2:
                    raise OSError("injected partial batch failure")
                return result

        with pytest.raises(LegacyMigrationError) as error:
            apply_verified_legacy_report(
                connection, FailAfterSecondBatch(), "ratsi_passages", report_path,
                confirm_collection="ratsi_passages",
                inspection_options={"vectorizer_factory": Vectorizer},
            )
        assert error.value.code == "release_failed"
        assert marker_path.read_bytes() == original_marker
        rolled_back = client.retrieve("ratsi_passages", ids=[1, 2, 3], with_vectors=True)
        assert all("index_compatibility" not in point.payload
                   and "index_provenance" not in point.payload for point in rolled_back)
        assert {point.id: point.vector for point in rolled_back} == before

        result = apply_verified_legacy_report(
            connection, client, "ratsi_passages", report_path,
            confirm_collection="ratsi_passages",
            inspection_options={"vectorizer_factory": Vectorizer},
        )
        assert result["backfilled_points"] == 3
        assert connection.read_index_compatibility("ratsi_passages") == compatibility
        assert all(point.payload["index_provenance"] == "legacy_verified"
                   for point in client.retrieve("ratsi_passages", ids=[1, 2, 3]))
    finally:
        client.close()


@pytest.mark.integration
def test_failed_rollback_keeps_marker_unreleased_and_retry_finishes_backfill(
    tmp_path, monkeypatch, compatibility,
):
    from src.indexing import legacy_index_migration

    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    monkeypatch.setattr(legacy_index_migration, "BACKFILL_SIZE", 1)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    try:
        client.upsert("ratsi_passages", [
            _point(number, f"source-{number}", {
                "text": f"source-{number}", "snippet": f"source-{number}", "committed": True,
            })
            for number in (1, 2)
        ])
        report_path = tmp_path / "inspection.json"
        inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                                 vectorizer_factory=Vectorizer)

        class InterruptedClient:
            def __getattr__(self, name):
                return getattr(client, name)

            def set_payload(self, **kwargs):
                client.set_payload(**kwargs)
                raise OSError("write acknowledgement lost")

            def delete_payload(self, **kwargs):
                raise OSError("rollback unavailable")

        with pytest.raises(LegacyMigrationError) as error:
            apply_verified_legacy_report(
                connection, InterruptedClient(), "ratsi_passages", report_path,
                confirm_collection="ratsi_passages",
                inspection_options={"vectorizer_factory": Vectorizer},
            )
        assert error.value.code == "rollback_incomplete"
        assert not connection.release_path("ratsi_passages").exists()
        partial = client.retrieve("ratsi_passages", ids=[1, 2], with_payload=True)
        assert sum("index_compatibility" in point.payload for point in partial) == 1

        result = apply_verified_legacy_report(
            connection, client, "ratsi_passages", report_path,
            confirm_collection="ratsi_passages",
            inspection_options={"vectorizer_factory": Vectorizer},
        )
        assert result["backfilled_points"] == 1
        assert connection.read_index_compatibility("ratsi_passages") == compatibility
    finally:
        client.close()


@pytest.mark.integration
def test_competing_migrations_cannot_rollback_a_published_release(
    tmp_path, monkeypatch, compatibility,
):
    monkeypatch.setattr("src.indexing.legacy_index_inspection.current_index_compatibility",
                        lambda *, deep: compatibility)
    client = _client()
    connection = QdrantConnection(tmp_path / "store")
    client.upsert("ratsi_passages", [_point(1, "source", {
        "text": "source", "snippet": "source", "committed": True,
    })])
    report_path = tmp_path / "inspection.json"
    inspect_and_write_report(connection, client, "ratsi_passages", report_path,
                             vectorizer_factory=Vectorizer)
    first_write = Event()
    release_first = Event()

    class PausedClient:
        def __getattr__(self, name):
            return getattr(client, name)

        def set_payload(self, **kwargs):
            client.set_payload(**kwargs)
            first_write.set()
            assert release_first.wait(5)

    def apply(using):
        return apply_verified_legacy_report(
            connection, using, "ratsi_passages", report_path,
            confirm_collection="ratsi_passages",
            inspection_options={"vectorizer_factory": Vectorizer},
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(apply, PausedClient())
            assert first_write.wait(5)
            second = pool.submit(apply, client)
            try:
                with pytest.raises(TimeoutError):
                    second.result(timeout=0.1)
            finally:
                release_first.set()
            assert first.result(timeout=5)["backfilled_points"] == 1
            with pytest.raises(LegacyMigrationError) as error:
                second.result(timeout=5)
        assert error.value.code == "already_released"
        assert connection.read_index_compatibility("ratsi_passages") == compatibility
        point = client.retrieve("ratsi_passages", ids=[1])[0]
        assert point.payload["index_compatibility"] == compatibility.as_dict()
        assert point.payload["index_provenance"] == "legacy_verified"
    finally:
        release_first.set()
        client.close()


@pytest.mark.integration
def test_passage_inspection_reads_only_and_checks_fixed_sample(tmp_path, monkeypatch, compatibility):
    client = _client()
    try:
        client.upsert("ratsi_passages", [
            _point(number, f"text-{number}", {
                "text": f"text-{number}", "snippet": f"text-{number}",
                "committed": True, "model": compatibility.dense_model_id,
                "pipeline_version": compatibility.pipeline_version,
            })
            for number in range(1, 41)
        ])

        class ReadOnlyClient:
            def __getattr__(self, name):
                if name not in {"get_collections", "get_collection", "count", "scroll", "retrieve"}:
                    raise AssertionError(f"Unexpected write call: {name}")
                return getattr(client, name)

        result = _inspect(tmp_path, monkeypatch, ReadOnlyClient(), compatibility)

        assert result.collection == "ratsi_passages"
        assert result.point_count == 40
        assert result.sample_ids == select_sample_ids("ratsi_passages", list(range(1, 41)), compatibility)
        assert len(result.point_ids_sha256) == 64
        assert result.compatibility == compatibility
        assert client.count("ratsi_passages", exact=True).count == 40
        assert not (tmp_path / "unused").exists()
    finally:
        client.close()


@pytest.mark.integration
@pytest.mark.parametrize("collection", ["ratsi_documents", "landkreis_publications"])
def test_document_text_is_reconstructed_from_original_builder(
    tmp_path, monkeypatch, compatibility, collection,
):
    from scripts import build_landkreis_vector_index, build_vector_index
    from src.indexing.id_strategy import stable_document_id
    from src.indexing.payload_builder import build_document_payload

    if collection == "ratsi_documents":
        row = {"session_id": "1", "url": "https://example.test/one", "agenda_item": "1",
               "title": "Rat", "document_type": "protokoll", "local_path": ""}
        point_id = stable_document_id("1", row["url"], "1")
        text = build_vector_index._get_document_text(row)
        payload = build_document_payload(row, search_text=text)
        monkeypatch.setattr(build_vector_index, "_load_documents", lambda path, *, read_only: [row] if read_only else [])
    else:
        row = {"publication_id": "one", "url": "https://example.test/one",
               "title": "Bekanntmachung", "document_title": "Anlage", "extracted_text": "Prueftext",
               "local_path": "one.pdf"}
        point_id = build_landkreis_vector_index._stable_landkreis_qdrant_id("one", row["url"])
        text = build_landkreis_vector_index._document_text(row)
        payload = build_landkreis_vector_index._build_payload(row, data_root=tmp_path, search_text=text)
        monkeypatch.setattr(build_landkreis_vector_index, "_load_documents", lambda path, *, read_only: [row] if read_only else [])
    client = _client(collection)
    try:
        client.upsert(collection, [_point(point_id, text, payload)])
        result = _inspect(tmp_path, monkeypatch, client, compatibility, collection,
                          ratsinfo_db=tmp_path / "unused.sqlite",
                          landkreis_db=tmp_path / "unused-county.sqlite",
                          landkreis_data_root=tmp_path)
        assert result.sample_ids == (point_id,)
        assert result.point_count == 1
        connection = QdrantConnection(tmp_path / "unused")
        report_path = tmp_path / f"{collection}.inspection.json"
        options = {"ratsinfo_db": tmp_path / "unused.sqlite",
                   "landkreis_db": tmp_path / "unused-county.sqlite",
                   "landkreis_data_root": tmp_path, "vectorizer_factory": Vectorizer}
        before = client.retrieve(collection, ids=[point_id], with_vectors=True)[0].vector
        report = inspect_and_write_report(connection, client, collection, report_path, **options)
        if collection == "landkreis_publications":
            assert report["result"] == "aborted"
            assert report["abort_code"] == "rebuild_required"
            with pytest.raises(LegacyMigrationError, match="neu aufgebaut") as error:
                apply_verified_legacy_report(
                    connection, client, collection, report_path,
                    confirm_collection=collection, inspection_options=options,
                )
            assert error.value.code == "rebuild_required"
            assert client.retrieve(collection, ids=[point_id], with_vectors=True)[0].vector == before
            assert connection.read_index_compatibility(collection) is None
            return
        assert report["result"] == "verified"
        assert report["source_db"] == str((tmp_path / "unused.sqlite").resolve())
        with pytest.raises(LegacyMigrationError) as error:
            apply_verified_legacy_report(
                connection, client, collection, report_path,
                confirm_collection=collection,
                inspection_options={**options, "ratsinfo_db": tmp_path / "different.sqlite"},
            )
        assert error.value.code == "source_mismatch"
        assert client.retrieve(collection, ids=[point_id], with_vectors=True)[0].vector == before
        assert connection.read_index_compatibility(collection) is None
        released = apply_verified_legacy_report(
            connection, client, collection, report_path,
            confirm_collection=collection, inspection_options=options,
        )
        assert released["backfilled_points"] == 1
        migrated = client.retrieve(collection, ids=[point_id], with_vectors=True)[0]
        assert migrated.vector == before
        assert migrated.payload["index_compatibility"] == compatibility.as_dict()
        assert migrated.payload["index_provenance"] == "legacy_verified"
        assert connection.read_index_compatibility(collection) == compatibility
        marker = json.loads(connection.release_path(collection).read_text(encoding="utf-8"))
        assert "build_options" not in marker
    finally:
        client.close()


@pytest.mark.parametrize("sparse", ["idf", "float16"])
def test_schema_rejects_sparse_scoring_changes(compatibility, sparse):
    from qdrant_client.models import (
        Datatype, Distance, Modifier, SparseIndexParams, SparseVectorParams, VectorParams,
    )
    from src.indexing.legacy_index_inspection import _check_schema

    sparse_params = (SparseVectorParams(modifier=Modifier.IDF) if sparse == "idf"
                     else SparseVectorParams(index=SparseIndexParams(datatype=Datatype.FLOAT16)))
    info = SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(
        vectors={"harrier": VectorParams(size=compatibility.vector_dimension,
                                         distance=Distance.COSINE)},
        sparse_vectors={"bm25": sparse_params},
    )))
    with pytest.raises(LegacyInspectionError, match="Vektorschema"):
        _check_schema(info, compatibility)


@pytest.mark.parametrize("dense_setting", ["float16", "hnsw"])
def test_schema_rejects_non_native_dense_settings(compatibility, dense_setting):
    from qdrant_client.models import (
        Datatype, Distance, HnswConfigDiff, SparseVectorParams, VectorParams,
    )
    from src.indexing.legacy_index_inspection import _check_schema

    changes = ({"datatype": Datatype.FLOAT16} if dense_setting == "float16"
               else {"hnsw_config": HnswConfigDiff(m=32)})
    info = SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(
        vectors={"harrier": VectorParams(size=compatibility.vector_dimension,
                                         distance=Distance.COSINE, **changes)},
        sparse_vectors={"bm25": SparseVectorParams()},
    )))
    with pytest.raises(LegacyInspectionError, match="Vektorschema"):
        _check_schema(info, compatibility)


@pytest.mark.integration
def test_missing_source_database_is_not_created(tmp_path, monkeypatch, compatibility):
    from scripts.build_vector_index import _stable_qdrant_id

    collection = "ratsi_documents"
    url = "https://example.test/one"
    point_id = _stable_qdrant_id("1", url, "1")
    db_path = tmp_path / "missing.sqlite"
    client = _client(collection)
    try:
        client.upsert(collection, [_point(point_id, "Rat protokoll", {
            "url": url, "snippet": "Rat protokoll",
        })])
        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, client, compatibility, collection,
                     ratsinfo_db=db_path)
        assert error.value.code == "source_missing"
        assert not db_path.exists()
    finally:
        client.close()


@pytest.mark.integration
@pytest.mark.parametrize("change,code", [
    ("model", "model_mismatch"),
    ("text", "text_mismatch"),
    ("dense", "dense_mismatch"),
    ("sparse", "sparse_indices_mismatch"),
    ("sparse_values", "sparse_values_mismatch"),
])
def test_inspection_rejects_conflicting_evidence(tmp_path, monkeypatch, compatibility, change, code):
    from qdrant_client.models import SparseVector

    client = _client()
    try:
        payload = {"text": "source", "snippet": "source", "committed": True}
        point = _point(1, "source", payload)
        if change == "model":
            point.payload["model"] = "other/model"
        elif change == "text":
            point.payload["snippet"] = "changed"
        elif change == "dense":
            point.vector["harrier"] = [0.0, 1.0, 0.0]
        elif change == "sparse":
            point.vector["bm25"] = SparseVector(indices=[9999], values=[1.0])
        else:
            point.vector["bm25"] = SparseVector(
                indices=point.vector["bm25"].indices,
                values=[2.0],
            )
        client.upsert("ratsi_passages", [point])

        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, client, compatibility)
        assert error.value.code == code
    finally:
        client.close()


@pytest.mark.integration
def test_inspection_rejects_incomplete_retrieval(tmp_path, monkeypatch, compatibility):
    client = _client()
    try:
        client.upsert("ratsi_passages", [_point(1, "source", {
            "text": "source", "snippet": "source", "committed": True,
        })])

        class IncompleteClient:
            def __getattr__(self, name):
                if name == "retrieve":
                    return lambda **kwargs: []
                return getattr(client, name)

        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, IncompleteClient(), compatibility)
        assert error.value.code == "sample_incomplete"
    finally:
        client.close()


@pytest.mark.integration
def test_inspection_rejects_collection_changed_during_check(tmp_path, monkeypatch, compatibility):
    client = _client()
    payload = {"text": "source", "snippet": "source", "committed": True}
    try:
        client.upsert("ratsi_passages", [_point(1, "source", payload)])

        class ChangingClient:
            scroll_calls = 0

            def __getattr__(self, name):
                if name != "scroll":
                    return getattr(client, name)

                def scroll(**kwargs):
                    self.scroll_calls += 1
                    if self.scroll_calls == 2:
                        return [SimpleNamespace(id=2, payload=payload)], None
                    return client.scroll(**kwargs)

                return scroll

        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, ChangingClient(), compatibility)
        assert error.value.code == "collection_changed"
    finally:
        client.close()


@pytest.mark.integration
def test_inspection_rejects_wrong_schema_and_marker(tmp_path, monkeypatch, compatibility):
    client = _client(dimension=4)
    try:
        point = _point(1, "source", {
            "text": "source", "snippet": "source", "committed": True,
        })
        point.vector["harrier"] = [1.0, 0.0, 0.0, 0.0]
        client.upsert("ratsi_passages", [point])
        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, client, compatibility)
        assert error.value.code == "schema_mismatch"
    finally:
        client.close()

    client = _client()
    try:
        client.upsert("ratsi_passages", [_point(1, "source", {
            "text": "source", "snippet": "source", "committed": True,
        })])
        marker = QdrantConnection(tmp_path / "unused").release_path("ratsi_passages")
        marker.parent.mkdir(parents=True)
        marker.write_text('{"model":"other/model"}', encoding="utf-8")
        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, client, compatibility)
        assert error.value.code == "model_mismatch"
        marker.write_text('{"points_count":2}', encoding="utf-8")
        with pytest.raises(LegacyInspectionError) as error:
            _inspect(tmp_path, monkeypatch, client, compatibility)
        assert error.value.code == "marker_count_mismatch"
    finally:
        client.close()
