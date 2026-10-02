"""Inspect a legacy Qdrant collection or explicitly apply its verified report."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys

import grpc
import httpx
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.indexing.legacy_index_migration import LegacyMigrationError, apply_verified_legacy_report, _migration_lock, _read_report
from src.indexing.legacy_inspection_report import inspect_and_write_report
from src.indexing.legacy_index_inspection import LegacyInspectionError
from src.qdrant_connection import QdrantConnection, QdrantServerUnavailableError
from src.paths import QDRANT_DIR, LOCAL_INDEX_DB
from src.model_operations import locked_model_operation, model_preparation_binding
from src.indexing.legacy_index_inspection import target_sha256
from src.observability import RUN_ID_ENV


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
          file=sys.stdout if os.environ.get("RATSI_LEGACY_APPLY_CONTEXT") is not None else sys.stderr)
    return 1


@locked_model_operation
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
    web_context = os.environ.get("RATSI_LEGACY_INSPECTION_CONTEXT")
    web_apply = os.environ.get("RATSI_LEGACY_APPLY_CONTEXT")
    expected_report_sha256 = None
    if web_context is not None:
        try:
            expected = json.loads(web_context)
            actual = {
                "collection": args.collection, "target": connection.target,
                "target_sha256": target_sha256(connection),
                "qdrant_dir": str(args.qdrant_dir.resolve()),
                "source_db": str((args.source_db or LOCAL_INDEX_DB).resolve()) if args.collection == "ratsi_documents" else None,
                "report_root": expected["report_root"], "model_binding": model_preparation_binding(),
            }
            report_path = Path(expected["report_root"]) / f"{os.environ[RUN_ID_ENV]}.json"
            if (not args.inspect or args.collection not in {"ratsi_passages", "ratsi_documents"}
                    or expected != actual or args.report != report_path or args.report.exists()):
                raise ValueError("Changed inspection binding")
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            print(json.dumps({"result": "aborted", "abort_code": "configuration_changed"}))
            return 1
    if web_apply is not None:
        try:
            payload = json.loads(web_apply)
            expected = payload["inspection_context"]
            identifier = payload["inspection_job_id"]
            digest = payload["report_sha256"]
            actual = {
                "collection": args.collection, "target": connection.target,
                "target_sha256": target_sha256(connection),
                "qdrant_dir": str(args.qdrant_dir.resolve()),
                "source_db": str((args.source_db or LOCAL_INDEX_DB).resolve()) if args.collection == "ratsi_documents" else None,
                "report_root": expected["report_root"], "model_binding": model_preparation_binding(),
            }
            if (set(payload) != {"inspection_context", "inspection_job_id", "report_sha256"}
                    or not args.apply or args.collection not in {"ratsi_passages", "ratsi_documents"}
                    or expected != actual or not isinstance(identifier, str) or len(identifier) != 12
                    or any(c not in "0123456789abcdef" for c in identifier)
                    or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
                    or args.report != Path(expected["report_root"]) / f"{identifier}.json"):
                raise ValueError("Changed application binding")
            expected_report_sha256 = digest
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            print(json.dumps({"result": "aborted", "abort_code": "configuration_changed"}))
            return 1
    if args.collection == "landkreis_publications":
        return _abort_preflight(connection, args, "rebuild_required",
                                inspection_options=inspection_options)
    if not connection.url and not _local_store_exists(connection.path):
        return _abort_preflight(connection, args, "store_missing",
                                inspection_options=inspection_options)
    client = None
    operations = ExitStack()
    try:
        if args.apply:
            operations.enter_context(_migration_lock(connection, args.collection))
            if expected_report_sha256 is not None:
                _read_report(args.report, expected_report_sha256=expected_report_sha256)
        client = connection.create_client()
        if args.inspect:
            result = inspect_and_write_report(connection, client, args.collection, args.report,
                                              **inspection_options)
            print(json.dumps({"result": result["result"], "abort_code": result["abort_code"],
                              "report": str(args.report)}, ensure_ascii=False))
            return 0 if result["result"] == "verified" else 1
        options = {"expected_report_sha256": expected_report_sha256} if expected_report_sha256 is not None else {}
        result = apply_verified_legacy_report(
            connection, client, args.collection, args.report,
            confirm_collection=args.confirm_collection, inspection_options=inspection_options, **options,
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
              file=sys.stdout if web_apply is not None else sys.stderr)
        return 1
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            operations.close()


if __name__ == "__main__":
    raise SystemExit(main())
