"""Check the configured local embedding model inventory without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    EmbeddingModelStatus,
    check_embedding_model_status,
)
from src.config.settings import (
    EmbeddingModelSettingsError,
    load_embedding_model_settings,
)


def _print_status(status: EmbeddingModelStatus, *, deep: bool, json_output: bool) -> None:
    if json_output:
        payload = {**status.as_dict(), "check_level": "deep" if deep else "fast"}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        label = "Tiefenpruefung" if deep else "Schnellpruefung"
        print(f"{label}: {status.state.value} - {status.message}")
        if status.manifest_sha256 is not None:
            print(f"Manifest-SHA-256: {status.manifest_sha256}")


def main(argv: list[str] | None = None) -> int:
    """Check local models and return 0 if ready, 1 if unusable, or 2 on usage errors."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        required=True,
        help="Lokalen Modellbestand ohne Netzwerkzugriff pruefen.",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Zusaetzlich alle festgelegten Artefakt-SHA-256-Werte pruefen.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Status als einzelnes JSON-Objekt statt als CLI-Meldung ausgeben.",
    )
    args = parser.parse_args(argv)
    try:
        settings = load_embedding_model_settings()
    except EmbeddingModelSettingsError as error:
        if args.json:
            _print_status(
                EmbeddingModelStatus(EmbeddingModelReadiness.INCOMPATIBLE, str(error)),
                deep=args.deep,
                json_output=True,
            )
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    status = check_embedding_model_status(settings.models_dir, deep=args.deep)
    _print_status(status, deep=args.deep, json_output=args.json)
    return 0 if status.state is EmbeddingModelReadiness.READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
