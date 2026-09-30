"""Build preflight rejects unverified indexes before any Qdrant mutation."""

from dataclasses import replace
import json

import pytest

from src.analysis.vector_store import DocumentVectorStore
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER
from src.config.index_compatibility import IndexCompatibility
from src.indexing.build_compatibility import IndexBuildCompatibilityError
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
        vector_dimension=HARRIER_MODEL.vector_dimension,
        pipeline_version="passages-1",
    )


def _store(tmp_path, collection, compatibility=None):
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, SparseVector

    client = QdrantClient(":memory:")
    store = DocumentVectorStore(tmp_path / "unused", collection_name=collection)
    store.connection = QdrantConnection(tmp_path / "markers")
    store._client = client
    store.ensure_collection()
    client.upsert(collection, [PointStruct(
        id=1, vector={"harrier": [1.0] + [0.0] * 1023,
                      "bm25": SparseVector(indices=[1], values=[1.0])},
        payload={"text": "legacy", **({"index_compatibility": compatibility.as_dict()}
                                    if compatibility else {})},
    )])
    return store


@pytest.mark.integration
@pytest.mark.parametrize("collection", [
    "ratsi_passages", "ratsi_documents", "landkreis_publications",
])
def test_nonempty_collection_without_contract_is_rejected_before_writes(
    tmp_path, compatibility, collection,
):
    store = _store(tmp_path, collection)
    client = store._get_client()
    original_upsert = client.upsert
    original_set_payload = client.set_payload
    try:
        client.upsert = lambda *args, **kwargs: pytest.fail("Unexpected vector write")
        client.set_payload = lambda *args, **kwargs: pytest.fail("Unexpected payload write")
        with pytest.raises(IndexBuildCompatibilityError, match="Kompatibilitaetsmarker"):
            store.begin_build(compatibility)
        assert not store.connection.release_path(collection).exists()
        assert client.count(collection, exact=True).count == 1
    finally:
        client.upsert = original_upsert
        client.set_payload = original_set_payload
        store.close()


@pytest.mark.integration
@pytest.mark.parametrize("provenance", ["native", "legacy_verified"])
@pytest.mark.parametrize("collection", [
    "ratsi_passages", "ratsi_documents", "landkreis_publications",
])
def test_matching_contract_survives_in_progress_build(tmp_path, compatibility, provenance, collection):
    store = _store(tmp_path, collection, compatibility)
    connection = store.connection
    client = store._get_client()
    try:
        connection.write_readiness(client, {"ready": True, "provenance": provenance},
                                   collection=collection, compatibility=compatibility)
        before = client.retrieve(collection, ids=[1], with_vectors=True)[0].vector
        store.begin_build(compatibility)
        marker_path = connection.release_path(collection)
        pending = json.loads(marker_path.read_text())
        assert pending["ready"] is False
        assert pending["provenance"] == provenance
        assert connection.read_index_compatibility(collection) == compatibility
        if collection == "ratsi_passages":
            assert not connection.passages_ready(client)
        with pytest.raises(RuntimeError, match="Kompatibilitaetspruefung"):
            store.finish_build(replace(compatibility, manifest_sha256="b" * 64))
        assert json.loads(marker_path.read_text())["ready"] is False
        store.begin_build(compatibility)  # Resume after an interrupted build.
        store.finish_build(compatibility)
        if collection == "ratsi_passages":
            assert connection.passages_ready(client)
        assert json.loads(marker_path.read_text())["provenance"] == provenance
        assert client.retrieve(collection, ids=[1], with_vectors=True)[0].vector == before
    finally:
        store.close()


