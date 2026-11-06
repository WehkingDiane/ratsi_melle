"""Storage setup uses synthetic credentials and never opens the real OS keyring."""

from types import SimpleNamespace
import subprocess
import sys

import pytest

from scripts import setup_ri_secret_storage as setup


class MemoryBackend:
    def __init__(self, *, broken_read=False):
        self.values = {}
        self.broken_read = broken_read

    def set_password(self, service, user, value):
        self.values[service, user] = value

    def get_password(self, service, user):
        if self.broken_read and (service, user) in self.values:
            return "wrong"
        return self.values.get((service, user))

    def delete_password(self, service, user):
        del self.values[service, user]


def test_probe_removes_own_item_and_preserves_existing_credentials():
    backend = MemoryBackend()
    backend.values["existing-service", "existing-user"] = "existing-secret"
    setup.probe_backend(backend)
    assert backend.values == {("existing-service", "existing-user"): "existing-secret"}


def test_probe_cleans_up_after_failed_read():
    backend = MemoryBackend(broken_read=True)
    with pytest.raises(setup.SetupError):
        setup.probe_backend(backend)
    assert backend.values == {}


def test_partial_write_failure_is_cleaned_up_without_exposing_error(monkeypatch, capsys):
    backend = MemoryBackend()

    def partial_write(service, user, value):
        backend.values[service, user] = value
        raise RuntimeError("private-native-error")

    backend.set_password = partial_write
    monkeypatch.setattr(setup, "select_backend", lambda platform: backend)
    monkeypatch.setattr(setup.sys, "platform", "win32")
    assert setup.worker() == 14
    assert backend.values == {}
    output = capsys.readouterr()
    assert "private-native-error" not in output.out + output.err


def test_timeout_does_not_include_process_input_or_output(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 20, output="private-output")

    monkeypatch.setattr(setup.subprocess, "run", timeout)
    with pytest.raises(setup.SetupError) as error:
        setup.run_command(["daemon"], password="private-input")
    assert "private" not in str(error.value)


def test_linux_password_sent_only_over_stdin(monkeypatch):
    calls = []
    monkeypatch.setattr(setup.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/usr/bin/daemon")
    monkeypatch.setattr(setup, "read_password", lambda prompt: "private-password")

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(setup, "run_command", run)
    setup.prepare_linux()
    assert "--start" in calls[0][0]
    assert "--unlock" in calls[1][0]
    assert calls[1][1]["password"] == "private-password"
    assert all("private-password" not in arg for args, kwargs in calls for arg in args)


def test_root_rejected_before_start_or_password_prompt(monkeypatch):
    monkeypatch.setattr(setup.os, "geteuid", lambda: 0, raising=False)
    with pytest.raises(setup.SetupError, match="nicht mit sudo"):
        setup.prepare_linux()


def test_no_echo_fallback_for_password(monkeypatch):
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))

    def getpass(prompt):
        import warnings
        warnings.warn("no terminal", setup.getpass.GetPassWarning)
        pytest.fail("Must not proceed to visible input")

    monkeypatch.setattr(setup.getpass, "getpass", getpass)
    with pytest.raises(setup.SetupError, match="Verdeckte"):
        setup.read_password("password:")


def test_empty_password_rejected(monkeypatch):
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt: "")
    with pytest.raises(setup.SetupError, match="leeres Passwort"):
        setup.read_password("password:")


def test_main_stops_on_failed_probe_and_does_not_print_native_errors(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys, "platform", "linux")
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup, "prepare_linux", lambda: None)
    monkeypatch.setattr(
        setup, "run_command",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="private-native-error"),
    )
    assert setup.main([]) == 1
    output = capsys.readouterr()
    assert "private-native-error" not in output.out + output.err
    assert "Erfolgreich" not in output.out


def test_unsupported_backend_rejected():
    with pytest.raises(setup.SetupError):
        setup.select_backend("unsupported")


