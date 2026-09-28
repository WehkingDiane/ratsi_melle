"""CLI checks of local model inventories using controlled files and blocked network."""

from pathlib import Path
import os
import socket
import subprocess
import sys
import urllib.request

import pytest

from scripts import prepare_embedding_models as cli
from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    EmbeddingModelStatus,
)


@pytest.mark.parametrize("state", list(EmbeddingModelReadiness))
def test_check_uses_shared_status_and_configured_directory(tmp_path, monkeypatch, capsys, state):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path))
    expected = EmbeddingModelStatus(state, "Testmeldung")

    def check_status(models_dir):
        assert models_dir == tmp_path
        return expected

    monkeypatch.setattr(cli, "check_embedding_model_status", check_status)

    assert cli.main(["--check"]) == (0 if state is EmbeddingModelReadiness.READY else 1)
    output = capsys.readouterr()
    assert output.out == f"{state.value}: Testmeldung\n"
    assert output.err == ""


def test_check_missing_inventory_stays_offline_and_does_not_create_directory(
    tmp_path, monkeypatch, capsys,
):
    models_dir = tmp_path / "absent_models"
    monkeypatch.setenv("RATSI_MODELS_DIR", str(models_dir))

    def reject_network(*args, **kwargs):
        raise AssertionError("Local CLI checks must remain offline")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)

    assert cli.main(["--check"]) == 1
    assert capsys.readouterr().out.startswith("fehlt:")
    assert not models_dir.exists()


def test_check_invalid_settings_reports_short_error(monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", " ")

    assert cli.main(["--check"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "RATSI_MODELS_DIR" in output.err
    assert "Traceback" not in output.err


@pytest.mark.integration
def test_script_can_be_called_from_another_working_directory(tmp_path):
    script = Path(cli.__file__).resolve()
    environment = dict(os.environ, RATSI_MODELS_DIR=str(tmp_path / "absent_models"))
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert result.stdout.startswith("fehlt:")
    assert result.stderr == ""
