from __future__ import annotations

import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from src.indexing import passages
from src.indexing.passage_builder import build_passage_index
from src.indexing.evaluation import score_query, evaluate


class Tokenizer:
    def __call__(self, text, **kwargs):
        return {"offset_mapping": [m.span() for m in re.finditer(r"\S+", text)]}


class Store:
    def __init__(self):
        self.points = {}
        self.fail = False

    def get_point_payloads(self):
        return {key: point["payload"] for key, point in self.points.items()}

    def upsert_batch(self, points):
        if self.fail:
            raise RuntimeError("interrupted")
        self.points.update({point["id"]: point for point in points})

    def delete_ids(self, ids):
        for key in ids:
            self.points.pop(key, None)

    def commit_passages(self, ids):
        for key in ids:
            self.points[key]["payload"]["committed"] = True


class Vectorizer:
    def encode_documents(self, texts):
        return [{"dense_vector": [1.0] + [0.0] * 1023,
                 "sparse_vector": {"indices": [1], "values": [1.0]}} for text in texts]


def document(tmp_path):
    folder = tmp_path / "data/raw/2025/06/session"
    folder.mkdir(parents=True)
    path = folder / "source.txt"
    path.write_text(" ".join(f"word{i}" for i in range(120)), encoding="utf-8")
    return {"id": 1, "session_id": "1", "url": "https://example.org/1.pdf", "title": "Test",
            "session_path": str(folder), "local_path": path.name}, path


def test_chunks_preserve_all_text_pages_and_overlap():
    text = " ".join(f"word{i}" for i in range(101))
    pages = [{"text": text, "page": 14, "method": "text"}]
    chunks = passages.chunk_pages(pages, Tokenizer(), tokens=32, overlap=8)
    assert all(chunk["token_count"] <= 32 and chunk["page_start"] == 14 for chunk in chunks)
    assert set(text.split()) == {word for chunk in chunks for word in chunk["text"].split()}
    assert chunks[0]["text"].split()[-8:] == chunks[1]["text"].split()[:8]


def test_extract_all_pages_including_ocr_mixed_pdf(tmp_path, monkeypatch):
    path = tmp_path / "mixed.pdf"
    path.write_bytes(b"placeholder")
    pages = [SimpleNamespace(extract_text=lambda i=i: "" if i == 11 else f"page {i}") for i in range(1, 15)]
    monkeypatch.setattr("pypdf.PdfReader", lambda path: SimpleNamespace(pages=pages))
    calls = []
    monkeypatch.setattr(passages, "ocr_page", lambda path, page: calls.append(page) or "scan text")
    result = passages.extract_pages(path)
    assert len(result) == 14
    assert calls == [11]
    assert result[10] == {"page": 11, "text": "scan text", "method": "ocr"}
    assert result[-1]["text"] == "page 14"


