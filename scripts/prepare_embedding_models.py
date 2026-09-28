"""Check local embedding models offline or explicitly download pinned candidates."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
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
from src.embedding_model_preparation import EmbeddingModelDownloadError, download_embedding_models


def _print_status(status: EmbeddingModelStatus, *, deep: bool, json_output: bool) -> None:
    if json_output:
        payload = {**status.as_dict(), "check_level": "deep" if deep else "fast"}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        label = "Tiefenpruefung" if deep else "Schnellpruefung"
        print(f"{label}: {status.state.value} - {status.message}")
        if status.manifest_sha256 is not None:
            print(f"Manifest-SHA-256: {status.manifest_sha256}")


def _print_download_error(message: str, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps({"operation": "download", "status": "fehlgeschlagen", "message": message}))
    else:
        print(f"ERROR: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Return 0 on successful checks/downloads, 1 on failure, or 2 on usage errors."""

    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check",
        action="store_true",
        help="Lokalen Modellbestand ohne Netzwerkzugriff pruefen.",
    )
    action.add_argument(
        "--download",
        action="store_true",
        help="Gepinnte Artefakte in einen separaten Vorbereitungsordner herunterladen.",
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
    if args.deep and not args.check:
        parser.error("--deep ist nur zusammen mit --check erlaubt.")
    try:
        settings = load_embedding_model_settings()
    except EmbeddingModelSettingsError as error:
        if args.download:
            _print_download_error(str(error), json_output=args.json)
        elif args.json:
            _print_status(
                EmbeddingModelStatus(EmbeddingModelReadiness.INCOMPATIBLE, str(error)),
                deep=args.deep,
                json_output=True,
            )
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if args.download:
        try:
            # Hub progress output must not mix with a machine-readable result.
            with redirect_stdout(sys.stderr):
                result = download_embedding_models(settings.models_dir)
        except EmbeddingModelDownloadError as error:
            _print_download_error(str(error), json_output=args.json)
            return 1
        if args.json:
            print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(result.as_dict()["message"])
            print(f"Vorbereitungsordner: {result.staging_dir}")
            for snapshot in result.snapshots:
                print(f"{snapshot.model_id}: {snapshot.revision}")
        return 0

    status = check_embedding_model_status(settings.models_dir, deep=args.deep)
    _print_status(status, deep=args.deep, json_output=args.json)
    return 0 if status.state is EmbeddingModelReadiness.READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
