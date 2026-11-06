"""Login checks use fake tokens and CLI calls, never the actual credential store."""

from types import SimpleNamespace
import subprocess

import pytest

from scripts import check_ri_proton_login as check

TOKEN = "pst_synthetic::synthetic-key"


def test_login_isolated_and_token_only_passed_to_login(monkeypatch, capsys):
    calls = []
    monkeypatch.setenv("PROTON_PASS_SESSION_DIR", "/personal/session")
    monkeypatch.setenv("PROTON_PASS_PASSWORD", "account-secret")
    monkeypatch.setenv("PROTON_PASS_KEY_PROVIDER", "fs")
    monkeypatch.setattr(check.sys, "platform", "win32")

    def run(args, **kwargs):
        calls.append((args, dict(kwargs["env"])))
        return SimpleNamespace(returncode=0, stdout=TOKEN, stderr=TOKEN)

    monkeypatch.setattr(check.subprocess, "run", run)
    check.test_login("pass-cli.exe", TOKEN)
    assert [args[1] for args, env in calls] == ["login", "logout"]
    login_env, logout_env = [env for args, env in calls]
    assert login_env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] == TOKEN
    assert "PROTON_PASS_PERSONAL_ACCESS_TOKEN" not in logout_env
    assert "PROTON_PASS_PASSWORD" not in login_env
    assert login_env["PROTON_PASS_KEY_PROVIDER"] == "keyring"
    assert login_env["PROTON_PASS_SESSION_DIR"] != "/personal/session"
    assert login_env["PROTON_PASS_SESSION_DIR"] == logout_env["PROTON_PASS_SESSION_DIR"]
    assert TOKEN not in repr([args for args, env in calls])
    assert TOKEN not in repr(capsys.readouterr())
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


def test_logout_failure_never_reported_as_overall_success(monkeypatch):
    monkeypatch.setattr(check.subprocess, "run", lambda args, **kwargs: SimpleNamespace(
        returncode=0 if args[1] == "login" else 1,
    ))
    with pytest.raises(check.SetupError, match="Abmeldung nicht bestätigt"):
        check.test_login("fake-cli", TOKEN)


def test_absent_token_never_starts_cli(monkeypatch, capsys):
    monkeypatch.setattr(check.sys, "platform", "win32")
    monkeypatch.setattr(check.shutil, "which", lambda name: "fake-cli")
    monkeypatch.setattr(check, "select_backend", lambda platform: SimpleNamespace(
        get_password=lambda *args: None,
    ))
    monkeypatch.setattr(check.subprocess, "run", lambda *args, **kwargs: pytest.fail("No token, no login"))
    assert check.main([]) == 1
    assert "Kein vollständiger RI-Token" in capsys.readouterr().err
