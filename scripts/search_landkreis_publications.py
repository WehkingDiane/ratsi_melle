"""Search the separated Landkreis Osnabrueck publications database."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - direct CLI execution
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.landkreis import LandkreisPublicationStore
from src.paths import LANDKREIS_PUBLICATIONS_DB


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Search terms, e.g. 'Melle Genehmigung'.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of results.")
    parser.add_argument(
        "--db",
        type=Path,
        default=LANDKREIS_PUBLICATIONS_DB,
        help="SQLite database path (default: RATSI_LANDKREIS_DB or %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = LandkreisPublicationStore(args.db).search(args.query, limit=args.limit)
    for row in rows:
        date_value = row.get("date") or "-"
        source = row.get("source") or "-"
        print(f"{date_value} [{source}] {row.get('title')}")
        if row.get("snippet"):
            print(f"  {row['snippet']}")
        print(f"  {row.get('detail_url')}")


if __name__ == "__main__":
    main()
