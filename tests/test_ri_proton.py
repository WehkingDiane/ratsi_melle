"""Single-entry, read-only Proton access with synthetic tokens and CLI responses."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config.ri_proton import (
    ProtonRiSession, RiAccessError, RiCredentials, RiReference,
)

REF = RiReference("share_test_123", "item_test_123")


def test_credentials_repr_hides_both_fields():
    assert "private" not in repr(RiCredentials("private-user", "private-password"))


@pytest.mark.parametrize("identifier", ["--help", "bad\nvalue", "a", "", None])
def test_reference_rejects_malformed_ids(identifier):
    with pytest.raises(RiAccessError):
        RiReference(identifier, REF.item_id)




@pytest.fixture
def session():
    client = ProtonRiSession("pst_synthetic::private-token", cli="fake-cli")
    client._env = {}
    return client


def responses(operation, reference=None, share_id=None):
    if operation == "vaults":
        return json.dumps({"vaults": [{"share_id": REF.share_id}]})
    if operation == "items":
        return json.dumps({"items": [{"id": REF.item_id, "share_id": REF.share_id,
                                     "item_type": "login", "state": "active"}]})
    return {"username": "test-user\n", "password": "  test-password  \n", "email": "test@example.invalid\n"}[operation]


def test_only_single_item_fields_read_and_password_spaces_preserved(session, monkeypatch):
    calls = []

    def fake(operation, **kwargs):
        calls.append(operation)
        return responses(operation, **kwargs)

    monkeypatch.setattr(session, "_call", fake)
    result = session.credentials()
    assert result.username == "test-user"
    assert result.password == "  test-password  "
    assert calls == ["vaults", "items", "username", "password"]


@pytest.mark.parametrize("operation", ["vaults", "items"])
def test_multiple_vaults_or_items_prevent_any_secret_read(session, monkeypatch, operation):
    calls = []

    def fake(op, **kwargs):
        calls.append(op)
        if op == operation:
            payload = json.loads(responses(op, **kwargs))
            payload[op] *= 2
            return json.dumps(payload)
        return responses(op, **kwargs)

    monkeypatch.setattr(session, "_call", fake)
    with pytest.raises(RiAccessError):
        session.credentials()
    assert not {"username", "password", "email"}.intersection(calls)


def test_current_single_entry_is_used_without_persistent_binding(session, monkeypatch):
    monkeypatch.setattr(session, "_call", responses)
    assert session.credentials().username == "test-user"


@pytest.mark.parametrize("operation", ["create", "update", "delete", "trash", "move", "grant", "share", "url", "item view"])
def test_unlisted_operations_never_start_a_process(session, monkeypatch, operation):
    import src.config.ri_proton as module
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: pytest.fail("Forbidden process"))
    with pytest.raises(RiAccessError):
        session._call(operation, reference=REF)


@pytest.mark.integration
def test_lifecycle_only_login_receives_token_and_native_outputs_are_hidden(monkeypatch, capsys):
    import src.config.ri_proton as module
    calls = []
    monkeypatch.setenv("PROTON_PASS_PASSWORD", "private-account-password")
    monkeypatch.setenv("PROTON_PASS_SESSION_DIR", "/personal-session")
    monkeypatch.setenv("PROTON_PASS_KEY_PROVIDER", "fs")

    def fake(args, **kwargs):
        calls.append((args, dict(kwargs["env"])))
        output = "Proton Pass CLI 2.7.0 (ba80a19)" if args[-1] == "--version" else "private-native-output"
        return SimpleNamespace(returncode=0, stdout=output, stderr="private-native-error")

    monkeypatch.setattr(module.subprocess, "run", fake)
    with ProtonRiSession("pst_synthetic::private-token", cli="fake-cli") as client:
        directory = Path(client._env["PROTON_PASS_SESSION_DIR"])
        assert directory.exists()
    assert not directory.exists()
    assert [args[1] for args, env in calls] == ["--version", "login", "logout"]
    for args, env in calls:
        assert "private-token" not in repr(args)
        assert "PROTON_PASS_PASSWORD" not in env
        assert env["PROTON_PASS_KEY_PROVIDER"] == "fs"
        assert env["PROTON_PASS_SESSION_DIR"] != "/personal-session"
        assert ("PROTON_PASS_PERSONAL_ACCESS_TOKEN" in env) == (args[1] == "login")
    assert "private" not in repr(capsys.readouterr())
