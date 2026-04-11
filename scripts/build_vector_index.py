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
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run directly
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.paths import LOCAL_INDEX_DB, QDRANT_DIR


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
    local_path_str: str = row.get("local_path") or ""
    session_path_str: str = row.get("session_path") or ""

    if local_path_str and session_path_str:
        local_path = Path(session_path_str) / local_path_str
        if local_path.exists() and local_path.suffix.lower() == ".pdf":
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

    # Lazy imports so the script fails gracefully if deps are missing
    try:
        from src.analysis.embeddings import HarrierEmbedder
        from src.analysis.vector_store import DocumentVectorStore
    except ImportError as exc:
        print(
            f"ERROR: Missing dependency – {exc}\n"
            "Install with: pip install sentence-transformers qdrant-client",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Loading documents from database …")
    all_docs = _load_documents(db_path, limit=args.limit)
    total_in_db = len(all_docs)
    print(f"  Found {total_in_db} document(s) in DB.")

    vector_store = DocumentVectorStore(qdrant_dir)
    vector_store.ensure_collection()

    already_indexed = vector_store.get_indexed_ids()
    docs_to_index = [d for d in all_docs if d["id"] not in already_indexed]

    if not docs_to_index:
        print("Nothing to index – all documents are already in the vector store.")
        print(f"Total indexed: {vector_store.count()}")
        return

    print(f"  {len(already_indexed)} already indexed, {len(docs_to_index)} new.")
    print("Loading embedding model (this may take a moment on first run) …")
    embedder = HarrierEmbedder()

    batch_size = 8
    indexed_count = 0
    n = len(docs_to_index)

    for batch_start in range(0, n, batch_size):
        batch = docs_to_index[batch_start : batch_start + batch_size]

        texts: list[str] = []
        for doc in batch:
            global_index = batch_start + len(texts) + 1
            title_preview = (doc.get("title") or "(kein Titel)")[:60]
            print(f"  [{global_index}/{n}] {title_preview} …")
            texts.append(_get_document_text(doc))

        vectors = embedder.embed_documents(texts)

        points: list[dict] = []
        for doc, vector in zip(batch, vectors):
            points.append(
                {
                    "id": doc["id"],
                    "vector": vector,
                    "payload": {
                        "session_id": doc.get("session_id"),
                        "title": doc.get("title") or "",
                        "document_type": doc.get("document_type") or "",
                        "agenda_item": doc.get("agenda_item") or "",
                        "url": doc.get("url") or "",
                        "local_path": doc.get("local_path") or "",
                        "date": doc.get("date") or "",
                        "committee": doc.get("committee") or "",
                    },
                }
            )

        vector_store.upsert_batch(points)
        indexed_count += len(batch)

    total_now = vector_store.count()
    print(f"\nIndexed {indexed_count} new documents. Total: {total_now}")


if __name__ == "__main__":
    main()
