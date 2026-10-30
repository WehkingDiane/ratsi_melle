"""Explicit service operation: update changed Ratsinfo documents, optionally rebuild or clean up."""

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.indexing.build_compatibility import IndexBuildCompatibilityError
from src.indexing.passage_builder import main as passage_main
from src.observability import cli_log_level, run_cli
from src.qdrant_connection import QdrantServerUnavailableError


def main(argv=None):
    """Run the deliberate content-update workflow, separate from normal builds."""
    try:
        passage_main(argv, maintenance=True)
    except (QdrantServerUnavailableError, IndexBuildCompatibilityError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    run_cli(Path(__file__).stem, main, log_level=cli_log_level(sys.argv[1:]))
