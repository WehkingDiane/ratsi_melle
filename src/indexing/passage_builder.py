"""Incremental Harrier passage indexing with source fingerprints."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import logging
from pathlib import Path
import shutil
from uuid import uuid4

from src.fetching.storage_layout import resolve_local_file_path
from src.indexing.id_strategy import stable_document_id
from src.indexing.payload_builder import build_document_payload
from src.indexing.passage_inventory import complete_document_ids
from src.indexing.passages import COLLECTION, MODEL, PIPELINE_VERSION, chunk_pages, extract_pages, file_digest
from src.indexing.vectorizer import HybridVectorizer
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR
from src.config.embedding_model_status import prepared_model_path
from src.config.embedding_models import HARRIER_TOKENIZER
from src.config.index_compatibility import (
    IndexCompatibility,
    current_index_compatibility,
    with_index_compatibility,
)


LOGGER = logging.getLogger(__name__)


def _load_tokenizer():
    """Load the pinned Harrier tokenizer from its prepared local snapshot."""

    tokenizer_path = prepared_model_path("tokenizer")
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)


def build_passage_index(documents, store, tokenizer, vectorizer_factory, *, limit=None,
                        tokens=768, overlap=96, use_ocr=True, batch_size=4, refresh=False,
                        update_existing=False, cleanup_orphans=False, indexed_payloads=None,
                        compatibility: IndexCompatibility | None = None):
    """Add missing documents; updating existing content is an explicit service operation."""
    if not 32 <= tokens <= 8192 or not 0 <= overlap < tokens or batch_size < 1:
        raise ValueError("Require 32..8192 chunk tokens, smaller nonnegative overlap and positive batch size")
    if refresh and not update_existing:
        raise ValueError("Forced refresh belongs to scripts/update_vector_index.py")
    indexed = store.get_point_payloads() if indexed_payloads is None else indexed_payloads
    complete_ids = complete_document_ids(indexed)
    groups = {}
    for point_id, payload in indexed.items():
        groups.setdefault(payload.get("document_id"), {})[point_id] = payload
    current = set()
    changed = 0
    pending = 0
    failures = []
    vectorizer = None
    skipped = 0
    for document in documents:
        parent = stable_document_id(str(document.get("session_id") or ""),
                                    str(document.get("url") or ""), str(document.get("agenda_item") or ""))
        current.add(parent)
        if not update_existing and parent in complete_ids:
            skipped += 1
            continue
        if not update_existing and limit is not None and changed >= limit:
            pending += 1
            continue
        path = resolve_local_file_path(session_path=document.get("session_path"), local_path=document.get("local_path"))
        try:
            source_hash = file_digest(path) if path is not None and path.is_file() else "missing"
            metadata = build_document_payload(document)
            metadata["sqlite_document_id"] = document.get("id")
            fingerprint = sha256(json.dumps({
                "source": source_hash, "metadata": metadata, "model": MODEL,
                "pipeline": PIPELINE_VERSION, "tokens": tokens, "overlap": overlap,
                "ocr": use_ocr, "ocr_tools": [shutil.which("pdftoppm"), shutil.which("tesseract")],
                "tokenizer_revision": HARRIER_TOKENIZER.revision,
            }, sort_keys=True).encode()).hexdigest()
            old = groups.get(parent, {})
            generations = {}
            for pid, payload in old.items():
                if payload.get("fingerprint") == fingerprint:
                    generations.setdefault(payload.get("generation", fingerprint), {})[pid] = payload
            complete = next((parts for parts in generations.values()
                             if parent in complete_document_ids(parts)), None)
            if update_existing and not refresh and complete:
                store.delete_ids(set(old) - set(complete))
                skipped += 1
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
                LOGGER.warning(
                    "event=document_pages_unreadable document_id=%s pages=%s",
                    parent,
                    unreadable,
                )
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
                if compatibility is not None:
                    payload = with_index_compatibility(payload, compatibility)
                points.append({"id": point_id, "payload": payload})
            if vectorizer is None:
                vectorizer = vectorizer_factory()
            for start in range(0, len(points), batch_size):
                batch = points[start:start + batch_size]
                vectors = vectorizer.encode_documents([p["payload"]["text"] for p in batch])
                store.upsert_batch([{**point, **vector} for point, vector in zip(batch, vectors, strict=True)])
            store.commit_passages({p["id"] for p in points})
            store.delete_ids(set(old) - {p["id"] for p in points})
            complete_ids.add(parent)
            LOGGER.info(
                "event=document_indexed document_id=%s passages=%d pages=%d",
                parent,
                len(chunks),
                len(pages),
            )
            print(f"Indexed {parent}: {len(chunks)} passages, {len(pages)} pages", flush=True)
        except Exception as exc:
            failures.append({"document_id": parent, "error": str(exc)})
            LOGGER.exception("event=document_failed document_id=%s", parent)
            print(f"ERROR {parent}: {exc}", flush=True)
    if cleanup_orphans and limit is None and not failures:
        store.delete_ids({pid for parent, points in groups.items() if parent not in current for pid in points})
    return {"processed_documents": changed, "pending_documents": pending,
            "skipped_documents": skipped, "failures": failures, "collection": COLLECTION}


def main(argv=None, *, maintenance=False):
    """Add missing documents, or explicitly run the separate update service."""
    from scripts.build_vector_index import _load_documents, _positive_int
    from src.analysis.vector_store import DocumentVectorStore
    from src.analysis.embeddings import HarrierEmbedder
    from src.analysis.bm25_sparse import BM25Encoder
    from src.indexing.build_compatibility import check_build_compatibility

    parser = argparse.ArgumentParser(description=(
        "Service: update changed documents." if maintenance else
        "Add only missing or incomplete documents. Complete documents remain unchanged."
    ))
    parser.add_argument("--db", type=Path, default=LOCAL_INDEX_DB)
    parser.add_argument("--qdrant-dir", type=Path, default=QDRANT_DIR,
                        help="Local storage when RATSI_QDRANT_MODE=local and RATSI_QDRANT_URL is unset")
    parser.add_argument("--limit", type=_positive_int, help="Maximum documents to index per run")
    parser.add_argument("--batch-size", type=_positive_int, default=4)
    parser.set_defaults(chunk_tokens=768, overlap_tokens=96, no_ocr=False, refresh=False, cleanup_orphans=False)
    if maintenance:
        parser.add_argument("--chunk-tokens", type=_positive_int, default=768)
        parser.add_argument("--overlap-tokens", type=int, default=96)
        parser.add_argument("--no-ocr", action="store_true")
        parser.add_argument("--refresh", action="store_true", help="Reindex even unchanged files")
        parser.add_argument("--cleanup-orphans", action="store_true", help="Remove documents absent from SQLite after a successful unlimited update")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args(argv)
    if not 32 <= args.chunk_tokens <= 8192 or not 0 <= args.overlap_tokens < args.chunk_tokens:
        parser.error("Require 32..8192 chunk tokens and 0 <= overlap-tokens < chunk-tokens")
    if not args.db.is_file():
        parser.error(f"Database not found: {args.db}")
    store = DocumentVectorStore(args.qdrant_dir, collection_name=COLLECTION)
    try:
        store.acquire_build_lock()
        store._get_client()
        compatibility = current_index_compatibility()
        check_build_compatibility(store.connection, store._get_client(), COLLECTION,
                                  compatibility, validate_vectors=False)
        documents = _load_documents(args.db)
        expected = {stable_document_id(str(d.get("session_id") or ""), str(d.get("url") or ""),
                                       str(d.get("agenda_item") or "")) for d in documents}
        inventory = store.get_passage_inventory()
        missing = expected - complete_document_ids(inventory)
        if not maintenance:
            print(f"Dokumente: {len(expected)}; vollständig vorhanden: {len(expected - missing)}; "
                  f"fehlend oder unvollständig: {len(missing)}", flush=True)
        ready_before = store.connection.passages_ready(store._get_client())
        needs_build = maintenance or bool(missing) or bool(expected and not ready_before)
        if needs_build:
            store.begin_build(compatibility, validate_vectors=maintenance)
        tokenizer = _load_tokenizer() if missing or maintenance else None
        result = build_passage_index(
            documents, store, tokenizer,
            lambda: HybridVectorizer(HarrierEmbedder(), BM25Encoder()),
            limit=args.limit, tokens=args.chunk_tokens, overlap=args.overlap_tokens,
            use_ocr=not args.no_ocr, batch_size=args.batch_size, refresh=args.refresh,
            update_existing=maintenance, cleanup_orphans=args.cleanup_orphans,
            indexed_payloads=inventory,
            compatibility=compatibility,
        )
        # Activate only after every current document has a complete generation.
        # A --limit build may finish migration over several runs.
        final_inventory = store.get_passage_inventory() if needs_build else inventory
        complete = complete_document_ids(final_inventory)
        if (needs_build and expected and expected <= complete and not result["failures"]
                and not result["pending_documents"]
                and all(p.get("committed") is True for p in final_inventory.values())):
            store.finish_build(compatibility)
        result["ready"] = store.connection.passages_ready(store._get_client())
        print(json.dumps(result, ensure_ascii=False))
        if result["failures"]:
            raise SystemExit(1)
    finally:
        store.close()
