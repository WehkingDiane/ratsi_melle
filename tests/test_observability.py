from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.observability import (
    RUN_ID_ENV,
    SafeFormatter,
    cli_log_level,
    configure_logging,
    run_cli,
)


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
