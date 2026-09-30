"""Inspect a legacy Qdrant collection or explicitly apply its verified report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.indexing.legacy_index_migration import LegacyMigrationError, apply_verified_legacy_report
from src.indexing.legacy_inspection_report import inspect_and_write_report
from src.indexing.legacy_index_inspection import LegacyInspectionError
from src.qdrant_connection import QdrantConnection


COLLECTIONS = ("ratsi_passages", "ratsi_documents", "landkreis_publications")


def main(argv: list[str] | None = None) -> int:
    """Require an explicit collection confirmation before any Qdrant write."""

    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true", help="Write a read-only inspection report")
    action.add_argument("--apply", action="store_true", help="Apply a verified report")
    parser.add_argument("--collection", required=True, choices=COLLECTIONS)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--confirm-collection", choices=COLLECTIONS,
                        help="Repeat the collection name to authorize payload and marker writes")
    args = parser.parse_args(argv)
    if args.apply and args.confirm_collection != args.collection:
        parser.error("--apply requires --confirm-collection matching --collection")
    if args.inspect and args.confirm_collection:
        parser.error("--inspect does not accept --confirm-collection")

    connection = QdrantConnection.from_env()
    client = connection.create_client()
    try:
        if args.inspect:
            result = inspect_and_write_report(connection, client, args.collection, args.report)
            print(json.dumps({"result": result["result"], "abort_code": result["abort_code"],
                              "report": str(args.report)}, ensure_ascii=False))
            return 0 if result["result"] == "verified" else 1
        result = apply_verified_legacy_report(
            connection, client, args.collection, args.report,
            confirm_collection=args.confirm_collection,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (LegacyMigrationError, LegacyInspectionError) as error:
        print(json.dumps({"result": "aborted", "abort_code": error.code}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