@pytest.mark.skipif(sys.platform != "linux", reason="Linux Secret Service backend")
def test_linux_backend_rejects_locked_store_without_gui_or_plaintext_fallback(monkeypatch):
    import sys
    import keyring.backends.SecretService

    calls = []
    connection = SimpleNamespace(close=lambda: calls.append("closed"))
    collection = SimpleNamespace(is_locked=lambda: True)
    monkeypatch.setitem(sys.modules, "secretstorage", SimpleNamespace(
        dbus_init=lambda: connection,
        Collection=lambda bus, path: collection,
    ))
    backend = setup.select_backend("linux")
    with pytest.raises(setup.SetupError, match="gesperrt"):
        backend.get_preferred_collection()
    assert calls == ["closed"]


def test_windows_main_probes_in_bounded_subprocess_without_password(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys, "platform", "win32")
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(setup, "run_command", run)
    assert setup.main([]) == 0
    assert calls[0][0][-1] == "--probe-worker"
    assert calls[0][1] == {"timeout": 20}
    assert "noch nicht eingerichtet" in capsys.readouterr().out


@pytest.mark.parametrize("code", [11, 12, 13, 17])
def test_check_prints_only_known_error_and_never_asks_for_password(monkeypatch, capsys, code):
    monkeypatch.setattr(setup.sys, "platform", "linux")
    monkeypatch.setattr(setup, "read_password", lambda prompt: pytest.fail("No password in --check"))
    monkeypatch.setattr(setup, "prepare_linux", lambda: pytest.fail("No daemon startup in --check"))
    monkeypatch.setattr(setup, "run_command", lambda *args, **kwargs: SimpleNamespace(
        returncode=code, stdout="private-secret", stderr="private-secret",
    ))
    assert setup.main(["--check"]) == 1
    output = capsys.readouterr()
    assert setup.PROBE_ERRORS[code] in output.err
    assert "private-secret" not in output.err + output.out


def test_startup_control_directory_used_for_unlock_without_evaluating_output(monkeypatch):
    calls = []
    monkeypatch.setattr(setup.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/usr/bin/daemon")
    monkeypatch.setattr(setup, "read_password", lambda prompt: "private-password")
    monkeypatch.setenv("GNOME_KEYRING_CONTROL", "/old/path")

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=(
            "GNOME_KEYRING_CONTROL=/run/user/1000/new-keyring\n"
            "UNRELATED=value\n"
            "GNOME_KEYRING_CONTROL=relative-path\n"
        ))

    monkeypatch.setattr(setup, "run_command", run)
    setup.prepare_linux()
    env = calls[1][1]["env"]
    assert env["GNOME_KEYRING_CONTROL"] == "/run/user/1000/new-keyring"
    assert "UNRELATED" not in env
    assert "private-password" not in env.values()
    assert setup.os.environ["GNOME_KEYRING_CONTROL"] == "/old/path"


def test_inspection_never_reads_or_writes_credentials(monkeypatch):
    calls = []
    collection = SimpleNamespace(connection=SimpleNamespace(close=lambda: calls.append("close")))
    backend = SimpleNamespace(get_preferred_collection=lambda: collection)
    monkeypatch.setattr(setup.sys, "platform", "linux")
    monkeypatch.setattr(setup, "select_backend", lambda platform: backend)
    monkeypatch.setattr(setup, "probe_backend", lambda backend: pytest.fail("No credential access"))
    assert setup.worker(inspect_only=True) == 0
    assert calls == ["close"]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux Secret Service backend")
def test_missing_collection_is_reported_before_any_write(monkeypatch):
    from secretstorage.exceptions import ItemNotFoundException

    def missing():
        raise ItemNotFoundException("native error with private information")

    monkeypatch.setattr(setup.sys, "platform", "linux")
    monkeypatch.setattr(setup, "select_backend", lambda platform: SimpleNamespace(
        get_preferred_collection=missing,
    ))
    monkeypatch.setattr(setup, "probe_backend", lambda backend: pytest.fail("Must not write"))
    assert setup.worker() == 12
