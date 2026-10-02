"""Check local embedding models offline or explicitly prepare pinned models."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
import logging
import os
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
from src.embedding_model_preparation import (
    EmbeddingModelDownloadError, preparation_error, prepare_embedding_models,
)
from src.observability import configure_logging
from src.model_operations import model_operation_lock, model_preparation_binding


def _print_status(status: EmbeddingModelStatus, *, deep: bool, json_output: bool) -> None:
    if json_output:
        payload = {**status.as_dict(), "check_level": "deep" if deep else "fast"}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        label = "Tiefenpruefung" if deep else "Schnellpruefung"
        print(f"{label}: {status.state.value} - {status.message}")
        if status.manifest_sha256 is not None:
            print(f"Manifest-SHA-256: {status.manifest_sha256}")


def _print_download_error(
    message: str, *, json_output: bool, error_code: str = "configuration_error",
) -> None:
    if json_output:
        print(json.dumps({
            "operation": "download", "status": "fehlgeschlagen",
            "message": message, "error_code": error_code,
        }))
    else:
        print(f"ERROR: {message}", file=sys.stderr)


def _ignore_log_write_failure(record: logging.LogRecord) -> None:
    # A full log filesystem must not produce a logging traceback or conceal the
    # short preparation result that is still written to stdout/stderr.
    pass


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
        help="Gepinnte Artefakte herunterladen, pruefen und atomar freigeben.",
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
    parser.add_argument(
        "--log-level", type=str.upper,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Loglevel fuer die Vorbereitung; sonst RATSI_LOG_LEVEL oder INFO.",
    )
    args = parser.parse_args(argv)
    if args.deep and not args.check:
        parser.error("--deep ist nur zusammen mit --check erlaubt.")
    if args.download:
        try:
            configure_logging("embedding_model_preparation", args.log_level, console=False)
            for handler in logging.getLogger().handlers:
                if getattr(handler, "_ratsi_handler", False):
                    handler.addFilter(logging.Filter("embedding_model_preparation"))
                    handler.handleError = _ignore_log_write_failure
        except (OSError, RuntimeError) as error:
            failure = preparation_error(error, phase="logging")
            _print_download_error(str(failure), json_output=args.json, error_code=failure.error_code)
            return 1
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
                with model_operation_lock(settings.models_dir):
                    expected = os.environ.get("RATSI_MODEL_PREPARATION_BINDING")
                    if expected is not None and expected != model_preparation_binding(settings.models_dir):
                        raise EmbeddingModelDownloadError(
                            "Modellkonfiguration wurde geändert. Vorbereitung erneut bestätigen.",
                            error_code="confirmation_changed",
                        )
                    result = prepare_embedding_models(settings.models_dir)
        except EmbeddingModelDownloadError as error:
            _print_download_error(str(error), json_output=args.json, error_code=error.error_code)
            return 1
        except (OSError, RuntimeError) as error:
            failure = preparation_error(error, phase="prepare")
            _print_download_error(str(failure), json_output=args.json, error_code=failure.error_code)
            return 1
        logging.getLogger("embedding_model_preparation").info(
            "event=model_preparation_completed status=ready reused=%s", result.reused,
        )
        if args.json:
            print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(result.as_dict()["message"])
            print(f"Modellbestand: {result.inventory_dir}")
            print(f"Manifest-SHA-256: {result.manifest.manifest_sha256}")
        return 0

    status = check_embedding_model_status(settings.models_dir, deep=args.deep)
    _print_status(status, deep=args.deep, json_output=args.json)
    return 0 if status.state is EmbeddingModelReadiness.READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
