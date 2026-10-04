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
    django_logging_config,
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


@pytest.mark.parametrize("configuration", ["cli", "web"])
def test_http_diagnostics_remain_in_file_without_console_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, configuration: str
) -> None:
    monkeypatch.setenv("RATSI_LOG_DIR", str(tmp_path))
    monkeypatch.setenv(LOG_LEVEL_ENV, "DEBUG")
    if configuration == "cli":
        log_path = configure_logging("quiet_http", log_dir=tmp_path)
    else:
        from logging.config import DictConfigurator

        configurator = DictConfigurator(django_logging_config("quiet_http"))
        for name in list(configurator.config["filters"]):
            configurator.config["filters"][name] = configurator.configure_filter(
                configurator.config["filters"][name]
            )
        for name in list(configurator.config["formatters"]):
            configurator.config["formatters"][name] = configurator.configure_formatter(
                configurator.config["formatters"][name]
            )
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        for name in ("console", "file"):
            handler = configurator.configure_handler(configurator.config["handlers"][name])
            handler._ratsi_handler = True
            root.addHandler(handler)
        log_path = tmp_path / "quiet_http.log"

    for name in ("httpx", "httpx.transport", "httpcore", "httpcore.connection"):
        logger = logging.getLogger(name)
        logger.debug("%s debug request", name)
        logger.info("%s successful request", name)
        logger.warning("%s request warning", name)
        logger.error("%s request failed", name)
    logging.getLogger("build_vector_index").info("event=run_completed status=ok")
    logging.getLogger("httpx_application").info("application message")

    terminal = capsys.readouterr().err
    content = log_path.read_text(encoding="utf-8")
    for name in ("httpx", "httpx.transport", "httpcore", "httpcore.connection"):
        assert f"{name} debug request" not in terminal
        assert f"{name} successful request" not in terminal
        assert f"{name} debug request" in content
        assert f"{name} successful request" in content
        assert f"{name} request warning" in terminal
        assert f"{name} request failed" in terminal
    assert "event=run_completed status=ok" in terminal
    assert "application message" in terminal


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
