"""CLI wrapper for exporting analysis batches from SQLite index data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - defensive
    sys.path.insert(0, str(REPO_ROOT))

from src.analysis.batch_exporter import (  # noqa: E402
    ALLOWED_DOCUMENT_TYPES,
    _normalize_document_types,
    export_analysis_batch,
    resolve_local_file_path,
)
from src.data_layout import migrate_legacy_database_layout  # noqa: E402
from src.paths import DEFAULT_ANALYSIS_BATCH, LOCAL_INDEX_DB  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=LOCAL_INDEX_DB,
        help="Path to source SQLite index database.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ANALYSIS_BATCH,
        help="Path to JSON output file.",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        dest="session_ids",
        help="Restrict export to one or more session IDs.",
    )
    parser.add_argument(
        "--committee",
        action="append",
        default=[],
        dest="committees",
        help="Restrict export to one or more committee names.",
    )
    parser.add_argument(
        "--date-from",
        default=None,
        help="Lower date bound (inclusive), format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--date-to",
        default=None,
        help="Upper date bound (inclusive), format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--document-type",
        action="append",
        default=[],
        dest="document_types",
        help="Restrict export to one or more document types.",
    )
    parser.add_argument(
        "--require-local-path",
        action="store_true",
        help="Export only rows with a non-empty local_path.",
    )
    parser.add_argument(
        "--include-text-extraction",
        action="store_true",
        help="Extract local document text and include extraction quality metadata.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=12000,
        help="Maximum number of extracted characters included per document.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrate_legacy_database_layout()
    count = export_analysis_batch(
        args.db_path,
        args.output,
        session_ids=args.session_ids,
        committees=args.committees,
        date_from=args.date_from,
        date_to=args.date_to,
        document_types=args.document_types,
        require_local_path=args.require_local_path,
        include_text_extraction=args.include_text_extraction,
        max_text_chars=args.max_text_chars,
    )
    print(f"Exported {count} documents to {args.output}")


if __name__ == "__main__":  # pragma: no cover
    main()
