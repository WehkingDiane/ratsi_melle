from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from scripts import build_vector_index


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