@pytest.mark.integration
@pytest.mark.parametrize("replacement", ["different_count", "missing_contract", "foreign_contract"])
def test_stale_marker_rejects_replaced_collection_before_writes(tmp_path, compatibility, replacement):
    from qdrant_client.models import PointStruct, SparseVector

    collection = "landkreis_publications"
    store = _store(tmp_path, collection, compatibility)
    client = store._get_client()
    connection = store.connection
    try:
        connection.write_readiness(client, {"ready": True, "provenance": "native"},
                                   collection=collection, compatibility=compatibility)
        marker = connection.release_path(collection).read_bytes()
        client.delete_collection(collection)
        store.ensure_collection()
        payload = {"text": "replaced"}
        if replacement == "foreign_contract":
            payload["index_compatibility"] = replace(compatibility, manifest_sha256="b" * 64).as_dict()
        client.upsert(collection, [PointStruct(
            id=2, vector={"harrier": [1.0] + [0.0] * 1023,
                          "bm25": SparseVector(indices=[1], values=[1.0])}, payload=payload,
        )])
        if replacement == "different_count":
            client.upsert(collection, [PointStruct(
                id=3, vector={"harrier": [1.0] + [0.0] * 1023,
                              "bm25": SparseVector(indices=[1], values=[1.0])},
                payload={"index_compatibility": compatibility.as_dict()},
            )])
        original_upsert = client.upsert
        client.upsert = lambda *args, **kwargs: pytest.fail("Unexpected vector write")
        try:
            with pytest.raises(IndexBuildCompatibilityError, match="Punktbestand"):
                store.begin_build(compatibility)
        finally:
            client.upsert = original_upsert
        assert connection.release_path(collection).read_bytes() == marker
    finally:
        store.close()


@pytest.mark.integration
def test_search_rejects_stale_marker_on_equal_size_replacement(tmp_path, monkeypatch, compatibility):
    from qdrant_client.models import PointStruct, SparseVector

    collection = "ratsi_documents"
    store = _store(tmp_path, collection, compatibility)
    client = store._get_client()
    connection = store.connection
    try:
        connection.write_readiness(client, {"ready": True},
                                   collection=collection, compatibility=compatibility)
        client.delete_collection(collection)
        store.ensure_collection()
        client.upsert(collection, [PointStruct(
            id=2, vector={"harrier": [1.0] + [0.0] * 1023,
                          "bm25": SparseVector(indices=[1], values=[1.0])},
            payload={"text": "foreign"},
        )])
        monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility",
                            lambda: compatibility)
        with pytest.raises(RuntimeError, match="Punktbestand"):
            connection.require_search_compatibility(collection, client)
    finally:
        store.close()


@pytest.mark.integration
@pytest.mark.parametrize("collection", ["ratsi_passages", "ratsi_documents", "landkreis_publications"])
def test_pending_build_resumes_after_new_points(tmp_path, compatibility, collection):
    from qdrant_client.models import PointStruct, SparseVector

    store = _store(tmp_path, collection, compatibility)
    client = store._get_client()
    try:
        store.connection.write_readiness(client, {"ready": True},
                                         collection=collection, compatibility=compatibility)
        store.begin_build(compatibility)
        client.upsert(collection, [PointStruct(
            id=2, vector={"harrier": [0.0, 1.0] + [0.0] * 1022,
                          "bm25": SparseVector(indices=[2], values=[1.0])},
            payload={"index_compatibility": compatibility.as_dict()},
        )])
        assert client.count(collection, exact=True).count == 2
        store.begin_build(compatibility)
        store.finish_build(compatibility)
        assert store.connection.collection_contents_match(client, collection, compatibility)
    finally:
        store.close()


@pytest.mark.integration
def test_landkreis_text_limit_cannot_change_between_incremental_builds(tmp_path, compatibility):
    collection = "landkreis_publications"
    store = _store(tmp_path, collection, compatibility)
    connection = store.connection
    try:
        connection.write_readiness(store._get_client(),
                                   {"ready": True, "build_options": {"max_text_chars": 6000}},
                                   collection=collection, compatibility=compatibility)
        store.begin_build(compatibility, build_options={"max_text_chars": 6000})
        store.finish_build(compatibility, build_options={"max_text_chars": 6000})
        marker = connection.release_path(collection).read_bytes()
        with pytest.raises(IndexBuildCompatibilityError, match="Build-Optionen"):
            store.begin_build(compatibility, build_options={"max_text_chars": 3000})
        assert connection.release_path(collection).read_bytes() == marker
        store.begin_build(compatibility, build_options={"max_text_chars": 6000})
    finally:
        store.close()


