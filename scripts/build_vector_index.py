"""Build or update the Qdrant vector index from local_index.sqlite.

Usage
-----
    python scripts/build_vector_index.py [--db PATH] [--qdrant-dir PATH] [--limit N]

The script reads all documents from the ``documents`` table, skips those
already present in the vector store, extracts text from local PDF files
(up to 10 pages) or falls back to title + document_type, and upserts
batches of embeddings into the Qdrant collection.
"""

from __future__ import annotations

import argparse
import importlib
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run directly
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.fetching.storage_layout import resolve_local_file_path
from src.indexing.id_strategy import stable_document_id
from src.indexing.payload_builder import build_document_payload, resolve_local_path as _resolved_payload_local_path
from src.indexing.reconciliation import find_orphaned_ids
from src.indexing.vectorizer import HybridVectorizer
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR

_stable_qdrant_id = stable_document_id


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_text_pypdf(pdf_path: Path, max_pages: int = 10) -> str:
    """Extract text from a PDF using pypdf, limited to *max_pages* pages."""
    try:
        import pypdf  # type: ignore[import-untyped]

        reader = pypdf.PdfReader(str(pdf_path))
        pages = reader.pages[:max_pages]
        parts: list[str] = []
        for page in pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
        return "\n\n".join(parts)
    except Exception:
        return ""


def _get_document_text(row: dict) -> str:
    """Return the best available text for a document row.

    local_path in SQLite is relative to the session folder (session_path),
    so we resolve the full path before attempting extraction.
    """
    local_path = resolve_local_file_path(
        session_path=str(row.get("session_path") or ""),
        local_path=str(row.get("local_path") or ""),
    )

    if local_path is not None and local_path.is_file() and local_path.suffix.lower() == ".pdf":
        text = _extract_text_pypdf(local_path)
        if text.strip():
            return text

    # Fallback: title + document_type
    title: str = row.get("title") or ""
    doc_type: str = row.get("document_type") or ""
    return f"{title} {doc_type}".strip()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _load_documents(db_path: Path, limit: int | None = None) -> list[dict]:
    """Return all documents joined with session metadata."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT
                d.id,
                d.session_id,
                d.title,
                d.document_type,
                d.agenda_item,
                d.url,
                d.local_path,
                s.date,
                s.committee,
                s.session_path
            FROM documents d
            LEFT JOIN sessions s ON s.session_id = d.session_id
            ORDER BY d.id
        """
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _reconcile_orphaned_vectors(
    vector_store,
    already_indexed: set[int],
    current_ids: set[int],
    *,
    allow_delete: bool,
) -> int:
    """Remove vectors for documents that no longer exist in SQLite."""
    if not allow_delete:
        print("Skipping orphan cleanup because --limit is set.")
        return 0

    orphaned = find_orphaned_ids(already_indexed, current_ids)
    if orphaned:
        print(f"  Removing {len(orphaned)} orphaned vector(s) …")
        vector_store.delete_ids(orphaned)
    return len(orphaned)


def _validate_runtime_dependencies() -> tuple[type, type]:
    """Fail fast with a clear install hint when runtime deps are missing."""
    requirements: list[tuple[str, str]] = [
        ("sentence-transformers", "sentence_transformers"),
        ("qdrant-client", "qdrant_client"),
        ("fastembed", "fastembed"),
    ]
    missing: list[str] = []
    for package_name, module_name in requirements:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        missing_text = ", ".join(missing)
        print(
            f"ERROR: Missing dependency – {missing_text}\n"
            "Install with: pip install sentence-transformers qdrant-client fastembed",
            file=sys.stderr,
        )
        sys.exit(1)

    from src.analysis.embeddings import HarrierEmbedder
    from src.analysis.vector_store import DocumentVectorStore

    return HarrierEmbedder, DocumentVectorStore


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build or update the Qdrant semantic vector index."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=LOCAL_INDEX_DB,
        help="Path to local_index.sqlite (default: %(default)s)",
    )
    parser.add_argument(
        "--qdrant-dir",
        type=Path,
        default=QDRANT_DIR,
        dest="qdrant_dir",
        help="Directory for Qdrant local storage (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N documents (useful for testing).",
    )
    args = parser.parse_args(argv)

    db_path: Path = args.db
    qdrant_dir: Path = args.qdrant_dir

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    HarrierEmbedder, DocumentVectorStore = _validate_runtime_dependencies()

    print("Loading documents from database …")
    all_docs = _load_documents(db_path, limit=args.limit)
    total_in_db = len(all_docs)
    print(f"  Found {total_in_db} document(s) in DB.")

    vector_store = DocumentVectorStore(qdrant_dir)
    vector_store.ensure_collection()

    # Use stable hash IDs (not SQLite autoincrement) to survive index refreshes
    for doc in all_docs:
        doc["_qdrant_id"] = stable_document_id(
            str(doc.get("session_id") or ""),
            str(doc.get("url") or ""),
            str(doc.get("agenda_item") or ""),
        )

    current_ids = {d["_qdrant_id"] for d in all_docs}
    already_indexed = vector_store.get_indexed_ids()
    docs_to_index = [d for d in all_docs if d["_qdrant_id"] not in already_indexed]
    indexed_count = 0

    if not docs_to_index:
        print("Nothing to index – all documents are already in the vector store.")
    else:
        print(f"  {len(already_indexed)} already indexed, {len(docs_to_index)} new.")
        print("Loading embedding models …")
        embedder = HarrierEmbedder()

        from src.analysis.bm25_sparse import BM25Encoder

        bm25 = BM25Encoder()
        # Trigger BM25 model download before the main loop
        bm25._get_model()

        # XPU (Intel Arc) has limited free VRAM after loading the model (~1 GB left).
        # Use smaller batches to avoid OOM; CPU can handle larger batches.
        from src.analysis.embeddings import _detect_device

        device = _detect_device()
        batch_size = 4 if device == "xpu" else 32
        print(f"  Device: {device.upper()}, batch size: {batch_size}")

        n = len(docs_to_index)
        vectorizer = HybridVectorizer(embedder, bm25)

        for batch_start in range(0, n, batch_size):
            batch = docs_to_index[batch_start : batch_start + batch_size]

            texts: list[str] = []
            for doc in batch:
                global_index = batch_start + len(texts) + 1
                title_preview = (doc.get("title") or "(kein Titel)")[:60]
                print(f"  [{global_index}/{n}] {title_preview} …")
                texts.append(_get_document_text(doc))

            vector_results = vectorizer.encode_documents(texts)

            points: list[dict] = []
            for doc, vectors in zip(batch, vector_results):
                points.append(
                    {
                        "id": doc["_qdrant_id"],
                        "dense_vector": vectors["dense_vector"],
                        "sparse_vector": vectors["sparse_vector"],
                        "payload": build_document_payload(doc),
                    }
                )

            vector_store.upsert_batch(points)
            indexed_count += len(batch)

            # Free unused XPU/GPU memory after each batch to prevent OOM
            try:
                import torch

                if device == "xpu" and torch.xpu.is_available():
                    torch.xpu.empty_cache()
            except Exception:
                pass

    _reconcile_orphaned_vectors(
        vector_store,
        already_indexed,
        current_ids,
        allow_delete=args.limit is None,
    )

    total_now = vector_store.count()
    print(f"\nIndexed {indexed_count} new documents. Total: {total_now}")


if __name__ == "__main__":
    main()
