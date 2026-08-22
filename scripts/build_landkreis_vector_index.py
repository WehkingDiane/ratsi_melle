"""Build or update the Qdrant vector index for Landkreis publications.

Usage
-----
    python scripts/build_landkreis_vector_index.py [--db PATH] [--qdrant-dir PATH] [--data-dir PATH] [--limit N]
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
DEFAULT_MAX_TEXT_CHARS = 6_000


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


def _document_text(row: dict, *, max_chars: int = DEFAULT_MAX_TEXT_CHARS) -> str:
    """Return extracted text with a metadata fallback."""

    extracted = str(row.get("extracted_text") or "").strip()
    if extracted:
        return _truncate_text(extracted, max_chars)
    fallback = f"{row.get('title') or ''} {row.get('document_title') or ''}".strip()
    return _truncate_text(fallback, max_chars)


def _truncate_text(text: str, max_chars: int) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rsplit(" ", 1)[0].strip() or normalized[:max_chars].strip()


def _resolve_local_path(local_path: str, data_root: Path | None = None) -> str:
    path = Path(local_path)
    if not path.is_absolute():
        path = Path(data_root or LANDKREIS_DATA_DIR) / path
    return str(path.resolve())


def _build_payload(row: dict, *, data_root: Path = LANDKREIS_DATA_DIR, search_text: str = "") -> dict:
    return {
        "source_system": "landkreis",
        "publication_id": str(row.get("publication_id") or ""),
        "source": str(row.get("source") or ""),
        "title": str(row.get("title") or ""),
        "document_title": str(row.get("document_title") or ""),
        "date": str(row.get("date") or ""),
        "url": str(row.get("url") or ""),
        "local_path": _resolve_local_path(str(row.get("local_path") or ""), data_root=data_root),
        "snippet": _truncate_text(" ".join(search_text.split()), 500),
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


def _clear_torch_cache(device: str) -> None:
    try:
        import torch

        if device == "xpu" and torch.xpu.is_available():
            torch.xpu.empty_cache()
    except Exception:
        pass


def _is_torch_oom(exc: Exception) -> bool:
    return exc.__class__.__name__ == "OutOfMemoryError" or "out of memory" in str(exc).lower()


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
        "--data-dir",
        type=Path,
        default=LANDKREIS_DATA_DIR,
        dest="data_dir",
        help="Raw file storage root for resolving local_path payloads (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Index at most N missing Landkreis documents.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=_positive_int,
        default=DEFAULT_MAX_TEXT_CHARS,
        help=(
            "Maximum text characters per document passed to the embedding model "
            "(default: %(default)s)."
        ),
    )
    args = parser.parse_args(argv)

    db_path: Path = args.db
    qdrant_dir: Path = args.qdrant_dir
    data_dir: Path = args.data_dir

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
        batch_size = 1 if device == "xpu" else 32
        print(
            f"  Device: {device.upper()}, batch size: {batch_size}, "
            f"max text chars: {args.max_text_chars}"
        )

        vectorizer = HybridVectorizer(embedder, bm25)
        n = len(docs_to_index)
        batch_start = 0
        while batch_start < n:
            current_batch_size = min(batch_size, n - batch_start)
            batch = docs_to_index[batch_start : batch_start + current_batch_size]
            texts: list[str] = []
            for doc in batch:
                global_index = batch_start + len(texts) + 1
                title_preview = (doc.get("document_title") or doc.get("title") or "(kein Titel)")[:60]
                print(f"  [{global_index}/{n}] {title_preview} ...")
                texts.append(_document_text(doc, max_chars=args.max_text_chars))

            try:
                vector_results = vectorizer.encode_documents(texts)
            except Exception as exc:
                _clear_torch_cache(device)
                if _is_torch_oom(exc) and current_batch_size > 1:
                    batch_size = max(1, current_batch_size // 2)
                    print(f"  XPU/torch out of memory; retrying with batch size {batch_size}.")
                    continue
                if _is_torch_oom(exc):
                    print(
                        "ERROR: Embedding ran out of XPU/GPU memory. "
                        "Retry with a lower --max-text-chars value, for example 3000.",
                        file=sys.stderr,
                    )
                raise
            points = [
                {
                    "id": doc["_qdrant_id"],
                    "dense_vector": vectors["dense_vector"],
                    "sparse_vector": vectors["sparse_vector"],
                    "payload": _build_payload(doc, data_root=data_dir, search_text=text),
                }
                for doc, text, vectors in zip(batch, texts, vector_results)
            ]
            vector_store.upsert_batch(points)
            indexed_count += len(batch)
            batch_start += current_batch_size
            _clear_torch_cache(device)

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
