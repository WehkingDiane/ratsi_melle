"""Gespeicherten RI-PAT in einer frischen Proton-Testsitzung anmelden und abmelden."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.setup_ri_secret_storage import SetupError, select_backend
from scripts.store_ri_proton_token import SERVICE, USERNAME, valid_token


def test_login(cli: str, token: str) -> None:
    """Use only a fresh temporary session, suppress output and attempt logout always."""
    with tempfile.TemporaryDirectory(prefix="ratsi_ri_proton_login_") as directory:
        env = {
            name: value for name, value in os.environ.items()
            if not name.startswith(("PROTON_PASS_", "PASS_"))
        }
        env.update({
            "PROTON_PASS_SESSION_DIR": directory,
            "PROTON_PASS_KEY_PROVIDER": "keyring",
            "PASS_LOG_LEVEL": "off",
        })
        if sys.platform == "linux":
            env["PROTON_PASS_LINUX_KEYRING"] = "dbus"
        env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] = token
        failure = None
        try:
            result = subprocess.run(
                [cli, "login"], env=env, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=45, check=False,
            )
            if result.returncode:
                failure = "Anmeldung fehlgeschlagen. Tokenablauf, Freischaltung und Netzwerk prüfen."
        except subprocess.TimeoutExpired:
            failure = "Zeitüberschreitung bei der Proton-Anmeldung."
        except OSError:
            failure = "Proton Pass CLI konnte nicht gestartet werden."
        finally:
            env.pop("PROTON_PASS_PERSONAL_ACCESS_TOKEN", None)
            try:
                logout = subprocess.run(
                    [cli, "logout"], env=env, stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                if logout.returncode == 0:
                    print("Temporäre Testsitzung abgemeldet.")
                elif failure is None:
                    failure = "Anmeldung erfolgreich, aber Abmeldung nicht bestätigt."
            except (OSError, subprocess.TimeoutExpired):
                if failure is None:
                    failure = "Anmeldung erfolgreich, aber Abmeldung nicht bestätigt."
        if failure:
            raise SetupError(failure)


def main(argv: list[str] | None = None) -> int:
    """Run a login-only test using the PAT from the explicit OS credential store."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        if sys.platform not in {"win32", "linux"}:
            raise SetupError("Dieses Skript unterstützt Windows und Linux/WSL.")
        if sys.platform == "linux" and os.geteuid() == 0:
            raise SetupError("Als normaler Benutzer starten, nicht mit sudo.")
        cli = shutil.which("pass-cli.exe" if sys.platform == "win32" else "pass-cli")
        if cli is None:
            raise SetupError("Proton Pass CLI wurde nicht im PATH gefunden.")
        token = select_backend(sys.platform).get_password(SERVICE, USERNAME)
        if not token or not valid_token(token):
            raise SetupError("Kein vollständiger RI-Token hinterlegt. Zuerst store_ri_proton_token.py starten.")
        print("Gespeicherten Token in einer eigenen temporären Sitzung prüfen ...", flush=True)
        try:
            test_login(cli, token)
        finally:
            token = None
        print(
            "Erfolgreich: Proton-Anmeldung mit dem gespeicherten Token bestätigt.\n"
            "Keine Passworteinträge angefordert; RI-Einzelberechtigung noch nicht geprüft."
        )
        return 0
    except SetupError as error:
        print(f"Abbruch: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nAnmeldetest abgebrochen.", file=sys.stderr)
        return 1
    except Exception:
        print("Abbruch: Anmeldetest fehlgeschlagen; keine vertraulichen Fehlerdetails ausgegeben.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
