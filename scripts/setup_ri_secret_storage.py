"""Geführte Prüfung des lokalen RI-Schlüsselspeichers ohne echte Zugangsdaten."""

from __future__ import annotations

import argparse
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


def run_command(args: list[str], *, password: str | None = None, timeout: int = 20):
    """Run a bounded subprocess without forwarding its output or exception details."""
    try:
        return subprocess.run(
            args, input=password, text=True, capture_output=True,
            timeout=timeout, check=False,
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
    password = read_password("Passwort des lokalen Schlüsselspeichers (unsichtbar): ")
    try:
        result = run_command([daemon, "--unlock", "--components=secrets"], password=password)
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
                        raise SetupError("Der Login-Schlüsselspeicher ist noch gesperrt.")
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
    try:
        backend.set_password(service, username, value)
        if backend.get_password(service, username) != value:
            raise SetupError("Der Speichertest konnte den Testwert nicht korrekt lesen.")
    finally:
        # Delete only our unique test item, even if writing failed halfway through.
        try:
            backend.delete_password(service, username)
        except Exception:
            raise SetupError(
                "Speichertest fehlgeschlagen oder Testwert nicht entfernbar. "
                "Es kann ein harmloser Eintrag mit Präfix ratsi_melle_storage_test_ "
                "zurückbleiben; keine echten Geheimnisse wurden gespeichert."
            ) from None
    if backend.get_password(service, username) is not None:
        raise SetupError("Der Testwert konnte nicht vollständig entfernt werden.")


def worker() -> int:
    """Perform the OS probe in a process that the parent can stop on timeout."""
    try:
        probe_backend(select_backend(sys.platform))
    except Exception:
        # Native errors can contain credential details: never forward them.
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Guide the storage test and return a safe, bounded result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.probe_worker:
        return worker()
    try:
        if sys.platform not in {"win32", "linux"}:
            raise SetupError("Dieses Skript unterstützt Windows und Linux/WSL.")
        if not sys.stdin.isatty():
            raise SetupError("Bitte direkt in einem interaktiven Terminal starten.")
        try:
            import keyring  # noqa: F401 -- check the existing project dependency
        except ImportError:
            raise SetupError(
                'Python-Paket fehlt. In dieser Umgebung ausführen: '
                'python -m pip install "keyring>=25.7.0"'
            ) from None
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
            raise SetupError(
                "Der Speichertest ist fehlgeschlagen. Unter WSL wurde der Login-Speicher "
                "möglicherweise nicht entsperrt (Passwort prüfen) oder ist nicht verfügbar. "
                "Es wird kein Klartextspeicher verwendet. Ein harmloser Testeintrag "
                "mit Präfix ratsi_melle_storage_test_ kann zurückbleiben."
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
