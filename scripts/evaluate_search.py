"""Validate known PDF evidence or measure local Harrier retrieval quality."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indexing.evaluation import evaluate, normalize_evidence
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR


def validate_sources(queries, documents):
    """Verify all annotated quotations on their original PDF pages."""
    from pypdf import PdfReader
    from src.fetching.storage_layout import resolve_local_file_path

    readers = {}
    errors = []
    for query in queries:
        for source in query["relevant"]:
            try:
                if source["url"] not in readers:
                    matches = [d for d in documents if d["url"] == source["url"]]
                    paths = [resolve_local_file_path(session_path=d["session_path"], local_path=d["local_path"]) for d in matches]
                    path = next((p for p in paths if p and p.is_file()), None)
                    if path is None:
                        raise ValueError("Source PDF is not available locally")
                    readers[source["url"]] = PdfReader(str(path))
                text = readers[source["url"]].pages[source["page"] - 1].extract_text() or ""
                if normalize_evidence(source["evidence"]) not in normalize_evidence(text):
                    raise ValueError("Evidence does not match the annotated page")
            except Exception as exc:
                errors.append({"id": query["id"], "url": source["url"], "error": str(exc)})
    return errors


def main(argv=None):
    """Run source validation or a timed local retrieval benchmark."""
    from scripts.build_vector_index import _load_documents, _positive_int

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=ROOT / "docs/examples/search_benchmark.json")
    parser.add_argument("--db", type=Path, default=LOCAL_INDEX_DB)
    parser.add_argument("--qdrant-dir", type=Path, default=QDRANT_DIR,
                        help="Local storage when RATSI_QDRANT_MODE=local and RATSI_QDRANT_URL is unset")
    parser.add_argument("--collection", choices=["ratsi_documents", "ratsi_passages"], default="ratsi_passages")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--k", type=_positive_int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.db.is_file():
        parser.error(f"Database not found: {args.db}")
    queries = json.loads(args.benchmark.read_text(encoding="utf-8"))["queries"]
    if not queries or len({q["id"] for q in queries}) != len(queries) or any(not q["relevant"] for q in queries):
        parser.error("Require nonempty queries with unique IDs and evidence")
    errors = validate_sources(queries, _load_documents(args.db))
    if errors:
        print(json.dumps({"validation_errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if args.validate_only:
        print(f"Validated {len(queries)} questions against local PDF pages.")
        return
    from src.analysis.embeddings import HarrierEmbedder
    from src.analysis.bm25_sparse import BM25Encoder
    from src.analysis.vector_store import DocumentVectorStore
    from src.indexing.passages import MODEL, PIPELINE_VERSION, file_digest

    store = DocumentVectorStore(args.qdrant_dir, collection_name=args.collection)
    embedder, sparse = HarrierEmbedder(), BM25Encoder()
    try:
        store.require_available()
        indexed_points = store.count()
        if not indexed_points:
            parser.error(f"Collection {args.collection} is empty or unavailable")
        # Exclude model startup from query timings, and report it separately.
        import time
        start = time.perf_counter()
        embedder.embed_query("Suche")
        sparse.encode_query("Suche")
        startup = time.perf_counter() - start
        report = evaluate(queries, lambda text, k: store.search(
            query_dense=embedder.embed_query(text), query_sparse=sparse.encode_query(text), limit=k), k=args.k)
        report.update(collection=args.collection, model=MODEL,
                      pipeline_version=PIPELINE_VERSION if args.collection == "ratsi_passages" else "legacy-10-pages",
                      indexed_points=indexed_points,
                      benchmark_sha256=file_digest(args.benchmark), model_startup_seconds=startup,
                      generated_at=datetime.now(timezone.utc).isoformat())
        output = args.output or ROOT / "data/processed/search_evaluation" / f"{args.collection}-{datetime.now():%Y%m%d-%H%M%S}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps(report["metrics"], indent=2))
        print(f"Report: {output}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
