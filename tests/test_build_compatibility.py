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


def _store(tmp_path, collection):
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
        payload={"text": "legacy"},
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
def test_matching_contract_survives_in_progress_build(tmp_path, compatibility, provenance):
    store = _store(tmp_path, "ratsi_passages")
    connection = store.connection
    client = store._get_client()
    try:
        connection.write_readiness(client, {"provenance": provenance},
                                   compatibility=compatibility)
        before = client.retrieve("ratsi_passages", ids=[1], with_vectors=True)[0].vector
        store.begin_build(compatibility)
        pending = json.loads(connection.ready_path.read_text())
        assert pending["ready"] is False
        assert pending["provenance"] == provenance
        assert connection.read_index_compatibility("ratsi_passages") == compatibility
        assert not connection.passages_ready(client)
        with pytest.raises(RuntimeError, match="Kompatibilitaetspruefung"):
            store.finish_build(replace(compatibility, manifest_sha256="b" * 64))
        assert not connection.passages_ready(client)
        store.begin_build(compatibility)  # Resume after an interrupted build.
        store.finish_build(compatibility)
        assert connection.passages_ready(client)
        assert json.loads(connection.ready_path.read_text())["provenance"] == provenance
        assert client.retrieve("ratsi_passages", ids=[1], with_vectors=True)[0].vector == before
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
