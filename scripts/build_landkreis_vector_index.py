"""Build or update the Qdrant vector index for Landkreis publications.

Usage
-----
    python scripts/build_landkreis_vector_index.py [--db PATH] [--qdrant-dir PATH] [--limit N]
"""

from __future__ import annotations

import argparse
import importlib
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.indexing.id_strategy import stable_document_id
from src.indexing.reconciliation import find_orphaned_ids
from src.indexing.vectorizer import HybridVectorizer
from src.paths import LANDKREIS_DATA_DIR, LANDKREIS_PUBLICATIONS_DB, QDRANT_DIR

COLLECTION_NAME = "landkreis_publications"


def _stable_landkreis_qdrant_id(publication_id: str, document_url: str) -> int:
    """Return a stable Qdrant point ID for one Landkreis document."""

    return stable_document_id("landkreis", publication_id, document_url)


def _load_documents(db_path: Path) -> list[dict]:
    """Return locally available Landkreis document rows with publication metadata."""

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.publication_id,
                d.title AS document_title,
                d.url,
                d.local_path,
                p.source,
                p.date,
                p.title,
                et.extracted_text
            FROM documents d
            JOIN publications p ON p.publication_id = d.publication_id
            LEFT JOIN extracted_texts et ON et.document_id = d.id
            WHERE COALESCE(d.local_path, '') != ''
            ORDER BY p.date DESC, p.title ASC, d.title ASC, d.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _document_text(row: dict) -> str:
    """Return extracted text with a metadata fallback."""

    extracted = str(row.get("extracted_text") or "").strip()
    if extracted:
        return extracted
    return f"{row.get('title') or ''} {row.get('document_title') or ''}".strip()


def _resolve_local_path(local_path: str, data_root: Path | None = None) -> str:
    path = Path(local_path)
    if not path.is_absolute():
        path = Path(data_root or LANDKREIS_DATA_DIR) / path
    return str(path.resolve())


def _build_payload(row: dict) -> dict:
    return {
        "source_system": "landkreis",
        "publication_id": str(row.get("publication_id") or ""),
        "source": str(row.get("source") or ""),
        "title": str(row.get("title") or ""),
        "document_title": str(row.get("document_title") or ""),
        "date": str(row.get("date") or ""),
        "url": str(row.get("url") or ""),
        "local_path": _resolve_local_path(str(row.get("local_path") or "")),
    }


def _reconcile_orphaned_vectors(
    vector_store,
    already_indexed: set[int],
    current_ids: set[int],
    *,
    allow_delete: bool,
) -> int:
    if not allow_delete:
        print("Skipping orphan cleanup because --limit is set.")
        return 0

    orphaned = find_orphaned_ids(already_indexed, current_ids)
    if orphaned:
        print(f"  Removing {len(orphaned)} orphaned Landkreis vector(s) ...")
        vector_store.delete_ids(orphaned)
    return len(orphaned)


def _validate_runtime_dependencies() -> tuple[type, type]:
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
            f"ERROR: Missing dependency - {missing_text}\n"
            "Install with: pip install sentence-transformers qdrant-client fastembed",
            file=sys.stderr,
        )
        sys.exit(1)

    from src.analysis.embeddings import HarrierEmbedder
    from src.analysis.vector_store import DocumentVectorStore

    return HarrierEmbedder, DocumentVectorStore


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build or update the Landkreis Qdrant semantic vector index."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=LANDKREIS_PUBLICATIONS_DB,
        help="Path to landkreis_publications.sqlite (default: %(default)s)",
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
        type=_positive_int,
        default=None,
        help="Index at most N missing Landkreis documents.",
    )
    args = parser.parse_args(argv)

    db_path: Path = args.db
    qdrant_dir: Path = args.qdrant_dir

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    HarrierEmbedder, DocumentVectorStore = _validate_runtime_dependencies()

    print("Loading Landkreis documents from database ...")
    all_docs = _load_documents(db_path)
    print(f"  Found {len(all_docs)} locally stored Landkreis document(s) in DB.")

    vector_store = DocumentVectorStore(qdrant_dir, collection_name=COLLECTION_NAME)
    vector_store.ensure_collection()

    for doc in all_docs:
        doc["_qdrant_id"] = _stable_landkreis_qdrant_id(
            str(doc.get("publication_id") or ""),
            str(doc.get("url") or ""),
        )

    current_ids = {doc["_qdrant_id"] for doc in all_docs}
    already_indexed = vector_store.get_indexed_ids()
    missing_docs = [doc for doc in all_docs if doc["_qdrant_id"] not in already_indexed]
    docs_to_index = missing_docs[: args.limit] if args.limit is not None else missing_docs
    indexed_count = 0

    if not docs_to_index:
        print("Nothing to index - all Landkreis documents are already in the vector store.")
    else:
        if args.limit is not None and len(missing_docs) > len(docs_to_index):
            print(
                f"  {len(already_indexed)} already indexed, "
                f"{len(missing_docs)} missing, indexing next {len(docs_to_index)}."
            )
        else:
            print(f"  {len(already_indexed)} already indexed, {len(docs_to_index)} new.")
        print("Loading embedding models ...")
        embedder = HarrierEmbedder()

        from src.analysis.bm25_sparse import BM25Encoder
        from src.analysis.embeddings import _detect_device

        bm25 = BM25Encoder()
        bm25._get_model()
        device = _detect_device()
        batch_size = 4 if device == "xpu" else 32
        print(f"  Device: {device.upper()}, batch size: {batch_size}")

        vectorizer = HybridVectorizer(embedder, bm25)
        n = len(docs_to_index)
        for batch_start in range(0, n, batch_size):
            batch = docs_to_index[batch_start : batch_start + batch_size]
            texts: list[str] = []
            for doc in batch:
                global_index = batch_start + len(texts) + 1
                title_preview = (doc.get("document_title") or doc.get("title") or "(kein Titel)")[:60]
                print(f"  [{global_index}/{n}] {title_preview} ...")
                texts.append(_document_text(doc))

            vector_results = vectorizer.encode_documents(texts)
            points = [
                {
                    "id": doc["_qdrant_id"],
                    "dense_vector": vectors["dense_vector"],
                    "sparse_vector": vectors["sparse_vector"],
                    "payload": _build_payload(doc),
                }
                for doc, vectors in zip(batch, vector_results)
            ]
            vector_store.upsert_batch(points)
            indexed_count += len(batch)

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
    print(f"\nIndexed {indexed_count} new Landkreis documents. Total: {total_now}")


if __name__ == "__main__":
    main()
