"""RI check orchestration with file token and fake services; no real accounts."""

import pytest

from scripts.setup import check_ri_access as cli
from src.config.ri_proton import RiAccessError, RiCredentials
from src.fetching import ri_login

pytestmark = pytest.mark.integration


class FakeProton:
    cleanup_warning = False

    def __init__(self, token):
        assert token == "pst_synthetic::private-token"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def credentials(self):
        return RiCredentials("private-user", "private-password")


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(cli, "read_token", lambda: "pst_synthetic::private-token")
    monkeypatch.setattr(cli, "ProtonRiSession", FakeProton)
    monkeypatch.setattr(cli.sys, "platform", "win32")


def test_missing_token_never_opens_proton_session(setup, monkeypatch, capsys):
    def missing():
        raise RiAccessError("Token-Datei fehlt: .env/ri_token.txt")

    monkeypatch.setattr(cli, "read_token", missing)
    monkeypatch.setattr(cli, "ProtonRiSession", lambda token: pytest.fail("No session without token"))
    assert cli.main([]) == 1
    assert "Token-Datei fehlt" in capsys.readouterr().err


def test_access_without_binding_supplies_credentials_only_to_ri_verifier(setup, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ri_login, "verify_ri_login", lambda credentials: calls.append(credentials))
    assert cli.main([]) == 0
    assert calls[0].username == "private-user"
    assert calls[0].password == "private-password"
    assert "private" not in repr(capsys.readouterr())


def test_native_failure_hides_sensitive_error_text(setup, monkeypatch, capsys):
    def fail(credentials):
        raise RuntimeError("private-user private-password private-cookie")

    monkeypatch.setattr(ri_login, "verify_ri_login", fail)
    assert cli.main([]) == 1
    assert "private" not in repr(capsys.readouterr())


def test_ambiguous_entry_does_not_attempt_ri_login(setup, monkeypatch):
    def ambiguous(self):
        raise RiAccessError("Erforderlich ist genau ein freigegebener Tresor mit genau einem aktiven Login-Eintrag.")

    monkeypatch.setattr(FakeProton, "credentials", ambiguous)
    monkeypatch.setattr(ri_login, "verify_ri_login", lambda credentials: pytest.fail("No RI login"))
    assert cli.main([]) == 1


def test_remote_logout_warning_is_preserved(setup, monkeypatch):
    monkeypatch.setattr(FakeProton, "cleanup_warning", True)
    monkeypatch.setattr(ri_login, "verify_ri_login", lambda credentials: None)
    assert cli.main([]) == 2
