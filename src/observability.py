"""Shared logging and run diagnostics for CLI and web processes."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
from time import gmtime, perf_counter
from typing import Callable, TypeVar
from uuid import uuid4

from src.paths import REPO_ROOT


LOG_FORMAT = (
    "%(asctime)sZ %(levelname)s component=%(component)s run_id=%(run_id)s "
    "logger=%(name)s %(message)s"
)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
DEFAULT_LOG_LEVEL = "INFO"
RUN_ID_ENV = "RATSI_RUN_ID"
LOG_LEVEL_ENV = "RATSI_LOG_LEVEL"
LOG_DIR_ENV = "RATSI_LOG_DIR"
_URL_CREDENTIALS = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)
_T = TypeVar("_T")


def normalize_log_level(value: str | None) -> int:
    """Return a supported logging level, falling back to INFO."""

    level = getattr(logging, str(value or DEFAULT_LOG_LEVEL).upper(), None)
    return level if isinstance(level, int) else logging.INFO


def current_run_id() -> str:
    """Return the inherited run ID or create one for this process tree."""

    run_id = os.environ.get(RUN_ID_ENV, "").strip()
    if not run_id:
        run_id = uuid4().hex[:12]
        os.environ[RUN_ID_ENV] = run_id
    return run_id


def log_directory() -> Path:
    """Return the configured runtime log directory."""

    configured = os.environ.get(LOG_DIR_ENV, "").strip()
    return Path(configured).expanduser() if configured else REPO_ROOT / "logs"


def cli_log_level(arguments: list[str]) -> str | None:
    """Read ``--log-level`` from CLI arguments without owning their parser."""

    for index, argument in enumerate(arguments):
        if argument.startswith("--log-level="):
            return argument.partition("=")[2]
        if argument == "--log-level" and index + 1 < len(arguments):
            return arguments[index + 1]
    return None


class ContextFilter(logging.Filter):
    """Attach stable component and run identifiers to every record."""

    def __init__(self, component: str = "application", run_id: str | None = None) -> None:
        super().__init__()
        self.component = component
        self.run_id = run_id or current_run_id()

    def filter(self, record: logging.LogRecord) -> bool:
        record.component = getattr(record, "component", self.component)
        record.run_id = getattr(record, "run_id", self.run_id)
        return True


class ConsoleNoiseFilter(logging.Filter):
    """Keep routine HTTP diagnostics in files and warnings on the console."""

    def filter(self, record: logging.LogRecord) -> bool:
        is_http_client = any(
            record.name == name or record.name.startswith(f"{name}.")
            for name in ("httpx", "httpcore")
        )
        return not is_http_client or record.levelno >= logging.WARNING


class SafeFormatter(logging.Formatter):
    """Format records consistently and hide URL user-info from diagnostics."""

    converter = gmtime

    def format(self, record: logging.LogRecord) -> str:
        return _URL_CREDENTIALS.sub(r"\1[redacted]@", super().format(record))


def configure_logging(
    component: str,
    log_level: str | None = None,
    *,
    log_dir: Path | None = None,
    console: bool = True,
) -> Path:
    """Configure bounded file logging and optional stderr output."""

    directory = Path(log_dir) if log_dir is not None else log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / f"{component}.log"
    level = normalize_log_level(log_level or os.environ.get(LOG_LEVEL_ENV))
    context_filter = ContextFilter(component)
    formatter = SafeFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in root.handlers[:]:
        if getattr(handler, "_ratsi_handler", False) or any(
            isinstance(item, ContextFilter) for item in handler.filters
        ):
            root.removeHandler(handler)
            handler.close()

    handlers: list[logging.Handler] = []
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.addFilter(ConsoleNoiseFilter())
        handlers.append(console_handler)
    handlers.append(
        RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    )
    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)
        handler._ratsi_handler = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    return log_path


def django_logging_config(component: str = "web") -> dict[str, object]:
    """Return Django logging settings matching the CLI format."""

    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    level = normalize_log_level(os.environ.get(LOG_LEVEL_ENV))
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {
                "()": "src.observability.ContextFilter",
                "component": component,
            },
            "console_noise": {"()": "src.observability.ConsoleNoiseFilter"},
        },
        "formatters": {
            "ratsi": {
                "()": "src.observability.SafeFormatter",
                "format": LOG_FORMAT,
                "datefmt": DATE_FORMAT,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "filters": ["context", "console_noise"],
                "formatter": "ratsi",
                "level": level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(directory / f"{component}.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
                "filters": ["context"],
                "formatter": "ratsi",
                "level": level,
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": level,
        },
        "loggers": {"django.server": {"level": "ERROR", "propagate": True}},
    }


def run_cli(
    component: str,
    operation: Callable[[], _T],
    *,
    log_level: str | None = None,
) -> _T:
    """Run a CLI operation with common lifecycle and exception diagnostics."""

    log_path = configure_logging(component, log_level)
    logger = logging.getLogger(component)
    started = perf_counter()
    logger.info("event=run_started log_file=%s", log_path)
    try:
        result = operation()
    except SystemExit as exc:
        if exc.code in (None, 0):
            logger.info(
                "event=run_completed status=ok duration_seconds=%.3f",
                perf_counter() - started,
            )
        else:
            logger.error(
                "event=run_failed exit_code=%s duration_seconds=%.3f",
                exc.code,
                perf_counter() - started,
            )
        raise
    except Exception as exc:
        from src.config.embedding_model_status import PreparedModelUnavailableError

        if not isinstance(exc, PreparedModelUnavailableError):
            logger.exception(
                "event=run_failed duration_seconds=%.3f", perf_counter() - started
            )
            raise
        logger.error("event=run_failed reason=local_models_unavailable")
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except BaseException:
        logger.exception(
            "event=run_failed duration_seconds=%.3f", perf_counter() - started
        )
        raise
    logger.info(
        "event=run_completed status=ok duration_seconds=%.3f",
        perf_counter() - started,
    )
    return result
