from __future__ import annotations

import argparse
from collections.abc import Callable
import logging
import sys
from pathlib import Path

import pytest

from src.observability import (
    LOG_LEVEL_ENV,
    RUN_ID_ENV,
    SafeFormatter,
    cli_log_level,
    configure_logging,
    run_cli,
)
from scripts import (
    build_landkreis_publications_db,
    build_local_index,
    build_online_index_db,
    fetch_landkreis_publications,
    fetch_session_from_index,
    fetch_sessions,
)
from scripts._logging_utils import configure_file_logging


def _remove_ratsi_handlers() -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if getattr(handler, "_ratsi_handler", False):
            root.removeHandler(handler)
            handler.close()


@pytest.fixture(autouse=True)
def cleanup_logging() -> None:
    yield
    _remove_ratsi_handlers()


def test_configure_logging_adds_context_and_redacts_url_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RUN_ID_ENV, "job-123")
    log_path = configure_logging("test_component", "INFO", log_dir=tmp_path, console=False)

    logging.getLogger("test.logger").info("Connecting to https://user:secret@example.test/path")
    _remove_ratsi_handlers()

    content = log_path.read_text(encoding="utf-8")
    assert "component=test_component run_id=job-123 logger=test.logger" in content
    assert "https://[redacted]@example.test/path" in content
    assert "secret" not in content


def test_run_cli_records_failed_operation_with_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATSI_LOG_DIR", str(tmp_path))
    monkeypatch.setenv(RUN_ID_ENV, "failed-run")

    def fail() -> None:
        raise RuntimeError("diagnostic detail")

    with pytest.raises(RuntimeError, match="diagnostic detail"):
        run_cli("failing_command", fail)
    _remove_ratsi_handlers()

    content = (tmp_path / "failing_command.log").read_text(encoding="utf-8")
    assert "event=run_started" in content
    assert "event=run_failed" in content
    assert "Traceback" in content
    assert "diagnostic detail" in content


def test_run_cli_records_successful_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATSI_LOG_DIR", str(tmp_path))
    monkeypatch.setenv(RUN_ID_ENV, "successful-run")

    assert run_cli("successful_command", lambda: 42) == 42
    _remove_ratsi_handlers()

    content = (tmp_path / "successful_command.log").read_text(encoding="utf-8")
    assert "event=run_started" in content
    assert "event=run_completed status=ok" in content


def test_cli_log_level_supports_both_argument_forms() -> None:
    assert cli_log_level(["--log-level", "DEBUG"]) == "DEBUG"
    assert cli_log_level(["--log-level=WARNING"]) == "WARNING"
    assert cli_log_level([]) is None


@pytest.mark.parametrize(
    ("parse_args", "arguments"),
    [
        (fetch_sessions.parse_args, ["fetch_sessions.py", "2026"]),
        (fetch_session_from_index.parse_args, ["fetch_session_from_index.py"]),
        (build_local_index.parse_args, ["build_local_index.py"]),
        (build_online_index_db.parse_args, ["build_online_index_db.py", "2026"]),
        (
            fetch_landkreis_publications.parse_args,
            ["fetch_landkreis_publications.py"],
        ),
        (
            build_landkreis_publications_db.parse_args,
            ["build_landkreis_publications_db.py"],
        ),
    ],
)
def test_legacy_cli_omits_log_level_by_default(
    parse_args: Callable[[], argparse.Namespace],
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", arguments)

    assert parse_args().log_level is None


def test_legacy_logging_uses_environment_level_when_cli_option_is_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATSI_LOG_DIR", str(tmp_path))
    monkeypatch.setenv(LOG_LEVEL_ENV, "DEBUG")

    configure_file_logging("legacy_command", None)

    assert logging.getLogger().level == logging.DEBUG


def test_explicit_log_level_overrides_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "DEBUG")

    configure_logging("explicit_level", "WARNING", log_dir=tmp_path, console=False)

    assert logging.getLogger().level == logging.WARNING


def test_cli_logging_replaces_existing_django_context(tmp_path, monkeypatch):
    from src.observability import ContextFilter
    root = logging.getLogger()
    old = logging.StreamHandler()
    old.addFilter(ContextFilter("web", "old-web-run"))
    root.addHandler(old)
    monkeypatch.setenv(RUN_ID_ENV, "new-cli-run")
    try:
        path = configure_logging("cli", log_dir=tmp_path, console=False)
        logging.getLogger("test.context").warning("replacement context")
        assert old not in root.handlers
        content = path.read_text()
        assert "component=cli run_id=new-cli-run" in content
        assert "old-web-run" not in content
    finally:
        root.removeHandler(old)
        old.close()
