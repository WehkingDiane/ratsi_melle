"""Geführte Prüfung des lokalen RI-Schlüsselspeichers ohne echte Zugangsdaten."""

from __future__ import annotations

import argparse
import errno
import getpass
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import warnings


class SetupError(Exception):
    """Einrichtungsfehler mit einer inhaltsfreien Meldung für die Bedienung."""

    def __init__(self, message: str, *, code: int = 1):
        super().__init__(message)
        self.code = code


PROBE_ERRORS = {
    10: "Python-Unterstützung für den Betriebssystemspeicher fehlt (keyring/SecretStorage).",
    11: "Der Login-Schlüsselspeicher ist gesperrt. Das Entsperren war nicht erfolgreich.",
    12: "Der Dienst findet den Login-Schlüsselspeicher nicht; ein Alias allein genügt nicht.",
    13: "Der Secret-Service-Dienst oder seine D-Bus-Sitzung ist nicht erreichbar.",
    14: "Schreiben oder Lesen im Schlüsselspeicher ist fehlgeschlagen.",
    15: "Der eigene Testwert konnte nicht entfernt werden.",
    16: "Der gelesene Testwert stimmt nicht mit dem gespeicherten Wert überein.",
    17: "Das Betriebssystem verweigert den Zugriff auf den Schlüsselspeicher.",
    18: "Der ausgewählte Speicher unterstützt die benötigte Operation nicht.",
}


def run_command(
    args: list[str], *, password: str | None = None, timeout: int = 20,
    env: dict[str, str] | None = None,
):
    """Run a bounded subprocess without forwarding its output or exception details."""
    try:
        return subprocess.run(
            args, input=password, text=True, capture_output=True,
            timeout=timeout, check=False, env=env,
        )
    except subprocess.TimeoutExpired:
        raise SetupError(
            "Der Schlüsselspeicher antwortet nicht rechtzeitig. "
            "Der Versuch wurde beendet; es wurden keine echten Zugangsdaten verwendet."
        ) from None
    except OSError:
        raise SetupError("Das benötigte Programm konnte nicht gestartet werden.") from None


