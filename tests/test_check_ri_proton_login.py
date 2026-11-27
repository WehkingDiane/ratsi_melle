"""Login checks use fake tokens and CLI calls, never the actual credential store."""

from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from scripts.setup import check_ri_proton_login as check

TOKEN = "pst_synthetic::synthetic-key"


def test_login_isolated_and_token_only_passed_to_login(monkeypatch, capsys):
    calls = []
    monkeypatch.setenv("PROTON_PASS_SESSION_DIR", "/personal/session")
    monkeypatch.setenv("PROTON_PASS_PASSWORD", "account-secret")
    monkeypatch.setenv("PROTON_PASS_KEY_PROVIDER", "fs")
    monkeypatch.setattr(check.sys, "platform", "win32")

    def run(args, **kwargs):
        calls.append((args, dict(kwargs["env"])))
        output = f"[vault-id] RI Testtresor\n{TOKEN}" if args[1] == "vault" else TOKEN
        return SimpleNamespace(returncode=0, stdout=output, stderr=TOKEN)

    monkeypatch.setattr(check.subprocess, "run", run)
    assert check.test_login("pass-cli.exe", TOKEN) is True
    assert [args[1] for args, env in calls] == ["login", "vault", "logout"]
    login_env, vault_env, logout_env = [env for args, env in calls]
    assert login_env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] == TOKEN
    assert "PROTON_PASS_PERSONAL_ACCESS_TOKEN" not in vault_env
    assert "PROTON_PASS_PERSONAL_ACCESS_TOKEN" not in logout_env
    assert "PROTON_PASS_PASSWORD" not in login_env
    assert login_env["PROTON_PASS_KEY_PROVIDER"] == "fs"
    assert login_env["PROTON_PASS_SESSION_DIR"] != "/personal/session"
    assert login_env["PROTON_PASS_SESSION_DIR"] == logout_env["PROTON_PASS_SESSION_DIR"]
    assert not Path(login_env["PROTON_PASS_SESSION_DIR"]).exists()
    assert TOKEN not in repr([args for args, env in calls])
    output = capsys.readouterr()
    assert TOKEN not in output.out + output.err
    assert "RI Testtresor" in output.out
    assert check.os.environ["PROTON_PASS_SESSION_DIR"] == "/personal/session"


@pytest.mark.parametrize("outcome", ["failed", "timeout"])
def test_login_failure_still_attempts_logout_without_exposing_output(monkeypatch, capsys, outcome):
    calls = []

    def run(args, **kwargs):
        calls.append(args[1])
        if args[1] == "login":
            if outcome == "timeout":
                raise subprocess.TimeoutExpired(args, 45, output=TOKEN)
            return SimpleNamespace(returncode=1, stdout=TOKEN, stderr=TOKEN)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(check.subprocess, "run", run)
    with pytest.raises(check.SetupError) as error:
        check.test_login("fake-cli", TOKEN)
    assert calls == ["login", "logout"]
    assert TOKEN not in str(error.value) + repr(capsys.readouterr())


def test_logout_failure_uses_force_cleanup_and_reports_remote_uncertainty(monkeypatch, capsys):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        failed = args[1:] == ["logout"]
        return SimpleNamespace(returncode=int(failed), stdout="RI Testtresor", stderr="HTTP 403 " + TOKEN)

    monkeypatch.setattr(check.subprocess, "run", run)
    assert check.test_login("fake-cli", TOKEN) is False
    assert calls[-1] == ["fake-cli", "logout", "--force"]
    output = capsys.readouterr()
    assert "entfernte Testsitzung kann bis zum Ablauf bestehen bleiben" in output.out
    assert "Temporäre Testsitzung abgemeldet." not in output.out
    assert TOKEN not in output.out + output.err


def test_force_cleanup_failure_is_reported(monkeypatch):
    def run(args, **kwargs):
        return SimpleNamespace(returncode=int(args[1] == "logout"), stdout="", stderr="")

    monkeypatch.setattr(check.subprocess, "run", run)
    with pytest.raises(check.SetupError, match="lokale CLI-Bereinigung"):
        check.test_login("fake-cli", TOKEN)


@pytest.mark.parametrize("outcome", ["failed", "timeout"])
def test_vault_failure_does_not_print_error_contents_and_still_cleans_up(monkeypatch, capsys, outcome):
    calls = []

    def run(args, **kwargs):
        calls.append(args[1])
        if args[1] == "vault":
            if outcome == "timeout":
                raise subprocess.TimeoutExpired(args, 30, output=TOKEN)
            return SimpleNamespace(returncode=1, stdout=TOKEN, stderr=TOKEN)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(check.subprocess, "run", run)
    with pytest.raises(check.SetupError):
        check.test_login("fake-cli", TOKEN)
    assert calls == ["login", "vault", "logout"]
    assert TOKEN not in repr(capsys.readouterr())


def test_main_returns_warning_code_after_forced_local_cleanup(monkeypatch, capsys):
    monkeypatch.setattr(check.sys, "platform", "win32")
    monkeypatch.setattr(check, "find_cli", lambda: "fake-cli")
    monkeypatch.setattr(check, "read_token", lambda: TOKEN)
    monkeypatch.setattr(check, "test_login", lambda cli, token: False)
    assert check.main([]) == 2
    assert TOKEN not in repr(capsys.readouterr())


def test_absent_token_never_starts_cli(monkeypatch, capsys):
    monkeypatch.setattr(check.sys, "platform", "win32")
    monkeypatch.setattr(check, "find_cli", lambda: "fake-cli")
    def missing():
        raise check.SetupError("Token-Datei fehlt: .env/ri_token.txt")

    monkeypatch.setattr(check, "read_token", missing)
    monkeypatch.setattr(check.subprocess, "run", lambda *args, **kwargs: pytest.fail("No token, no login"))
    assert check.main([]) == 1
    assert "Token-Datei fehlt" in capsys.readouterr().err