@pytest.mark.integration
def test_search_reuses_recent_vector_check_then_revalidates(tmp_path, monkeypatch, compatibility):
    from qdrant_client.models import PointStruct, SparseVector
    from src import qdrant_connection

    collection = "ratsi_documents"
    store = _store(tmp_path, collection, compatibility)
    connection = store.connection
    client = store._get_client()
    try:
        connection.write_readiness(client, {"ready": True},
                                   collection=collection, compatibility=compatibility)
        monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility",
                            lambda: compatibility)
        now = [100.0]
        monkeypatch.setattr(qdrant_connection, "monotonic", lambda: now[0])
        calls = []
        original = QdrantConnection.collection_contents_match

        def checked(self, *args):
            calls.append(True)
            return original(self, *args)

        monkeypatch.setattr(QdrantConnection, "collection_contents_match", checked)
        connection.require_search_compatibility(collection, client)
        connection.require_search_compatibility(collection, client)
        assert len(calls) == 1
        marker_path = connection.release_path(collection)
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["inspection_checked_at"] = "changed"
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        connection.require_search_compatibility(collection, client)
        assert len(calls) == 2
        client.upsert(collection, [PointStruct(
            id=1, vector={"harrier": [0.0, 1.0] + [0.0] * 1022,
                          "bm25": SparseVector(indices=[2], values=[1.0])},
            payload={"index_compatibility": compatibility.as_dict()},
        )])
        now[0] += qdrant_connection._SEARCH_CACHE_SECONDS + 1
        with pytest.raises(RuntimeError, match="Punktbestand"):
            connection.require_search_compatibility(collection, client)
        assert len(calls) == 3
    finally:
        store.close()


@pytest.mark.integration
def test_search_rejects_marker_revoked_between_its_reads(tmp_path, monkeypatch, compatibility):
    collection = "ratsi_documents"
    store = _store(tmp_path, collection, compatibility)
    connection = store.connection
    client = store._get_client()
    try:
        connection.write_readiness(client, {"ready": True},
                                   collection=collection, compatibility=compatibility)
        monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility",
                            lambda: compatibility)
        original = QdrantConnection.read_index_compatibility

        def revoke_after_first_read(self, name, *, require_ready=False):
            result = original(self, name, require_ready=require_ready)
            marker_path = self.release_path(name)
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["ready"] = False
            marker_path.write_text(json.dumps(marker), encoding="utf-8")
            return result

        monkeypatch.setattr(QdrantConnection, "read_index_compatibility", revoke_after_first_read)
        monkeypatch.setattr(QdrantConnection, "collection_contents_match",
                            lambda *args: pytest.fail("Pending marker must reject before scanning"))
        with pytest.raises(RuntimeError, match="nicht freigegeben"):
            connection.require_search_compatibility(collection, client)
    finally:
        store.close()


@pytest.mark.integration
def test_copied_payload_with_foreign_vector_rejects_build_and_search(
    tmp_path, monkeypatch, compatibility,
):
    from qdrant_client.models import PointStruct, SparseVector

    collection = "ratsi_documents"
    store = _store(tmp_path, collection, compatibility)
    client = store._get_client()
    connection = store.connection
    try:
        connection.write_readiness(client, {"ready": True},
                                   collection=collection, compatibility=compatibility)
        marker = connection.release_path(collection).read_bytes()
        client.delete_collection(collection)
        store.ensure_collection()
        client.upsert(collection, [PointStruct(
            id=1, vector={"harrier": [0.0, 1.0] + [0.0] * 1022,
                          "bm25": SparseVector(indices=[2], values=[1.0])},
            payload={"index_compatibility": compatibility.as_dict(), "text": "legacy"},
        )])
        with pytest.raises(IndexBuildCompatibilityError, match="Punktbestand"):
            store.begin_build(compatibility)
        monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility",
                            lambda: compatibility)
        with pytest.raises(RuntimeError, match="Punktbestand"):
            connection.require_search_compatibility(collection, client)
        assert connection.release_path(collection).read_bytes() == marker
    finally:
        store.close()


@pytest.mark.integration
def test_different_contract_rejects_existing_collection_without_marker_change(
    tmp_path, compatibility,
):
    store = _store(tmp_path, "landkreis_publications")
    connection = store.connection
    try:
        connection.write_readiness(store._get_client(), {"provenance": "native"},
                                   collection="landkreis_publications", compatibility=compatibility)
        old_marker = connection.release_path("landkreis_publications").read_bytes()
        other = replace(compatibility, manifest_sha256="b" * 64)
        with pytest.raises(IndexBuildCompatibilityError, match="anderen Modell"):
            store.begin_build(other)
        assert connection.release_path("landkreis_publications").read_bytes() == old_marker
    finally:
        store.close()


