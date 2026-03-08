"""CLI helper to store human review decisions for analysis jobs."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.analysis.service import AnalysisService
from src.paths import LOCAL_INDEX_DB


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review an analysis job and store reviewer metadata.")
    parser.add_argument("job_id", type=int, help="analysis_jobs.id to review")
    parser.add_argument("--db", type=Path, default=LOCAL_INDEX_DB, help="Path to SQLite database")
    parser.add_argument("--reviewer", required=True, help="Reviewer identifier (e.g. name or mail)")
    parser.add_argument(
        "--status",
        default="approved",
        choices=("approved", "changes_requested", "rejected"),
        help="Review decision status",
    )
    parser.add_argument("--notes", default="", help="Optional review notes")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = AnalysisService()
    service.review_job(
        args.db,
        job_id=args.job_id,
        reviewer=args.reviewer,
        status=args.status,
        notes=args.notes,
    )
    print(f"Review gespeichert fuer Job {args.job_id} ({args.status})")


if __name__ == "__main__":
    main()
