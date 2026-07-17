from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

from scripts import build_landkreis_vector_index
from scripts import build_vector_index
from src.indexing.id_strategy import stable_document_id
from src.indexing.payload_builder import build_document_payload, resolve_local_path
from src.indexing.reconciliation import find_orphaned_ids
from src.indexing.vectorizer import HybridVectorizer
from src.analysis.vector_store import DocumentVectorStore


class _FakeVectorStore:
    def __init__(self, indexed_ids: set[int], count: int) -> None:
        self._indexed_ids = set(indexed_ids)
        self._count = count
        self.deleted_ids: list[set[int]] = []
        self.upserted_batches: list[list[dict]] = []

    def ensure_collection(self) -> None:
        pass

    def get_indexed_ids(self) -> set[int]:
        return set(self._indexed_ids)

    def delete_ids(self, ids: set[int]) -> None:
        self.deleted_ids.append(set(ids))

    def count(self) -> int:
        return self._count

    def upsert_batch(self, points: list[dict]) -> None:
        self.upserted_batches.append(points)


def _install_fake_modules(monkeypatch, vector_store: _FakeVectorStore) -> None:
    embeddings_module = ModuleType("src.analysis.embeddings")

    class _FakeHarrierEmbedder:
        def __init__(self) -> None:  # pragma: no cover - should not be reached here
            raise AssertionError("Embedder should not be initialized in these tests")

    embeddings_module.HarrierEmbedder = _FakeHarrierEmbedder
    embeddings_module._detect_device = lambda: "cpu"

    vector_store_module = ModuleType("src.analysis.vector_store")
    vector_store_module.DocumentVectorStore = lambda _path: vector_store

    bm25_module = ModuleType("src.analysis.bm25_sparse")

    class _FakeBM25Encoder:
        def __init__(self) -> None:  # pragma: no cover - should not be reached here
            raise AssertionError("BM25 should not be initialized in these tests")

    bm25_module.BM25Encoder = _FakeBM25Encoder

    monkeypatch.setitem(sys.modules, "src.analysis.embeddings", embeddings_module)
    monkeypatch.setitem(sys.modules, "src.analysis.vector_store", vector_store_module)
    monkeypatch.setitem(sys.modules, "src.analysis.bm25_sparse", bm25_module)


def _doc(session_id: str, url: str, agenda_item: str = "") -> dict:
    return {
        "session_id": session_id,
        "url": url,
        "title": f"Doc {session_id}",
        "document_type": "protokoll",
        "agenda_item": agenda_item,
        "local_path": "",
        "date": "2025-01-01",
        "committee": "Rat",
        "session_path": "",
    }


def test_stable_qdrant_id_distinguishes_duplicate_urls_by_agenda_item() -> None:
    url = "https://example.org/shared.pdf"

    top_1 = build_vector_index._stable_qdrant_id("1", url, "Ö 1")
    top_2 = build_vector_index._stable_qdrant_id("1", url, "Ö 2")
    session_doc = build_vector_index._stable_qdrant_id("1", url, "")
    session_doc_none = build_vector_index._stable_qdrant_id("1", url, "")

    assert top_1 != top_2
    assert top_1 != session_doc
    assert top_2 != session_doc
    assert session_doc == session_doc_none


def test_document_vector_store_defaults_to_ratsinfo_collection(tmp_path: Path) -> None:
    store = DocumentVectorStore(tmp_path / "qdrant")

    assert store.collection_name == "ratsi_documents"


def test_document_vector_store_accepts_custom_collection(tmp_path: Path) -> None:
    store = DocumentVectorStore(tmp_path / "qdrant", collection_name="landkreis_publications")

    assert store.collection_name == "landkreis_publications"


def test_stable_document_id_is_deterministic_and_sensitive_to_inputs() -> None:
    base = stable_document_id("901", "https://example.org/doc.pdf", "Oe 1")

    assert stable_document_id("901", "https://example.org/doc.pdf", "Oe 1") == base
    assert stable_document_id("902", "https://example.org/doc.pdf", "Oe 1") != base
    assert stable_document_id("901", "https://example.org/other.pdf", "Oe 1") != base


def test_landkreis_stable_qdrant_id_uses_publication_and_document_url() -> None:
    base = build_landkreis_vector_index._stable_landkreis_qdrant_id(
        "pub-1",
        "https://example.org/doc.pdf",
    )

    assert build_landkreis_vector_index._stable_landkreis_qdrant_id("pub-1", "https://example.org/doc.pdf") == base
    assert build_landkreis_vector_index._stable_landkreis_qdrant_id("pub-2", "https://example.org/doc.pdf") != base
    assert build_landkreis_vector_index._stable_landkreis_qdrant_id("pub-1", "https://example.org/other.pdf") != base


