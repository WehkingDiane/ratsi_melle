"""Backend routing and readiness regression tests; no production connections."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest

from src.analysis.vector_store import DocumentVectorStore
from src.config.settings import QdrantSettingsError, load_qdrant_settings
from src.qdrant_connection import QdrantConnection, collection_state, probe_qdrant

# Capture the real factory before the autouse isolation fixture replaces it.
CREATE_CLIENT = QdrantConnection.create_client


def point(pid=1, committed=True):
    return {"id": pid, "dense_vector": [1.0] + [0.0] * 1023,
            "sparse_vector": {"indices": [1], "values": [1.0]},
            "payload": {"document_id": 10, "committed": committed,
                        "chunk_count": 1, "chunk_index": 0, "generation": "first",
                        "text": "Test", "title": "Title", "session_id": "1"}}


@pytest.fixture
def remote(monkeypatch):
    from qdrant_client import QdrantClient
    client = QdrantClient(":memory:")
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333")
    monkeypatch.setattr(QdrantConnection, "create_client", lambda self: client)
    # Multiple stores/status requests share a simulated server without closing it.
    close = client.close
    monkeypatch.setattr(client, "close", lambda: None)
    yield client
    close()


def test_factory_url_precedes_path_and_never_creates_local_directory(tmp_path, monkeypatch):
    factory = Mock()
    monkeypatch.setattr("qdrant_client.QdrantClient", factory)
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333/")
    config = QdrantConnection.from_env(tmp_path / "absent")
    CREATE_CLIENT(config)
    factory.assert_called_once_with(url="http://test.invalid:6333", timeout=10)
    assert not config.path.exists()


def test_failed_server_does_not_fall_back(tmp_path, monkeypatch):
    factory = Mock()
    factory.return_value.get_collections.side_effect = OSError("connection refused")
    monkeypatch.setattr("qdrant_client.QdrantClient", factory)
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333")
    with pytest.raises(RuntimeError, match="Server nicht erreichbar"):
        CREATE_CLIENT(QdrantConnection.from_env(tmp_path / "absent"))
    assert factory.call_count == 1
    factory.return_value.close.assert_called_once()
    assert not (tmp_path / "absent").exists()


def test_factory_local_fallback(tmp_path, monkeypatch):
    factory = Mock()
    monkeypatch.setattr("qdrant_client.QdrantClient", factory)
    config = QdrantConnection.from_env(tmp_path / "local")
    CREATE_CLIENT(config)
    factory.assert_called_once_with(path=str(tmp_path / "local"))


def test_default_connection_uses_server(tmp_path, monkeypatch):
    monkeypatch.delenv("RATSI_QDRANT_MODE")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    factory = Mock()
    monkeypatch.setattr("qdrant_client.QdrantClient", factory)
    config = QdrantConnection.from_env(tmp_path / "not-created")
    CREATE_CLIENT(config)
    factory.assert_called_once_with(url="http://127.0.0.1:6333", timeout=10)
    assert not config.path.exists()


def test_explicit_local_mode_uses_path_without_server_url(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSI_QDRANT_MODE", "local")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    assert QdrantConnection.from_env(tmp_path / "local").url == ""


@pytest.mark.parametrize("name,value", [
    ("RATSI_QDRANT_MODE", "other"),
    ("RATSI_QDRANT_URL", "ftp://example.test"),
    ("RATSI_QDRANT_URL", "http://example.test:invalid"),
    ("RATSI_QDRANT_URL", "http://example.test/?token=secret"),
    ("RATSI_QDRANT_STATE_DIR", ""),
])
def test_invalid_qdrant_settings_do_not_echo_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(QdrantSettingsError) as error:
        load_qdrant_settings()
    if value:
        assert value not in str(error.value)


def test_credential_url_is_used_only_for_connection_and_hashed_marker(tmp_path, monkeypatch):
    secret = "test-password"
    url = f"https://user:{secret}@example.test:6333/prefix"
    monkeypatch.setenv("RATSI_QDRANT_URL", url)
    config = QdrantConnection.from_env(tmp_path / "absent")
    factory = Mock()
    monkeypatch.setattr("qdrant_client.QdrantClient", factory)
    factory.return_value.get_collections.side_effect = OSError(url)

    with pytest.raises(RuntimeError) as error:
        CREATE_CLIENT(config)
    factory.assert_called_once_with(url=url, timeout=10)
    assert secret not in config.target
    assert secret not in repr(config)
    assert secret not in repr(load_qdrant_settings())
    assert "/prefix" not in config.target
    assert secret not in str(error.value)

    client = Mock()
    client.count.return_value.count = 1
    config.write_readiness(client, {})
    marker = config.ready_path.read_text(encoding="utf-8")
    assert secret not in marker
    assert "url_sha256" in marker


def test_invalid_qdrant_configuration_is_unavailable_in_vector_status(tmp_path, monkeypatch):
    from src.indexing.vector_status import landkreis_vector_index_status, vector_index_status

    monkeypatch.setenv("RATSI_QDRANT_MODE", "invalid")
    for status_fn in (vector_index_status, landkreis_vector_index_status):
        status = status_fn(tmp_path / "absent.sqlite", tmp_path / "absent")
        assert status["status"] == "unavailable"
        assert status["qdrant_exists"] is False
        assert "RATSI_QDRANT_MODE" in status["warnings"][0] or any(
            "RATSI_QDRANT_MODE" in warning for warning in status["warnings"]
        )


@pytest.mark.integration
def test_default_vector_build_targets_server(tmp_path, monkeypatch):
    from qdrant_client import QdrantClient
    from scripts import build_vector_index

    monkeypatch.delenv("RATSI_QDRANT_MODE")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    client = QdrantClient(":memory:")
    targets = []

    def test_client(connection):
        targets.append(connection.url)
        return client

    monkeypatch.setattr(QdrantConnection, "create_client", test_client)
    monkeypatch.setattr(build_vector_index, "_load_documents", lambda db: [])
    monkeypatch.setitem(__import__("sys").modules, "transformers", SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda model, **kwargs: Mock())))
    db = tmp_path / "documents.sqlite"
    db.touch()
    build_vector_index.main(["--db", str(db), "--qdrant-dir", str(tmp_path / "unused")])
    assert targets == ["http://127.0.0.1:6333"]
    assert not (tmp_path / "unused").exists()


@pytest.mark.integration
def test_marker_is_scoped_to_server_and_committed_data(tmp_path, monkeypatch, remote):
    local = tmp_path / "old"
    local.mkdir()
    (local / "ratsi_passages.ready.json").write_text('{}')
    store = DocumentVectorStore(local, "ratsi_passages")
    store.ensure_collection()
    store.upsert_batch([point()])
    config = store.connection
    assert not config.passages_ready(remote)
    assert collection_state(config, remote)["state"] == "incomplete"
    config.write_readiness(remote, {"model": "test"})
    assert config.passages_ready(remote)
    assert collection_state(config, remote)["collection_name"] == "ratsi_passages"
    store.upsert_batch([point(2, committed=False)])
    assert not config.passages_ready(remote)
    store.delete_ids({2})
    assert config.passages_ready(remote)
    # Same point count but lost committed flags must also revoke readiness.
    store.upsert_batch([point(1, committed=False)])
    assert not config.passages_ready(remote)
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://different.invalid:6333")
    assert not QdrantConnection.from_env(local).passages_ready(remote)
    config.clear_readiness()
    assert (local / "ratsi_passages.ready.json").is_file()


@pytest.mark.integration
def test_status_matches_search_fallback_and_missing_collection(tmp_path, remote):
    from src.indexing.vector_status import vector_index_status, landkreis_vector_index_status
    directory = tmp_path / "never-created"
    legacy = DocumentVectorStore(directory)
    legacy.ensure_collection()
    legacy.upsert_batch([point()])
    passages = DocumentVectorStore(directory, "ratsi_passages")
    passages.ensure_collection()
    passages.upsert_batch([point()])
    legacy.prefer_passages()
    assert legacy.collection_name == "ratsi_documents"
    status = vector_index_status(tmp_path / "missing.sqlite", directory)
    assert status["collection_name"] == legacy.collection_name
    assert status["status"] == "incomplete"
    passages.connection.write_readiness(remote, {})
    legacy.prefer_passages()
    status = vector_index_status(tmp_path / "missing.sqlite", directory)
    assert legacy.collection_name == status["collection_name"] == "ratsi_passages"
    assert status["indexed_document_count"] == 1
    county = landkreis_vector_index_status(tmp_path / "missing.sqlite", directory)
    assert county["status"] == "missing_collection"
    assert not directory.exists()


def test_server_status_unreachable_is_distinct(tmp_path, monkeypatch):
    from src.indexing.vector_status import vector_index_status
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333")
    monkeypatch.setattr(QdrantConnection, "create_client", Mock(side_effect=OSError("offline")))
    status = vector_index_status(tmp_path / "missing.sqlite", tmp_path / "absent")
    assert status["status"] == "server_unreachable"
    assert not status["qdrant_exists"]
    assert probe_qdrant(QdrantConnection.from_env(tmp_path / "absent"))["state"] == "server_unreachable"


def test_status_survives_client_cleanup_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333")
    client = Mock()
    client.get_collections.side_effect = OSError("offline")
    client.close.side_effect = OSError("cleanup failed")
    monkeypatch.setattr(QdrantConnection, "create_client", lambda self: client)

    status = probe_qdrant(QdrantConnection.from_env(tmp_path / "absent"))

    assert status["state"] == "server_unreachable"
    assert status["available"] is False


@pytest.mark.integration
def test_explicit_evaluation_collection_is_preserved(tmp_path, remote):
    legacy = DocumentVectorStore(tmp_path / "absent")
    legacy.ensure_collection()
    legacy.upsert_batch([point()])
    passages = DocumentVectorStore(tmp_path / "absent", "ratsi_passages")
    passages.ensure_collection()
    passages.upsert_batch([point()])
    passages.connection.write_readiness(remote, {})
    legacy.require_available()
    assert legacy.collection_name == "ratsi_documents"
    legacy.require_available(prefer_passages=True)
    assert legacy.collection_name == "ratsi_passages"


@pytest.mark.integration
def test_tiny_migration_and_return_to_local(tmp_path, monkeypatch, remote):
    from qdrant_client import QdrantClient
    from qdrant_client.migrate import migrate
    source = QdrantClient(path=str(tmp_path / "source"))
    restored = QdrantClient(path=str(tmp_path / "restored"))
    try:
        monkeypatch.delenv("RATSI_QDRANT_URL")
        original = DocumentVectorStore(tmp_path / "source", "ratsi_passages")
        original._client = source
        original.ensure_collection()
        original.upsert_batch([point(), point(2, committed=False)])
        expected = original.search(point()["dense_vector"], point()["sparse_vector"], session_id="1")
        migrate(source, remote, collection_names=["ratsi_passages"], recreate_on_collision=False)
        monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333")
        migrated = DocumentVectorStore(tmp_path / "absent", "ratsi_passages")
        assert migrated.search(point()["dense_vector"], point()["sparse_vector"], session_id="1") == expected
        migrate(remote, restored, collection_names=["ratsi_passages"], recreate_on_collision=False)
        monkeypatch.delenv("RATSI_QDRANT_URL")
        back = DocumentVectorStore(tmp_path / "restored", "ratsi_passages")
        back._client = restored
        assert back.search(point()["dense_vector"], point()["sparse_vector"], session_id="1") == expected
        assert source.count("ratsi_passages").count == restored.count("ratsi_passages").count == 2
    finally:
        source.close()
        restored.close()


@pytest.mark.integration
@pytest.mark.parametrize('module_name,collection', [
    ('scripts.build_vector_index', 'ratsi_documents'),
    ('scripts.build_landkreis_vector_index', 'landkreis_publications'),
])
def test_legacy_and_county_builds_use_configured_server(tmp_path, monkeypatch, remote, module_name, collection):
    import importlib
    module = importlib.import_module(module_name)
    db = tmp_path / 'input.sqlite'
    db.touch()
    monkeypatch.setattr(module, '_load_documents', lambda db: [])
    monkeypatch.setattr(module, '_validate_runtime_dependencies', lambda: (Mock, DocumentVectorStore))
    args = ['--db', str(db), '--qdrant-dir', str(tmp_path / 'absent')]
    if collection == 'ratsi_documents':
        args.append('--legacy-document-index')
    module.main(args)
    assert collection in {c.name for c in remote.get_collections().collections}
    assert not (tmp_path / 'absent').exists()


@pytest.mark.integration
def test_passage_build_only_marks_complete_current_documents(tmp_path, monkeypatch, remote):
    import sys
    from src.indexing import passage_builder
    from scripts import build_vector_index
    from test_passage_index import Tokenizer, Vectorizer, document
    db = tmp_path / 'input.sqlite'
    db.touch()
    doc, source = document(tmp_path)
    docs = [doc, {**doc, 'id': 2, 'url': 'https://example.org/second'}]
    monkeypatch.setattr(build_vector_index, '_load_documents', lambda db: docs)
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda model, **kwargs: Tokenizer())))
    monkeypatch.setattr(passage_builder, 'HybridVectorizer', lambda *args: Vectorizer())
    args = ['--db', str(db), '--qdrant-dir', str(tmp_path / 'absent')]
    passage_builder.main(args)
    config = QdrantConnection.from_env(tmp_path / 'absent')
    assert config.passages_ready(remote)
    source.write_text('Changed document source')
    passage_builder.main(args + ['--limit', '1'])
    assert not config.ready_path.exists()
    passage_builder.main(args + ['--limit', '1'])
    assert config.passages_ready(remote)
    assert not (tmp_path / 'absent').exists()


def test_runtime_read_failures_are_not_reported_as_empty_index(tmp_path):
    store = DocumentVectorStore(tmp_path / 'index')
    store._client = Mock()
    store._client.get_collection.side_effect = OSError('offline')
    store._client.scroll.side_effect = OSError('offline')
    for read in (store.count, store.get_indexed_ids, lambda: store.get_ids_with_payload_field('snippet')):
        with pytest.raises(RuntimeError, match='Collection nicht lesbar'):
            read()


@pytest.mark.integration
def test_empty_collection_is_incomplete(tmp_path, remote):
    store = DocumentVectorStore(tmp_path / 'absent')
    store.ensure_collection()
    with pytest.raises(RuntimeError, match='Index unvollständig'):
        store.require_available(prefer_passages=True)
    assert probe_qdrant(store.connection)['state'] == 'incomplete'


@pytest.mark.integration
def test_evaluation_cli_uses_server_without_local_storage(tmp_path, monkeypatch, remote):
    from scripts import evaluate_search, build_vector_index
    store = DocumentVectorStore(tmp_path / 'absent', 'ratsi_passages')
    store.ensure_collection()
    store.upsert_batch([point()])
    db = tmp_path / 'input.sqlite'
    db.touch()
    benchmark = tmp_path / 'benchmark.json'
    benchmark.write_text(json.dumps({'queries': [{'id': 'q', 'query': 'Test',
        'relevant': [{'url': '', 'page': None, 'evidence': 'Test'}]}]}))
    monkeypatch.setattr(build_vector_index, '_load_documents', lambda db: [])
    monkeypatch.setattr(evaluate_search, 'validate_sources', lambda *args: [])
    monkeypatch.setattr('src.analysis.embeddings.HarrierEmbedder', lambda: SimpleNamespace(
        embed_query=lambda text: point()['dense_vector']))
    monkeypatch.setattr('src.analysis.bm25_sparse.BM25Encoder', lambda: SimpleNamespace(
        encode_query=lambda text: point()['sparse_vector']))
    output = tmp_path / 'report.json'
    evaluate_search.main(['--db', str(db), '--benchmark', str(benchmark),
                          '--qdrant-dir', str(tmp_path / 'absent'), '--output', str(output)])
    report = json.loads(output.read_text())
    assert report['indexed_points'] == 1
    assert report['metrics']['hit_at_k'] == 1
    assert not (tmp_path / 'absent').exists()
