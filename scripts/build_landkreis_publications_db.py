"""Build the Landkreis publications SQLite database from local raw files."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - direct CLI execution
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.landkreis.builder import build_landkreis_publications_db
from src.paths import LANDKREIS_DATA_DIR, LANDKREIS_PUBLICATIONS_DB


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=LANDKREIS_DATA_DIR,
        help="Raw file storage root (default: RATSI_LANDKREIS_DATA_DIR or %(default)s).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=LANDKREIS_PUBLICATIONS_DB,
        help="SQLite database path (default: RATSI_LANDKREIS_DB or %(default)s).",
    )
    parser.add_argument(
        "--max-text-chars",
        type=_positive_int,
        default=200_000,
        help="Maximum extracted text characters per local document.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    publications, documents, extracted = build_landkreis_publications_db(
        data_root=args.data_dir,
        db_path=args.db,
        max_text_chars=args.max_text_chars,
    )
    print(
        "Built Landkreis DB: "
        f"publications={publications} documents={documents} extracted_documents={extracted}"
    )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


if __name__ == "__main__":
    main()
