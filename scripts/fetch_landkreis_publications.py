"""Fetch Landkreis Osnabrueck raw publication data."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - direct CLI execution
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.landkreis import LandkreisClient, LandkreisStorage
from src.paths import LANDKREIS_DATA_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=("bekanntmachungen", "amtsblaetter", "all"),
        default="all",
        help="Landkreis publication source to fetch.",
    )
    parser.add_argument("--from-date", type=_parse_date, default=None, help="Earliest publication date YYYY-MM-DD.")
    parser.add_argument("--to-date", type=_parse_date, default=None, help="Latest publication date YYYY-MM-DD.")
    parser.add_argument("--query", default=None, help="Only fetch list entries whose title contains this text.")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Maximum number of matching entries.")
    parser.add_argument("--dry-run", action="store_true", help="Parse list pages without downloading detail pages or documents.")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Refetch detail HTML. Amtsblatt PDFs that already exist locally are still reused.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=LANDKREIS_DATA_DIR,
        help="Raw file storage root (default: RATSI_LANDKREIS_DATA_DIR or %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage = LandkreisStorage(args.data_dir)
    client = LandkreisClient(storage=storage)
    publications = client.crawl(
        source=args.source,
        from_date=args.from_date,
        to_date=args.to_date,
        query=args.query,
        limit=args.limit,
        dry_run=args.dry_run,
        refresh_existing=args.refresh_existing,
    )
    action = "Matched" if args.dry_run else "Fetched raw data for"
    print(f"{action} {len(publications)} Landkreis publication(s).")
    if args.dry_run:
        for publication in publications:
            print(f"{publication.date or '-'} {publication.source}: {publication.title}")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must use YYYY-MM-DD") from exc


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
