"""Read-only service check of the Ratsinfo passage collection; never repairs or releases it."""

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_vector_index import _load_documents
from src.analysis.vector_store import DocumentVectorStore
from src.config.index_compatibility import current_index_compatibility
from src.indexing.build_compatibility import check_build_compatibility
from src.indexing.id_strategy import stable_document_id
from src.indexing.passage_inventory import complete_document_ids
from src.indexing.passages import COLLECTION
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR


def main(argv=None):
    """Inspect model files, contracts, stored vectors and document completeness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=LOCAL_INDEX_DB)
    parser.add_argument("--qdrant-dir", type=Path, default=QDRANT_DIR)
    args = parser.parse_args(argv)
    if not args.db.is_file():
        parser.error(f"Database not found: {args.db}")
    store = DocumentVectorStore(args.qdrant_dir, collection_name=COLLECTION)
    try:
        client = store._get_client()
        compatibility = current_index_compatibility(deep=True)
        check_build_compatibility(store.connection, client, COLLECTION, compatibility)
        if COLLECTION not in {item.name for item in client.get_collections().collections}:
            raise ValueError("Passage collection does not exist")
        # A presence-only build marker deliberately does not hash numeric vectors.
        # This separate service explicitly reads those vectors and their contracts.
        snapshot = store.connection._point_snapshot(client, COLLECTION, compatibility)
        if snapshot is None:
            raise ValueError("Stored vector/contract inventory could not be read consistently")
        documents = _load_documents(args.db, read_only=True)
        expected = {stable_document_id(str(d.get("session_id") or ""), str(d.get("url") or ""),
                                       str(d.get("agenda_item") or "")) for d in documents}
        inventory = store.get_passage_inventory()
        complete = complete_document_ids(inventory)
        print(json.dumps({
            "collection": COLLECTION, "points": snapshot[0], "vectors_sha256": snapshot[1],
            "complete_documents": len(expected & complete), "missing_documents": len(expected - complete),
            "orphaned_documents": len(complete - expected),
            "uncommitted_passages": sum(p.get("committed") is not True for p in inventory.values()),
            "ready": store.connection.passages_ready(client), "read_only": True,
        }, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        store.close()


if __name__ == "__main__":
    main()
