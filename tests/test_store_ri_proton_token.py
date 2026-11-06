"""Synthetic tests: never touch the real credential store or Proton account."""

import io
import subprocess
from types import SimpleNamespace

import pytest

from scripts.setup import store_ri_proton_token as store
from tests.test_setup_ri_secret_storage import MemoryBackend

TOKEN = "pst_synthetic-test::synthetic-key"


def test_store_replaces_only_named_ri_token():
    backend = MemoryBackend()
    backend.values[store.SERVICE, store.USERNAME] = "old-token"
    backend.values["unrelated", "user"] = "other-secret"
    store.store_token(backend, TOKEN)
    assert backend.values == {
        (store.SERVICE, store.USERNAME): TOKEN,
        ("unrelated", "user"): "other-secret",
    }


@pytest.mark.parametrize("token", ["", "password", "pst_::key", "pst_id::", "pst_id::key\n", "pst_id::key::extra"])
def test_invalid_input_never_changes_store(token):
    backend = MemoryBackend()
    backend.values[store.SERVICE, store.USERNAME] = "old-token"
    with pytest.raises(store.SetupError):
        store.store_token(backend, token)
    assert backend.values == {(store.SERVICE, store.USERNAME): "old-token"}


def test_mismatched_read_is_not_success():
    with pytest.raises(store.SetupError):
        store.store_token(MemoryBackend(broken_read=True), TOKEN)


def test_parent_passes_token_only_via_pipe_not_arguments_or_environment(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(store.sys, "platform", "win32")
    monkeypatch.setattr(store, "read_password", lambda prompt: TOKEN)

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(store.subprocess, "run", run)
    assert store.main([]) == 0
    args, kwargs = calls[0]
    assert TOKEN not in repr(args)
    assert kwargs["input"] == TOKEN
    assert kwargs["timeout"] == 20
    assert "env" not in kwargs
    assert TOKEN not in repr(capsys.readouterr())


@pytest.mark.parametrize("outcome", ["error", "timeout"])
def test_native_errors_and_secret_outputs_are_not_printed(monkeypatch, capsys, outcome):
    monkeypatch.setattr(store.sys, "platform", "win32")
    monkeypatch.setattr(store, "read_password", lambda prompt: TOKEN)

    def run(args, **kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 20, output=TOKEN, stderr=TOKEN)
        return SimpleNamespace(returncode=17, stdout=TOKEN, stderr=TOKEN)

    monkeypatch.setattr(store.subprocess, "run", run)
    assert store.main([]) == 1
    output = capsys.readouterr()
    assert TOKEN not in output.out + output.err
    assert "Token gespeichert und intern geprüft" not in output.out


def test_worker_does_not_output_token_or_exception(monkeypatch, capsys):
    monkeypatch.setattr(store.sys, "stdin", io.StringIO(TOKEN))
    monkeypatch.setattr(store.sys, "platform", "win32")

    def fail(backend, token):
        raise RuntimeError(token)

    monkeypatch.setattr(store, "select_backend", lambda platform: object())
    monkeypatch.setattr(store, "store_token", fail)
    assert store.worker() == 14
    output = capsys.readouterr()
    assert output.out == output.err == ""