def test_landkreis_load_documents_uses_only_local_documents_and_extracted_text(tmp_path: Path) -> None:
    db_path = tmp_path / "landkreis.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE publications (
                publication_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                date TEXT,
                title TEXT NOT NULL
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                publication_id TEXT NOT NULL,
                title TEXT,
                url TEXT NOT NULL,
                local_path TEXT
            );
            CREATE TABLE extracted_texts (
                document_id INTEGER PRIMARY KEY,
                extracted_text TEXT
            );
            INSERT INTO publications VALUES ('pub-1', 'amtsblaetter', '2026-03-11', 'Amtsblatt 10');
            INSERT INTO documents VALUES (1, 'pub-1', 'PDF Anlage', 'https://example.org/a.pdf', 'amtsblatt/a.pdf');
            INSERT INTO documents VALUES (2, 'pub-1', 'Nur Link', 'https://example.org/b.pdf', '');
            INSERT INTO extracted_texts VALUES (1, 'Extrahierter Landkreis-Text');
            """
        )

    rows = build_landkreis_vector_index._load_documents(db_path)

    assert len(rows) == 1
    assert rows[0]["publication_id"] == "pub-1"
    assert rows[0]["document_title"] == "PDF Anlage"
    assert build_landkreis_vector_index._document_text(rows[0]) == "Extrahierter Landkreis-Text"


def test_landkreis_document_text_is_truncated_for_embedding() -> None:
    text = build_landkreis_vector_index._document_text(
        {"extracted_text": "eins zwei drei vier"},
        max_chars=11,
    )

    assert text == "eins zwei"


def test_landkreis_main_indexes_missing_documents_and_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc = {
        "publication_id": "pub-1",
        "source": "amtsblaetter",
        "title": "Amtsblatt 10",
        "document_title": "PDF Anlage",
        "date": "2026-03-11",
        "url": "https://example.org/a.pdf",
        "local_path": "amtsblaetter/2026/a.pdf",
        "extracted_text": "Extrahierter Landkreis-Text",
    }
    vector_store = _FakeVectorStore(indexed_ids=set(), count=1)
    captured: dict[str, object] = {}

    class _FakeHarrierEmbedder:
        pass

    class _FakeDocumentVectorStore:
        def __new__(cls, path, collection_name=""):
            captured["qdrant_path"] = path
            captured["collection_name"] = collection_name
            return vector_store

    class _FakeBM25Encoder:
        def _get_model(self) -> None:
            pass

    class _FakeHybridVectorizer:
        def __init__(self, _embedder, _bm25) -> None:
            pass

        def encode_documents(self, texts: list[str]) -> list[dict]:
            captured["texts"] = texts
            return [
                {
                    "dense_vector": [0.0] * 1024,
                    "sparse_vector": {"indices": [index], "values": [1.0]},
                }
                for index, _text in enumerate(texts)
            ]

    embeddings_module = ModuleType("src.analysis.embeddings")
    embeddings_module._detect_device = lambda: "cpu"
    bm25_module = ModuleType("src.analysis.bm25_sparse")
    bm25_module.BM25Encoder = _FakeBM25Encoder
    monkeypatch.setitem(sys.modules, "src.analysis.embeddings", embeddings_module)
    monkeypatch.setitem(sys.modules, "src.analysis.bm25_sparse", bm25_module)
    monkeypatch.setattr(
        build_landkreis_vector_index,
        "_validate_runtime_dependencies",
        lambda: (_FakeHarrierEmbedder, _FakeDocumentVectorStore),
    )
    monkeypatch.setattr(build_landkreis_vector_index, "HybridVectorizer", _FakeHybridVectorizer)
    monkeypatch.setattr(build_landkreis_vector_index, "_load_documents", lambda _db_path: [doc])
    monkeypatch.setattr(build_landkreis_vector_index, "LANDKREIS_DATA_DIR", tmp_path / "raw-landkreis")

    db_path = tmp_path / "landkreis.sqlite"
    db_path.write_text("", encoding="utf-8")

    build_landkreis_vector_index.main(
        [
            "--db",
            str(db_path),
            "--qdrant-dir",
            str(tmp_path / "qdrant"),
            "--max-text-chars",
            "12",
        ]
    )

    assert captured["collection_name"] == build_landkreis_vector_index.COLLECTION_NAME
    assert captured["texts"] == ["Extrahierter"]
    assert len(vector_store.upserted_batches) == 1
    point = vector_store.upserted_batches[0][0]
    assert point["id"] == build_landkreis_vector_index._stable_landkreis_qdrant_id("pub-1", "https://example.org/a.pdf")
    assert point["payload"]["source_system"] == "landkreis"
    assert point["payload"]["publication_id"] == "pub-1"
    assert point["payload"]["source"] == "amtsblaetter"
    assert point["payload"]["document_title"] == "PDF Anlage"
    assert point["payload"]["local_path"].endswith("raw-landkreis/amtsblaetter/2026/a.pdf")


def test_landkreis_main_skips_indexed_and_deletes_orphans_only_without_limit(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    doc = {
        "publication_id": "pub-1",
        "source": "amtsblaetter",
        "title": "Amtsblatt 10",
        "document_title": "PDF Anlage",
        "date": "2026-03-11",
        "url": "https://example.org/a.pdf",
        "local_path": "a.pdf",
        "extracted_text": "",
    }
    current_id = build_landkreis_vector_index._stable_landkreis_qdrant_id("pub-1", "https://example.org/a.pdf")
    orphan_id = 123456
    vector_store = _FakeVectorStore(indexed_ids={current_id, orphan_id}, count=2)

    class _FakeDocumentVectorStore:
        def __new__(cls, _path, collection_name=""):
            return vector_store

    monkeypatch.setattr(
        build_landkreis_vector_index,
        "_validate_runtime_dependencies",
        lambda: (object, _FakeDocumentVectorStore),
    )
    monkeypatch.setattr(build_landkreis_vector_index, "_load_documents", lambda _db_path: [doc])
    db_path = tmp_path / "landkreis.sqlite"
    db_path.write_text("", encoding="utf-8")

    build_landkreis_vector_index.main(["--db", str(db_path), "--qdrant-dir", str(tmp_path / "qdrant")])

    assert vector_store.upserted_batches == []
    assert vector_store.deleted_ids == [{orphan_id}]
    assert "Nothing to index" in capsys.readouterr().out

    vector_store.deleted_ids.clear()
    build_landkreis_vector_index.main(
        [
            "--db",
            str(db_path),
            "--qdrant-dir",
            str(tmp_path / "qdrant"),
            "--limit",
            "1",
        ]
    )

    assert vector_store.deleted_ids == []
    assert "Skipping orphan cleanup because --limit is set." in capsys.readouterr().out


def test_get_document_text_resolves_legacy_session_paths(tmp_path: Path, monkeypatch) -> None:
    session_dir = tmp_path / "data" / "raw" / "2025" / "09" / "2025-09-18_Rat_901"
    pdf_path = session_dir / "session-documents" / "protokoll.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"pdf")

    monkeypatch.setattr(build_vector_index, "_extract_text_pypdf", lambda path: f"TEXT:{path.name}")

    text = build_vector_index._get_document_text(
        {
            "session_path": str(tmp_path / "data" / "raw" / "2025" / "2025-09-18_Rat_901"),
            "local_path": r"session-documents\protokoll.pdf",
            "title": "Fallback title",
            "document_type": "protokoll",
        }
    )

    assert text == "TEXT:protokoll.pdf"


def test_resolved_payload_local_path_uses_storage_helper(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2025" / "09" / "2025-09-18_Rat_901"
    pdf_path = session_dir / "session-documents" / "protokoll.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"pdf")

    resolved = build_vector_index._resolved_payload_local_path(
        {
            "session_path": str(tmp_path / "data" / "raw" / "2025" / "2025-09-18_Rat_901"),
            "local_path": r"session-documents\protokoll.pdf",
        }
    )

    assert resolved == str(pdf_path.resolve())


def test_build_document_payload_preserves_existing_fields(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2025" / "09" / "2025-09-18_Rat_901"
    pdf_path = session_dir / "session-documents" / "vorlage.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"pdf")

    assert resolve_local_path(
        {
            "session_path": str(tmp_path / "data" / "raw" / "2025" / "2025-09-18_Rat_901"),
            "local_path": r"session-documents\vorlage.pdf",
        }
    ) == str(pdf_path.resolve())

    payload = build_document_payload(
        {
            "session_id": "901",
            "title": "Vorlage",
            "document_type": "beschlussvorlage",
            "agenda_item": "Oe 1",
            "url": "https://example.org/vorlage.pdf",
            "local_path": r"session-documents\vorlage.pdf",
            "date": "2025-09-18",
            "committee": "Rat",
            "session_path": str(tmp_path / "data" / "raw" / "2025" / "2025-09-18_Rat_901"),
        }
    )

    assert payload == {
        "session_id": "901",
        "title": "Vorlage",
        "document_type": "beschlussvorlage",
        "agenda_item": "Oe 1",
        "url": "https://example.org/vorlage.pdf",
        "local_path": str(pdf_path.resolve()),
        "date": "2025-09-18",
        "committee": "Rat",
    }


def test_build_document_payload_uses_empty_path_for_missing_file() -> None:
    payload = build_document_payload(
        {
            "session_id": "901",
            "title": None,
            "document_type": None,
            "agenda_item": None,
            "url": None,
            "local_path": "missing.pdf",
            "date": None,
            "committee": None,
            "session_path": "",
        }
    )

    assert payload["local_path"] == ""
    assert payload["title"] == ""
    assert payload["url"] == ""


def test_find_orphaned_ids_returns_indexed_ids_missing_from_current_set() -> None:
    assert find_orphaned_ids({1, 2, 3}, {2, 3, 4}) == {1}
    assert find_orphaned_ids({1, 2}, {1, 2}) == set()
    assert find_orphaned_ids(set(), {1}) == set()


def test_hybrid_vectorizer_combines_dense_and_sparse_vectors_by_order() -> None:
    class Dense:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[float(index)] for index, _text in enumerate(texts)]

    class Sparse:
        def encode_documents(self, texts: list[str]) -> list[dict]:
            return [
                {"indices": [index], "values": [float(len(text))]}
                for index, text in enumerate(texts)
            ]

    result = HybridVectorizer(Dense(), Sparse()).encode_documents(["eins", "zwei"])

    assert result == [
        {"dense_vector": [0.0], "sparse_vector": {"indices": [0], "values": [4.0]}},
        {"dense_vector": [1.0], "sparse_vector": {"indices": [1], "values": [4.0]}},
    ]


def test_hybrid_vectorizer_rejects_mismatched_output_lengths() -> None:
    class Dense:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0]]

    class Sparse:
        def encode_documents(self, texts: list[str]) -> list[dict]:
            return [{"indices": [1], "values": [1.0]} for _text in texts]

    with pytest.raises(ValueError, match="document count"):
        HybridVectorizer(Dense(), Sparse()).encode_documents(["eins", "zwei"])


def test_validate_runtime_dependencies_fails_fast_for_missing_third_party_module(
    monkeypatch,
    capsys,
) -> None:
    def fake_import_module(name: str):
        if name == "qdrant_client":
            raise ImportError("missing qdrant_client")
        return object()

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(SystemExit) as excinfo:
        build_vector_index._validate_runtime_dependencies()

    assert excinfo.value.code == 1
    error_output = capsys.readouterr().err
    assert "Missing dependency" in error_output
    assert "qdrant-client" in error_output
    assert "fastembed" in error_output


@pytest.mark.parametrize("value", ["0", "-1"])
def test_main_rejects_non_positive_limit(value: str, tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "local_index.sqlite"
    db_path.write_text("", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        build_vector_index.main(
            [
                "--db",
                str(db_path),
                "--qdrant-dir",
                str(tmp_path / "qdrant"),
                "--limit",
                value,
            ]
        )

    assert excinfo.value.code == 2
    assert "must be greater than 0" in capsys.readouterr().err


def test_main_reconciles_orphaned_vectors_even_when_nothing_is_new(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    current_doc = _doc("1", "https://example.org/doc-1.pdf")
    current_id = build_vector_index._stable_qdrant_id(
        current_doc["session_id"], current_doc["url"], current_doc["agenda_item"]
    )
    orphan_id = 999999
    vector_store = _FakeVectorStore(indexed_ids={current_id, orphan_id}, count=2)
    _install_fake_modules(monkeypatch, vector_store)
    monkeypatch.setattr(
        build_vector_index,
        "_validate_runtime_dependencies",
        lambda: (
            sys.modules["src.analysis.embeddings"].HarrierEmbedder,
            sys.modules["src.analysis.vector_store"].DocumentVectorStore,
        ),
    )
    monkeypatch.setattr(
        build_vector_index,
        "_load_documents",
        lambda _db_path, limit=None: [current_doc],
    )

    db_path = tmp_path / "local_index.sqlite"
    db_path.write_text("", encoding="utf-8")

    build_vector_index.main(["--db", str(db_path), "--qdrant-dir", str(tmp_path / "qdrant")])

    assert vector_store.deleted_ids == [{orphan_id}]
    assert vector_store.upserted_batches == []
    output = capsys.readouterr().out
    assert "Nothing to index" in output
    assert "Removing 1 orphaned vector(s)" in output


def test_main_skips_orphan_cleanup_for_limit_runs(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    current_doc = _doc("1", "https://example.org/doc-1.pdf")
    current_id = build_vector_index._stable_qdrant_id(
        current_doc["session_id"], current_doc["url"], current_doc["agenda_item"]
    )
    extra_indexed_id = 123456
    vector_store = _FakeVectorStore(indexed_ids={current_id, extra_indexed_id}, count=2)
    _install_fake_modules(monkeypatch, vector_store)
    monkeypatch.setattr(
        build_vector_index,
        "_validate_runtime_dependencies",
        lambda: (
            sys.modules["src.analysis.embeddings"].HarrierEmbedder,
            sys.modules["src.analysis.vector_store"].DocumentVectorStore,
        ),
    )
    monkeypatch.setattr(
        build_vector_index,
        "_load_documents",
        lambda _db_path, limit=None: [current_doc],
    )

    db_path = tmp_path / "local_index.sqlite"
    db_path.write_text("", encoding="utf-8")

    build_vector_index.main(
        [
            "--db",
            str(db_path),
            "--qdrant-dir",
            str(tmp_path / "qdrant"),
            "--limit",
            "1",
        ]
    )

    assert vector_store.deleted_ids == []
    assert vector_store.upserted_batches == []
    output = capsys.readouterr().out
    assert "Nothing to index" in output
    assert "Skipping orphan cleanup because --limit is set." in output


def test_limit_applies_to_missing_documents_not_first_sqlite_rows(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    first_doc = _doc("1", "https://example.org/doc-1.pdf")
    second_doc = _doc("2", "https://example.org/doc-2.pdf")
    third_doc = _doc("3", "https://example.org/doc-3.pdf")
    first_id = build_vector_index._stable_qdrant_id(
        first_doc["session_id"], first_doc["url"], first_doc["agenda_item"]
    )
    second_id = build_vector_index._stable_qdrant_id(
        second_doc["session_id"], second_doc["url"], second_doc["agenda_item"]
    )
    third_id = build_vector_index._stable_qdrant_id(
        third_doc["session_id"], third_doc["url"], third_doc["agenda_item"]
    )
    vector_store = _FakeVectorStore(indexed_ids={first_id}, count=1)

    embeddings_module = ModuleType("src.analysis.embeddings")

    class _FakeHarrierEmbedder:
        pass

    embeddings_module.HarrierEmbedder = _FakeHarrierEmbedder
    embeddings_module._detect_device = lambda: "cpu"

    vector_store_module = ModuleType("src.analysis.vector_store")
    vector_store_module.DocumentVectorStore = lambda _path: vector_store

    bm25_module = ModuleType("src.analysis.bm25_sparse")

    class _FakeBM25Encoder:
        def _get_model(self) -> None:
            pass

    bm25_module.BM25Encoder = _FakeBM25Encoder

    class _FakeHybridVectorizer:
        def __init__(self, _embedder, _bm25) -> None:
            pass

        def encode_documents(self, texts: list[str]) -> list[dict]:
            return [
                {
                    "dense_vector": [0.0] * 1024,
                    "sparse_vector": {"indices": [index], "values": [1.0]},
                }
                for index, _text in enumerate(texts)
            ]

    monkeypatch.setitem(sys.modules, "src.analysis.embeddings", embeddings_module)
    monkeypatch.setitem(sys.modules, "src.analysis.vector_store", vector_store_module)
    monkeypatch.setitem(sys.modules, "src.analysis.bm25_sparse", bm25_module)
    monkeypatch.setattr(
        build_vector_index,
        "_validate_runtime_dependencies",
        lambda: (_FakeHarrierEmbedder, vector_store_module.DocumentVectorStore),
    )
    monkeypatch.setattr(build_vector_index, "HybridVectorizer", _FakeHybridVectorizer)
    monkeypatch.setattr(
        build_vector_index,
        "_load_documents",
        lambda _db_path, limit=None: [first_doc, second_doc, third_doc],
    )

    db_path = tmp_path / "local_index.sqlite"
    db_path.write_text("", encoding="utf-8")

    build_vector_index.main(
        [
            "--db",
            str(db_path),
            "--qdrant-dir",
            str(tmp_path / "qdrant"),
            "--limit",
            "1",
        ]
    )

    assert [[point["id"] for point in batch] for batch in vector_store.upserted_batches] == [[second_id]]
    assert third_id not in {point["id"] for batch in vector_store.upserted_batches for point in batch}
    output = capsys.readouterr().out
    assert "2 missing, indexing next 1" in output
