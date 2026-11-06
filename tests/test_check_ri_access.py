"""CLI orchestration with local reference files and fake Proton/RI services."""

import pytest

from scripts.setup import check_ri_access as cli
from src.config.ri_proton import RiAccessError, RiCredentials, RiReference, load_reference, save_reference
from src.fetching import ri_login

pytestmark = pytest.mark.integration
REF = RiReference("synthetic_share_123", "synthetic_item_123")


class FakeProton:
    cleanup_warning = False
    read_calls = 0

    def __init__(self, token):
        self.token = token

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def discover_reference(self):
        return REF

    def credentials(self, reference):
        assert reference == REF
        self.read_calls += 1
        return RiCredentials("private-user", "private-password")


@pytest.fixture
def setup(monkeypatch, tmp_path):
    path = tmp_path / "private_config" / "ri.json"
    monkeypatch.setattr(cli, "reference_path", lambda: path)
    monkeypatch.setattr(cli, "read_os_token", lambda: "pst_synthetic::private-token")
    monkeypatch.setattr(cli, "ProtonRiSession", FakeProton)
    monkeypatch.setattr(cli.sys, "platform", "win32")
    return path


def test_configure_persists_only_reference_and_does_not_read_credentials(setup, monkeypatch, capsys):
    monkeypatch.setattr(FakeProton, "credentials", lambda *args: pytest.fail("No secret read in configure"))
    monkeypatch.setattr(ri_login, "verify_ri_login", lambda *args: pytest.fail("No RI login in configure"))
    assert cli.main(["--configure"]) == 0
    assert load_reference(setup) == REF
    assert "private" not in setup.read_text() + repr(capsys.readouterr())


def test_no_reference_means_no_token_read_and_no_login(setup, monkeypatch):
    monkeypatch.setattr(cli, "read_os_token", lambda: pytest.fail("Missing reference must stop first"))
    assert cli.main([]) == 1


def test_bound_access_supplies_credentials_only_to_ri_verifier(setup, monkeypatch, capsys):
    save_reference(setup, REF)
    calls = []
    monkeypatch.setattr(ri_login, "verify_ri_login", lambda credentials: calls.append(credentials))
    assert cli.main([]) == 0
    assert calls[0].username == "private-user"
    assert calls[0].password == "private-password"
    assert "private" not in repr(capsys.readouterr())


def test_native_failure_hides_sensitive_error_text(setup, monkeypatch, capsys):
    save_reference(setup, REF)

    def fail(credentials):
        raise RuntimeError("private-user private-password private-cookie")

    monkeypatch.setattr(ri_login, "verify_ri_login", fail)
    assert cli.main([]) == 1
    assert "private" not in repr(capsys.readouterr())