def read_password(prompt: str) -> str:
    """Read only from an interactive terminal, never fall back to visible input."""
    if not sys.stdin.isatty():
        raise SetupError("Bitte direkt in einem interaktiven Terminal starten.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            value = getpass.getpass(prompt)
        except (getpass.GetPassWarning, EOFError):
            raise SetupError("Verdeckte Passworteingabe ist hier nicht verfügbar.") from None
    if not value:
        raise SetupError("Ein leeres Passwort ist nicht erlaubt.")
    return value


def prepare_linux() -> None:
    """Start GNOME Secret Service and unlock/create its persistent login keyring."""
    if os.geteuid() == 0:
        raise SetupError("Als normaler Benutzer starten, nicht mit sudo.")
    daemon = shutil.which("gnome-keyring-daemon")
    if daemon is None:
        raise SetupError(
            "GNOME Keyring fehlt. Unter Ubuntu/WSL einmal ausführen: "
            "sudo apt install gnome-keyring"
        )
    print("1/3: Lokalen Schlüsselspeicher starten ...", flush=True)
    result = run_command([daemon, "--start", "--components=secrets"])
    if result.returncode:
        raise SetupError("GNOME Keyring konnte nicht gestartet werden. D-Bus-Sitzung prüfen.")
    print(
        "2/3: Lokalen Schlüsselspeicher entsperren.\n"
        "Falls bereits vorhanden: sein bisheriges Passwort verwenden.\n"
        "Falls neu: ein starkes Passwort wählen und für spätere Starts aufbewahren.\n"
        "Hier weder Proton-Passwort noch RI-Passwort oder Token eingeben.",
        flush=True,
    )
    # GNOME can announce a different control directory than the inherited one.
    # Parse one allowlisted value; never evaluate the daemon output as shell code.
    daemon_env = os.environ.copy()
    for line in getattr(result, "stdout", "").splitlines():
        name, separator, value = line.partition("=")
        if name == "GNOME_KEYRING_CONTROL" and separator and Path(value).is_absolute():
            daemon_env[name] = value
    password = read_password("Passwort des lokalen Schlüsselspeichers (unsichtbar): ")
    try:
        result = run_command([daemon, "--unlock", "--components=secrets"], password=password, env=daemon_env)
    finally:
        password = None
    if result.returncode:
        raise SetupError("Der lokale Schlüsselspeicher konnte nicht entsperrt werden.")


def select_backend(platform: str):
    """Select a specific OS backend; never use automatic or plaintext fallback."""
    if platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring

        return WinVaultKeyring()
    if platform == "linux":
        from keyring.backends.SecretService import Keyring
        import secretstorage

        class LoginKeyring(Keyring):
            def get_preferred_collection(self):
                # Do not invoke a GUI prompt or create an unprotected default collection.
                bus = secretstorage.dbus_init()
                try:
                    collection = secretstorage.Collection(
                        bus, "/org/freedesktop/secrets/collection/login",
                    )
                    if collection.is_locked():
                        raise SetupError("Der Login-Schlüsselspeicher ist noch gesperrt.", code=11)
                    return collection
                except Exception:
                    bus.close()
                    raise

        return LoginKeyring()
    raise SetupError("Dieses Skript unterstützt Windows und Linux/WSL.")


def probe_backend(backend) -> None:
    """Write, read and remove only a uniquely named random test credential."""
    service = "ratsi_melle_storage_test_" + secrets.token_hex(16)
    username = "storage_test"
    value = secrets.token_urlsafe(32)
    failure = None
    try:
        backend.set_password(service, username, value)
        if backend.get_password(service, username) != value:
            raise SetupError("Der Testwert stimmt nicht überein.", code=16)
    except Exception as error:
        failure = error
    try:
        backend.delete_password(service, username)
    except Exception:
        if failure is None:
            raise SetupError("Der Testwert konnte nicht entfernt werden.", code=15) from None
    if failure is not None:
        raise failure
    if backend.get_password(service, username) is not None:
        raise SetupError("Der Testwert konnte nicht vollständig entfernt werden.", code=15)


def classify_error(error: Exception) -> int:
    """Return only allowlisted error codes; never serialize native error text."""
    if isinstance(error, SetupError):
        return error.code if error.code in PROBE_ERRORS else 14
    if isinstance(error, ImportError):
        return 10
    if isinstance(error, PermissionError):
        return 17
    # Match the actual library types, never untrusted exception text.
    if sys.platform == "linux":
        try:
            from secretstorage.exceptions import (
                ItemNotFoundException, LockedException, SecretServiceNotAvailableException,
            )
            if isinstance(error, ItemNotFoundException):
                return 12
            if isinstance(error, LockedException):
                return 11
            if isinstance(error, SecretServiceNotAvailableException):
                return 13
        except ImportError:
            return 10
    if isinstance(error, NotImplementedError):
        return 18
    if isinstance(error, OSError) and error.errno in {errno.ENOENT, errno.ECONNREFUSED}:
        return 13
    return 14


def worker(*, inspect_only: bool = False) -> int:
    """Perform the OS probe in a process that the parent can stop on timeout."""
    try:
        backend = select_backend(sys.platform)
        if sys.platform == "linux":
            # Preflight before attempting a write/deletion, without GUI prompts.
            collection = backend.get_preferred_collection()
            collection.connection.close()
        if not inspect_only:
            probe_backend(backend)
    except Exception as error:
        return classify_error(error)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Guide the storage test and return a safe, bounded result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--inspect-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--check", action="store_true",
        help="Unter Linux nur Erreichbarkeit und Sperrstatus prüfen, ohne Passwort oder Testeintrag.",
    )
    args = parser.parse_args(argv)
    if args.inspect_worker:
        return worker(inspect_only=True)
    if args.probe_worker:
        return worker()
    try:
        if sys.platform not in {"win32", "linux"}:
            raise SetupError("Dieses Skript unterstützt Windows und Linux/WSL.")
        if not args.check and not sys.stdin.isatty():
            raise SetupError("Bitte direkt in einem interaktiven Terminal starten.")
        try:
            import keyring  # noqa: F401 -- check the existing project dependency
        except ImportError:
            raise SetupError(
                'Python-Paket fehlt. In dieser Umgebung ausführen: '
                'python -m pip install "keyring>=25.7.0"'
            ) from None
        if args.check:
            if sys.platform != "linux":
                raise SetupError("--check ist für die Diagnose unter Linux/WSL vorgesehen.")
            result = run_command(
                [sys.executable, str(Path(__file__).resolve()), "--inspect-worker"],
            )
            if result.returncode:
                raise SetupError(PROBE_ERRORS.get(result.returncode, "Speicherstatus nicht bestimmbar."))
            print("Login-Schlüsselspeicher erreichbar und entsperrt. Kein Speichertest ausgeführt.")
            return 0
        print("RI-Speicherhilfe: keine Anmeldung bei Proton, keine echten Zugangsdaten.")
        if sys.platform == "linux":
            prepare_linux()
        else:
            print("1/3: Windows-Anmeldedatenspeicher verwenden.")
            print("2/3: Die Entsperrung erfolgt über dein Windows-Benutzerkonto.")
        print("3/3: Schreiben, Lesen und Löschen eines Zufallswerts prüfen ...", flush=True)
        result = run_command(
            [sys.executable, str(Path(__file__).resolve()), "--probe-worker"],
            timeout=20,
        )
        if result.returncode:
            detail = PROBE_ERRORS.get(result.returncode, "Speichertest fehlgeschlagen.")
            raise SetupError(
                detail + " Es wird kein Klartextspeicher verwendet. "
                "Ein harmloser Testeintrag mit Präfix ratsi_melle_storage_test_ "
                "kann zurückbleiben."
            )
        print(
            "Erfolgreich: Testwert gespeichert, gelesen und wieder entfernt.\n"
            "Der Betriebssystemspeicher ist in dieser Sitzung nutzbar.\n"
            "Proton-Token und RI-Anbindung sind noch nicht eingerichtet.\n"
            "Die Prüfung nach einem Neustart steht noch aus."
        )
        return 0
    except SetupError as error:
        print(f"Abbruch: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nAbgebrochen. Keine echten Zugangsdaten verarbeitet.", file=sys.stderr)
        return 1
    except Exception:
        print("Abbruch: Speicherprüfung fehlgeschlagen; keine Fehlerdetails ausgegeben.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
