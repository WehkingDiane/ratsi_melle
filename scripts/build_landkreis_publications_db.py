"""Build the Landkreis publications SQLite database from local raw files."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from time import perf_counter


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - direct CLI execution
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.landkreis.builder import build_landkreis_publications_db
from src.paths import LANDKREIS_DATA_DIR, LANDKREIS_PUBLICATIONS_DB
from scripts._logging_utils import configure_file_logging


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
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_path = configure_file_logging(Path(__file__).stem, args.log_level)
    started = perf_counter()
    logging.info("Starting Landkreis database build: data_root=%s output=%s log_file=%s", args.data_dir, args.db, log_path)
    try:
        publications, documents, extracted = build_landkreis_publications_db(
            data_root=args.data_dir,
            db_path=args.db,
            max_text_chars=args.max_text_chars,
        )
        logging.info(
            "Build complete: publications=%d documents=%d extracted_documents=%d",
            publications, documents, extracted,
        )
        print(
            "Built Landkreis DB: "
            f"publications={publications} documents={documents} extracted_documents={extracted}"
        )
    except Exception:
        logging.exception("Landkreis database build failed")
        raise
    finally:
        logging.info("Landkreis database build runtime: %.2f seconds", perf_counter() - started)


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