@pytest.mark.integration
@pytest.mark.parametrize("schema", ["dimension", "distance", "vectors", "sparse"])
@pytest.mark.parametrize("empty", [False, True])
def test_stale_marker_does_not_authorize_recreated_collection_schema(
    tmp_path, compatibility, schema, empty,
):
    from qdrant_client.models import Distance, PointStruct, SparseVectorParams, VectorParams

    collection = "landkreis_publications"
    store = _store(tmp_path, collection)
    client = store._get_client()
    connection = store.connection
    try:
        connection.write_readiness(client, {"ready": True, "provenance": "native"},
                                   collection=collection, compatibility=compatibility)
        marker_before = connection.release_path(collection).read_bytes()
        client.delete_collection(collection)
        name = "other" if schema == "vectors" else "harrier"
        dimension = 3 if schema == "dimension" else compatibility.vector_dimension
        distance = Distance.DOT if schema == "distance" else Distance.COSINE
        sparse = {} if schema == "sparse" else {"bm25": SparseVectorParams()}
        client.create_collection(
            collection,
            vectors_config={name: VectorParams(size=dimension, distance=distance)},
            sparse_vectors_config=sparse,
        )
        if not empty:
            client.upsert(collection, [PointStruct(
                id=1, vector={name: [1.0] + [0.0] * (dimension - 1)}, payload={"text": "existing"},
            )])
        original_set_payload = client.set_payload
        client.set_payload = lambda *args, **kwargs: pytest.fail("Unexpected payload write")
        try:
            with pytest.raises(IndexBuildCompatibilityError, match="Vektorschema"):
                store.begin_build(compatibility)
        finally:
            client.set_payload = original_set_payload
        assert connection.release_path(collection).read_bytes() == marker_before
        assert client.count(collection, exact=True).count == (0 if empty else 1)
    finally:
        store.close()


@pytest.mark.integration
@pytest.mark.parametrize("builder,collection", [
    ("passages", "ratsi_passages"),
    ("legacy", "ratsi_documents"),
    ("landkreis", "landkreis_publications"),
])
@pytest.mark.parametrize("marker_state", ["missing", "different"])
def test_build_cli_reports_incompatible_continuation_without_traceback_or_writes(
    tmp_path, monkeypatch, capsys, compatibility, builder, collection, marker_state,
):
    from scripts import build_landkreis_vector_index, build_vector_index
    from src.indexing import passage_builder
    from src.qdrant_connection import QdrantConnection

    store = _store(tmp_path, collection)
    client = store._get_client()
    target = QdrantConnection(tmp_path / "target")
    if marker_state == "different":
        other = replace(compatibility, manifest_sha256="b" * 64)
        target.write_readiness(client, {"provenance": "native"},
                               collection=collection, compatibility=other)
    marker_path = target.release_path(collection)
    original_marker = marker_path.read_bytes() if marker_path.exists() else None
    monkeypatch.setattr(QdrantConnection, "create_client", lambda self: client)
    monkeypatch.setattr(client, "upsert", lambda *args, **kwargs: pytest.fail("Vector write"))
    monkeypatch.setattr(client, "set_payload", lambda *args, **kwargs: pytest.fail("Payload write"))
    monkeypatch.setattr(client, "create_collection", lambda *args, **kwargs: pytest.fail("Collection write"))
    db = tmp_path / "input.sqlite"
    db.touch()
    args = ["--db", str(db), "--qdrant-dir", str(target.path)]
    if builder == "landkreis":
        module = build_landkreis_vector_index
        monkeypatch.setattr(module, "_validate_runtime_dependencies", lambda: (object, DocumentVectorStore))
    else:
        module = build_vector_index
        if builder == "legacy":
            args.append("--legacy-document-index")
            monkeypatch.setattr(module, "_validate_runtime_dependencies", lambda: (object, DocumentVectorStore))
        else:
            monkeypatch.setattr(passage_builder, "current_index_compatibility", lambda: compatibility)
    if builder != "passages":
        monkeypatch.setattr(module, "current_index_compatibility", lambda: compatibility)

    try:
        with pytest.raises(SystemExit) as error:
            module.main(args)
        assert error.value.code == 1
        message = capsys.readouterr().err
        assert message.startswith(f"ERROR: Index {collection} inkompatibel:")
        assert "Neuaufbau oder getrennte Aufbau-Collection" in message
        assert message.count("\n") == 1
        assert "Traceback" not in message
        assert (marker_path.read_bytes() if marker_path.exists() else None) == original_marker
    finally:
        if builder != "passages":
            store.close()
