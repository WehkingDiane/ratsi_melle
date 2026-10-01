"""Inspect a legacy Qdrant collection or explicitly apply its verified report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import grpc
import httpx
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.indexing.legacy_index_migration import LegacyMigrationError, apply_verified_legacy_report
from src.indexing.legacy_inspection_report import inspect_and_write_report
from src.indexing.legacy_index_inspection import LegacyInspectionError
from src.qdrant_connection import QdrantConnection, QdrantServerUnavailableError
from src.paths import QDRANT_DIR


COLLECTIONS = ("ratsi_passages", "ratsi_documents", "landkreis_publications")


def _local_store_exists(path: Path) -> bool:
    """Recognize an initialized local Qdrant store before opening its client."""

    metadata = path / "meta.json"
    if not path.is_dir() or metadata.is_symlink() or not metadata.is_file():
        return False
    try:
        stored = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    return (isinstance(stored, dict)
            and isinstance(stored.get("collections"), dict)
            and isinstance(stored.get("aliases"), dict))


def _abort_preflight(connection: QdrantConnection, args, code: str, *, inspection_options: dict) -> int:
    """Persist inspection failure without opening or modifying the Qdrant store."""

    if args.inspect:
        inspect_and_write_report(connection, None, args.collection, args.report,
                                 abort_code=code, **inspection_options)
    print(json.dumps({"result": "aborted", "abort_code": code}, ensure_ascii=False),
          file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Require an explicit collection confirmation before any Qdrant write."""

    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true", help="Write a read-only inspection report")
    action.add_argument("--apply", action="store_true", help="Apply a verified report")
    parser.add_argument("--collection", required=True, choices=COLLECTIONS)
    parser.add_argument("--qdrant-dir", type=Path, default=QDRANT_DIR,
                        help="Local storage when RATSI_QDRANT_MODE=local and RATSI_QDRANT_URL is unset")
    parser.add_argument("--source-db", type=Path,
                        help="Source SQLite database for a ratsi_documents legacy index")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--confirm-collection", choices=COLLECTIONS,
                        help="Repeat the collection name to authorize payload and marker writes")
    args = parser.parse_args(argv)
    if args.apply and args.confirm_collection != args.collection:
        parser.error("--apply requires --confirm-collection matching --collection")
    if args.inspect and args.confirm_collection:
        parser.error("--inspect does not accept --confirm-collection")
    if args.source_db is not None and args.collection != "ratsi_documents":
        parser.error("--source-db is only available for ratsi_documents")

    inspection_options = {"ratsinfo_db": args.source_db} if args.source_db is not None else {}
    connection = QdrantConnection.from_env(args.qdrant_dir)
    if args.collection == "landkreis_publications":
        return _abort_preflight(connection, args, "rebuild_required",
                                inspection_options=inspection_options)
    if not connection.url and not _local_store_exists(connection.path):
        return _abort_preflight(connection, args, "store_missing",
                                inspection_options=inspection_options)
    client = None
    try:
        client = connection.create_client()
        if args.inspect:
            result = inspect_and_write_report(connection, client, args.collection, args.report,
                                              **inspection_options)
            print(json.dumps({"result": result["result"], "abort_code": result["abort_code"],
                              "report": str(args.report)}, ensure_ascii=False))
            return 0 if result["result"] == "verified" else 1
        result = apply_verified_legacy_report(
            connection, client, args.collection, args.report,
            confirm_collection=args.confirm_collection, inspection_options=inspection_options,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except QdrantServerUnavailableError:
        return _abort_preflight(connection, args, "qdrant_unavailable",
                                inspection_options=inspection_options)
    except (ResponseHandlingException, httpx.TransportError, grpc.RpcError,
            ConnectionError, TimeoutError):
        if not connection.url:
            raise
        return _abort_preflight(connection, args, "qdrant_unavailable",
                                inspection_options=inspection_options)
    except UnexpectedResponse as error:
        if not connection.url or error.status_code is None or error.status_code < 500:
            raise
        return _abort_preflight(connection, args, "qdrant_unavailable",
                                inspection_options=inspection_options)
    except (LegacyMigrationError, LegacyInspectionError) as error:
        print(json.dumps({"result": "aborted", "abort_code": error.code}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
