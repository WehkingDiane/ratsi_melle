"""Check the configured local embedding model inventory without network access."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    check_embedding_model_status,
)
from src.config.settings import (
    EmbeddingModelSettingsError,
    load_embedding_model_settings,
)


def main(argv: list[str] | None = None) -> int:
    """Check local models and return 0 if ready, 1 if unusable, or 2 on usage errors."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        required=True,
        help="Lokalen Modellbestand ohne Netzwerkzugriff pruefen.",
    )
    parser.parse_args(argv)
    try:
        settings = load_embedding_model_settings()
    except EmbeddingModelSettingsError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    status = check_embedding_model_status(settings.models_dir)
    print(f"{status.state.value}: {status.message}")
    return 0 if status.state is EmbeddingModelReadiness.READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
