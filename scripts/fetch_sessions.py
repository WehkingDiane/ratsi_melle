"""Command line helper to download sessions from the Melle SessionNet instance."""

from __future__ import annotations

import argparse
import logging
import sys
from time import perf_counter
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - defensive
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching import SessionNetClient  # noqa: E402  (import after sys.path manipulation)
from scripts._logging_utils import configure_file_logging  # noqa: E402


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
    months = tuple(months)
    total_sessions = 0
    for month_index, month in enumerate(months, start=1):
        logging.info("Fetching %04d month %02d (%d/%d)", year, month, month_index, len(months))
        references = client.fetch_month(year=year, month=month)
        logging.info("Found %d sessions for %04d-%02d", len(references), year, month)
        for session_index, reference in enumerate(references, start=1):
            logging.info("Fetching session %s (%d/%d in month)", reference.session_id, session_index, len(references))
            detail = client.fetch_session(reference)
            client.download_documents(detail)
            total_sessions += 1
    logging.info("Fetch complete: sessions=%d months=%d", total_sessions, len(months))


def main() -> None:
    args = parse_args()
    log_path = configure_file_logging(Path(__file__).stem, args.log_level)
    started = perf_counter()
    logging.info("Starting session fetch: year=%d log_file=%s", args.year, log_path)
    try:
        client = SessionNetClient(base_url=args.base_url)
        fetch_months(client, args.year, args.months)
    except Exception:
        logging.exception("Session fetch failed")
        raise
    finally:
        logging.info("Session fetch runtime: %.2f seconds", perf_counter() - started)


if __name__ == "__main__":  # pragma: no cover
    main()