def test_missing_ocr_is_reported_and_other_pages_survive(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"placeholder")
    monkeypatch.setattr("pypdf.PdfReader", lambda p: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")]))
    monkeypatch.setattr(passages, "ocr_page", lambda *args: "")
    assert passages.extract_pages(path)[0]["method"] == "ocr_needed"


def test_changed_sources_replace_chunks_and_failures_preserve_old(tmp_path):
    doc, path = document(tmp_path)
    store = Store()
    def build(**kwargs):
        return build_passage_index([doc], store, Tokenizer(), Vectorizer, tokens=32, overlap=8, **kwargs)
    assert build()["processed_documents"] == 1
    old_ids = set(store.points)
    assert len(old_ids) > 1
    assert build()["processed_documents"] == 0
    path.write_text("changed short source", encoding="utf-8")
    store.fail = True
    assert build()["failures"]
    assert set(store.points) == old_ids
    store.fail = False
    assert not build()["failures"]
    assert len(store.points) == 1
    assert not old_ids.intersection(store.points)


def test_limit_preserves_unprocessed_and_deleted_sources(tmp_path):
    doc, path = document(tmp_path)
    store = Store()
    build_passage_index([doc], store, Tokenizer(), Vectorizer)
    original = set(store.points)
    build_passage_index([], store, Tokenizer(), Vectorizer, limit=1)
    assert set(store.points) == original
    build_passage_index([], store, Tokenizer(), Vectorizer)
    assert not store.points


def test_failed_forced_refresh_preserves_committed_generation(tmp_path):
    doc, _ = document(tmp_path)
    store = Store()
    build_passage_index([doc], store, Tokenizer(), Vectorizer, tokens=32, overlap=8)
    original = set(store.points)
    upsert = store.upsert_batch
    calls = []
    def interrupt(points):
        if calls:
            raise RuntimeError("interrupted after first batch")
        calls.append(True)
        upsert(points)
    store.upsert_batch = interrupt
    result = build_passage_index([doc], store, Tokenizer(), Vectorizer,
                                 tokens=32, overlap=8, batch_size=1, refresh=True)
    assert result["failures"]
    assert all(store.points[pid]["payload"]["committed"] for pid in original)
    store.upsert_batch = upsert
    build_passage_index([doc], store, Tokenizer(), Vectorizer, tokens=32, overlap=8)
    assert set(store.points) == original


def test_metadata_fallback_without_local_file(tmp_path):
    doc, path = document(tmp_path)
    doc["local_path"] = "missing.pdf"
    store = Store()
    build_passage_index([doc], store, Tokenizer(), Vectorizer)
    payload = next(iter(store.points.values()))["payload"]
    assert payload["extraction_method"] == "metadata"
    assert payload["page_start"] is None


def test_local_qdrant_passage_search_returns_page_and_source(tmp_path):
    from src.analysis.vector_store import DocumentVectorStore
    doc, path = document(tmp_path)
    store = DocumentVectorStore(tmp_path / "qdrant", collection_name=passages.COLLECTION)
    try:
        store.ensure_collection()
        build_passage_index([doc], store, Tokenizer(), Vectorizer, tokens=32, overlap=8)
        hits = store.search([1.] + [0.] * 1023, {"indices": [1], "values": [1.]})
        assert hits[0]["document_id"]
        assert hits[0]["text"]
        assert hits[0]["sqlite_document_id"] == 1
        assert len(store.get_point_payloads()) > 1
    finally:
        store.close()


def test_evaluation_distinguishes_document_from_evidence_match():
    relevant = [{"url": "a", "page": 14, "evidence": "known fact"}]
    legacy = [{"url": "a", "snippet": "title"}]
    assert score_query(legacy, relevant)["hit_at_k"] == 1
    assert score_query(legacy, relevant)["evidence_hit_at_k"] == 0
    hits = [{"url": "b"}, {"url": "b"}, {"url": "a", "page_start": 14, "text": "known fact"}]
    assert score_query(hits, relevant)["reciprocal_rank"] == .5
    assert score_query(hits, relevant)["evidence_hit_at_k"] == 1


def test_benchmark_has_30_evidence_backed_questions():
    data = json.loads((Path(__file__).resolve().parents[1] / "docs/examples/search_benchmark.json").read_text())
    assert len(data["queries"]) == 30
    assert len({q["id"] for q in data["queries"]}) == 30
    assert any(r["page"] > 10 for q in data["queries"] for r in q["relevant"])


def test_default_cli_dispatches_to_passages(monkeypatch):
    from scripts import build_vector_index
    calls = []
    monkeypatch.setattr("src.indexing.passage_builder.main", lambda argv: calls.append(argv))
    build_vector_index.main(["--limit", "2"])
    assert calls == [["--limit", "2"]]


def test_incomplete_generation_is_not_searchable(tmp_path):
    from src.analysis.vector_store import DocumentVectorStore
    store = DocumentVectorStore(tmp_path / "qdrant", collection_name=passages.COLLECTION)
    try:
        store.ensure_collection()
        vector = Vectorizer().encode_documents(["text"])[0]
        store.upsert_batch([{"id": 123, **vector, "payload": {"text": "partial", "committed": False}}])
        assert store.search(vector["dense_vector"], vector["sparse_vector"]) == []
        store.commit_passages({123})
        assert store.search(vector["dense_vector"], vector["sparse_vector"])[0]["text"] == "partial"
    finally:
        store.close()


def test_passage_activation_requires_readiness_marker(tmp_path):
    from src.analysis.vector_store import DocumentVectorStore
    directory = tmp_path / "qdrant"
    passage_store = DocumentVectorStore(directory, collection_name=passages.COLLECTION)
    passage_store.ensure_collection()
    vector = Vectorizer().encode_documents(["text"])[0]
    passage_store.upsert_batch([{"id": 1, **vector, "payload": {"committed": True}}])
    passage_store.close()
    store = DocumentVectorStore(directory)
    try:
        store.prefer_passages()
        assert store.collection_name == "ratsi_documents"
        (directory / "ratsi_passages.ready.json").write_text("{}")
        store.prefer_passages()
        assert store.collection_name == passages.COLLECTION
    finally:
        store.close()
