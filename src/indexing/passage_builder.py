"""Incremental Harrier passage indexing with source fingerprints."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from uuid import uuid4

from src.fetching.storage_layout import resolve_local_file_path
from src.indexing.id_strategy import stable_document_id
from src.indexing.payload_builder import build_document_payload
from src.indexing.passages import COLLECTION, MODEL, PIPELINE_VERSION, chunk_pages, extract_pages, file_digest
from src.indexing.vectorizer import HybridVectorizer
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR


def build_passage_index(documents, store, tokenizer, vectorizer_factory, *, limit=None,
                        tokens=768, overlap=96, use_ocr=True, batch_size=4, refresh=False):
    """Replace changed documents only after all their new passages are stored."""
    if not 32 <= tokens <= 8192 or not 0 <= overlap < tokens or batch_size < 1:
        raise ValueError("Require 32..8192 chunk tokens, smaller nonnegative overlap and positive batch size")
    indexed = store.get_point_payloads()
    groups = {}
    for point_id, payload in indexed.items():
        groups.setdefault(payload.get("document_id"), {})[point_id] = payload
    current = set()
    changed = 0
    pending = 0
    failures = []
    vectorizer = None
    for document in documents:
        parent = stable_document_id(str(document.get("session_id") or ""),
                                    str(document.get("url") or ""), str(document.get("agenda_item") or ""))
        current.add(parent)
        path = resolve_local_file_path(session_path=document.get("session_path"), local_path=document.get("local_path"))
        try:
            source_hash = file_digest(path) if path is not None and path.is_file() else "missing"
            metadata = build_document_payload(document)
            metadata["sqlite_document_id"] = document.get("id")
            fingerprint = sha256(json.dumps({
                "source": source_hash, "metadata": metadata, "model": MODEL,
                "pipeline": PIPELINE_VERSION, "tokens": tokens, "overlap": overlap,
                "ocr": use_ocr, "ocr_tools": [shutil.which("pdftoppm"), shutil.which("tesseract")],
                "tokenizer_revision": getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
            }, sort_keys=True).encode()).hexdigest()
            old = groups.get(parent, {})
            generations = {}
            for pid, payload in old.items():
                if payload.get("fingerprint") == fingerprint and payload.get("committed"):
                    generations.setdefault(payload.get("generation", fingerprint), {})[pid] = payload
            complete = next((parts for parts in generations.values()
                             if len(parts) == next(iter(parts.values())).get("chunk_count")), None)
            if not refresh and complete:
                store.delete_ids(set(old) - set(complete))
                continue
            if limit is not None and changed >= limit:
                pending += 1
                continue
            changed += 1
            pages = extract_pages(path, use_ocr=use_ocr) if source_hash != "missing" else []
            chunks = chunk_pages(pages, tokenizer, tokens=tokens, overlap=overlap)
            unreadable = [p["page"] for p in pages if not p["text"].strip()]
            if not chunks:
                chunks = [{"text": f"{document.get('title', '')} {document.get('document_type', '')}".strip() or "Dokument",
                           "page_start": None, "page_end": None, "extraction_method": "metadata"}]
            if unreadable:
                print(f"WARNING {parent}: pages without text: {unreadable}", flush=True)
            points = []
            # Forced OCR retries must not overwrite the still-searchable generation.
            generation = f"{fingerprint}:{uuid4().hex}" if refresh else fingerprint
            for number, chunk in enumerate(chunks):
                point_id = int.from_bytes(sha256(f"{parent}:{generation}:{number}".encode()).digest()[:8], "big")
                payload = {**metadata, **chunk, "snippet": chunk["text"][:500], "document_id": parent,
                           "sqlite_document_id": document.get("id"), "chunk_index": number,
                           "chunk_count": len(chunks), "fingerprint": fingerprint, "generation": generation,
                           "source_hash": source_hash, "model": MODEL, "pipeline_version": PIPELINE_VERSION,
                           "unreadable_pages": unreadable, "committed": False}
                points.append({"id": point_id, "payload": payload})
            if vectorizer is None:
                vectorizer = vectorizer_factory()
            for start in range(0, len(points), batch_size):
                batch = points[start:start + batch_size]
                vectors = vectorizer.encode_documents([p["payload"]["text"] for p in batch])
                store.upsert_batch([{**point, **vector} for point, vector in zip(batch, vectors, strict=True)])
            store.commit_passages({p["id"] for p in points})
            store.delete_ids(set(old) - {p["id"] for p in points})
            print(f"Indexed {parent}: {len(chunks)} passages, {len(pages)} pages", flush=True)
        except Exception as exc:
            failures.append({"document_id": parent, "error": str(exc)})
            print(f"ERROR {parent}: {exc}", flush=True)
    if limit is None and not failures:
        store.delete_ids({pid for parent, points in groups.items() if parent not in current for pid in points})
    return {"processed_documents": changed, "pending_documents": pending, "failures": failures, "collection": COLLECTION}


def main(argv=None):
    """Build the passage collection using the existing local Harrier model."""
    from scripts.build_vector_index import _load_documents, _positive_int
    from src.analysis.vector_store import DocumentVectorStore
    from src.analysis.embeddings import HarrierEmbedder
    from src.analysis.bm25_sparse import BM25Encoder

    parser = argparse.ArgumentParser(description=__doc__, epilog="Use --legacy-document-index on build_vector_index.py to build the old document baseline.")
    parser.add_argument("--db", type=Path, default=LOCAL_INDEX_DB)
    parser.add_argument("--qdrant-dir", type=Path, default=QDRANT_DIR,
                        help="Local storage; ignored when RATSI_QDRANT_URL is set")
    parser.add_argument("--limit", type=_positive_int, help="Maximum changed documents per run")
    parser.add_argument("--chunk-tokens", type=_positive_int, default=768)
    parser.add_argument("--overlap-tokens", type=int, default=96)
    parser.add_argument("--batch-size", type=_positive_int, default=4)
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Retry extraction even for unchanged files")
    args = parser.parse_args(argv)
    if not 32 <= args.chunk_tokens <= 8192 or not 0 <= args.overlap_tokens < args.chunk_tokens:
        parser.error("Require 32..8192 chunk tokens and 0 <= overlap-tokens < chunk-tokens")
    if not args.db.is_file():
        parser.error(f"Database not found: {args.db}")
    from transformers import AutoTokenizer

    store = DocumentVectorStore(args.qdrant_dir, collection_name=COLLECTION)
    try:
        store.connection.clear_readiness()
        store.ensure_collection()
        tokenizer = AutoTokenizer.from_pretrained(MODEL)
        result = build_passage_index(
            _load_documents(args.db), store, tokenizer,
            lambda: HybridVectorizer(HarrierEmbedder(), BM25Encoder()),
            limit=args.limit, tokens=args.chunk_tokens, overlap=args.overlap_tokens,
            use_ocr=not args.no_ocr, batch_size=args.batch_size, refresh=args.refresh,
        )
        # Activate only after every current document has a complete generation.
        # A --limit build may finish migration over several runs.
        expected = {stable_document_id(str(d.get("session_id") or ""), str(d.get("url") or ""),
                                       str(d.get("agenda_item") or "")) for d in _load_documents(args.db)}
        generations = {}
        for payload in store.get_point_payloads().values():
            generations.setdefault((payload.get("document_id"), payload.get("generation", payload.get("fingerprint"))), []).append(payload)
        complete = {parent for (parent, _), chunks in generations.items()
                    if len(chunks) == chunks[0].get("chunk_count") and all(c.get("committed") for c in chunks)}
        if expected and expected <= complete and not result["failures"] and not result["pending_documents"]:
            store.connection.write_readiness(store._get_client(), {"pipeline_version": PIPELINE_VERSION, "model": MODEL})
        result["ready"] = store.connection.passages_ready(store._get_client())
        print(json.dumps(result, ensure_ascii=False))
        if result["failures"]:
            raise SystemExit(1)
    finally:
        store.close()
