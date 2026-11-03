"""Compare stored Ratsinfo passage vectors with a separately prepared model inventory."""

from contextlib import ExitStack
from datetime import datetime, timezone
from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.index_compatibility import current_index_compatibility
from src.config.embedding_model_status import load_and_validate_model_inventory
from src.indexing.legacy_index_migration import _migration_lock
from src.indexing.vector_compatibility_probe import COLLECTION, probe
from src.model_operations import model_operation_lock
from src.paths import MODELS_DIR
from src.qdrant_connection import QdrantConnection


def positive_int(value):
    """Parse a positive CLI integer."""
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("Must be positive")
    return result


def main(argv=None):
    """Write diagnostic evidence without any Qdrant or readiness-marker writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", required=True, type=Path,
                        help="Separately prepared candidate models, outside data/models")
    parser.add_argument("--report", required=True, type=Path, help="New JSON report; never overwrites")
    parser.add_argument("--sample-size", type=positive_int, default=128)
    parser.add_argument("--batch-size", type=positive_int, default=4)
    parser.add_argument("--top-k", type=positive_int, default=10)
    parser.add_argument("--queries", type=Path, help="UTF-8 text file, one search query per line")
    args = parser.parse_args(argv)
    candidate_dir = args.models_dir.expanduser().resolve()
    original_dir = MODELS_DIR.resolve()
    if candidate_dir == original_dir or original_dir in candidate_dir.parents or candidate_dir in original_dir.parents:
        parser.error("Use a separate candidate directory, e.g. data/models_candidate")
    if args.report.exists():
        parser.error("Report already exists; choose a new filename")
    queries = ([line.strip() for line in args.queries.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
               if args.queries else ["Schulsanierung", "Bebauungsplan", "Haushalt und Straßenbau"])
    if not queries:
        parser.error("Query file must contain at least one query")
    started = time.monotonic()
    report = {"result": "aborted", "migration_authorized": False,
              "started_at": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "executable": sys.executable,
              "platform": sys.platform, "candidate_models_dir": str(candidate_dir)}
    previous_models = os.environ.get("RATSI_MODELS_DIR")
    os.environ["RATSI_MODELS_DIR"] = str(candidate_dir)
    exit_code = 2
    try:
        with ExitStack() as stack:
            stack.enter_context(model_operation_lock())
            candidate = current_index_compatibility(candidate_dir, deep=True)
            inventory = load_and_validate_model_inventory(candidate_dir, deep=False)
            report["candidate_libraries"] = asdict(inventory.library_versions)
            connection = QdrantConnection.from_env()
            if not connection.url:
                raise ValueError("Probe requires Qdrant server mode; local storage is not opened")
            stack.enter_context(_migration_lock(connection, COLLECTION))
            marker_path = connection.release_path(COLLECTION)
            marker_bytes = marker_path.read_bytes()
            marker = json.loads(marker_bytes)
            stored = connection.read_index_compatibility(COLLECTION, require_ready=True)
            if stored is None or marker.get("ready") is not True:
                raise ValueError("Valid released reference marker required")
            client = connection.create_client()
            stack.callback(client.close)
            if marker.get("points_count") != client.count(collection_name=COLLECTION, exact=True).count:
                raise ValueError("Reference marker count does not match collection")
            from src.analysis.embeddings import HarrierEmbedder, _detect_device
            from src.analysis.bm25_sparse import BM25Encoder
            from src.indexing.vectorizer import HybridVectorizer
            dense, sparse = HarrierEmbedder(), BM25Encoder()
            report["device"] = _detect_device()
            print(f"Device: {report['device']}; sampling up to {args.sample_size} passages", flush=True)
            result = probe(client, stored, candidate, HybridVectorizer(dense, sparse), queries,
                           lambda text: {"dense_vector": dense.embed_query(text),
                                         "sparse_vector": sparse.encode_query(text)},
                           sample_size=args.sample_size, batch_size=args.batch_size, top_k=args.top_k)
            if marker_path.read_bytes() != marker_bytes:
                raise ValueError("Reference marker changed during probe")
            report.update(result)
            report["target"] = connection.target
            exit_code = 0 if result["result"] == "sample_matches" else 1
    except Exception as exc:
        report.update(result="aborted", error_type=type(exc).__name__, error=str(exc))
    finally:
        if previous_models is None:
            os.environ.pop("RATSI_MODELS_DIR", None)
        else:
            os.environ["RATSI_MODELS_DIR"] = previous_models
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(f"{report['result']}: {args.report}")
    if "error" in report:
        print(report["error"], file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
