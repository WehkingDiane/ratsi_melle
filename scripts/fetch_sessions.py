"""Command line helper to download sessions from the Melle SessionNet instance."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - defensive
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching import SessionNetClient  # noqa: E402  (import after sys.path manipulation)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, help="Year to fetch meetings for")
    parser.add_argument(
        "--months",
        type=int,
        nargs="*",
        default=tuple(range(1, 13)),
        help="Months to fetch (1-12). Defaults to the full year.",
    )
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default="https://session.melle.info/bi",
        help="Override the SessionNet base URL.",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Python logging level",
    )
    return parser.parse_args()


def fetch_months(client: SessionNetClient, year: int, months: Iterable[int]) -> None:
    for month in months:
        references = client.fetch_month(year=year, month=month)
        for reference in references:
            detail = client.fetch_session(reference)
            documents = [doc for item in detail.agenda_items for doc in item.documents]
            client.download_documents(documents, reference)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    client = SessionNetClient(base_url=args.base_url)
    fetch_months(client, args.year, args.months)


if __name__ == "__main__":  # pragma: no cover
    main()

