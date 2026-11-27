"""Gespeicherten RI-PAT in einer frischen Proton-Testsitzung anmelden und abmelden."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.ri_proton import RiAccessError as SetupError, find_cli, read_token


def logout_problem(result) -> str:
    """Classify captured CLI errors using fixed labels, never forward native text."""
    text = (getattr(result, "stderr", "") + " " + getattr(result, "stdout", "")).lower()
    if any(word in text for word in ("keyring", "credential manager", "encryption key", "decrypt")):
        return "lokaler Sitzungs-/Schlüsselspeicher"
    if re.search(r"\b(401|403)\b", text):
        return "Server lehnt die Abmeldung ab"
    if any(word in text for word in ("timed out", "timeout", "connect", "network")):
        return "Netzwerk oder Zeitüberschreitung"
    if any(word in text for word in ("deleting", "remove", "access is denied", "permission denied")):
        return "lokale Bereinigung"
    return "CLI-Fehler ohne ausgegebene Details"


def cleanup_session(cli: str, env: dict[str, str]) -> bool:
    """Attempt remote logout, then explicitly distinguish forced local cleanup."""
    try:
        result = subprocess.run(
            [cli, "logout"], env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
        )
        if result.returncode == 0:
            print("Temporäre Testsitzung abgemeldet.")
            return True
        reason = logout_problem(result)
    except subprocess.TimeoutExpired:
        reason = "Zeitüberschreitung"
    except OSError:
        reason = "CLI konnte nicht gestartet werden"
    print(f"Abmeldung nicht bestätigt ({reason}). Lokale Bereinigung versuchen ...", flush=True)
    try:
        forced = subprocess.run(
            [cli, "logout", "--force"], env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", timeout=10, check=False,
        )
        if forced.returncode:
            raise SetupError("Auch die lokale CLI-Bereinigung konnte nicht bestätigt werden.")
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError("Auch die lokale CLI-Bereinigung konnte nicht bestätigt werden.") from None
    print(
        "Lokale CLI-Bereinigung erfolgreich. Die entfernte Testsitzung kann bis zum Ablauf bestehen bleiben."
    )
    return False


def test_login(cli: str, token: str) -> bool:
    """Show accessible vaults in a fresh session, then attempt logout and cleanup."""
    with tempfile.TemporaryDirectory(prefix="ratsi_ri_proton_login_") as directory:
        env = {
            name: value for name, value in os.environ.items()
            if not name.startswith(("PROTON_PASS_", "PASS_"))
        }
        env.update({
            "PROTON_PASS_SESSION_DIR": directory,
            "PROTON_PASS_KEY_PROVIDER": "fs",
            "PASS_LOG_LEVEL": "off",
        })
        env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] = token
        failure = None
        cleanup_failure = None
        logged_out = False
        phase = "Anmeldung"
        try:
            result = subprocess.run(
                [cli, "login"], env=env, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", timeout=45, check=False,
            )
            env.pop("PROTON_PASS_PERSONAL_ACCESS_TOKEN", None)
            if result.returncode:
                failure = "Anmeldung fehlgeschlagen. Tokenablauf, Freischaltung und Netzwerk prüfen."
            else:
                print("Proton-Anmeldung erfolgreich.", flush=True)
                phase = "Tresorauflistung"
                vaults = subprocess.run(
                    [cli, "vault", "list", "--output", "human"], env=env,
                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    timeout=30, check=False,
                )
                if vaults.returncode:
                    failure = "Tresore konnten nicht aufgelistet werden. " + logout_problem(vaults) + "."
                else:
                    # Print only the explicitly requested vault metadata, never stderr.
                    output = vaults.stdout.replace(token, "[TOKEN AUSGEBLENDET]")
                    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
                    output = "".join(char for char in output if char.isprintable() or char in "\n\t")
                    print("Für diesen Token sichtbare Tresore:")
                    print(output.strip() or "Keine Tresore angezeigt.", flush=True)
        except subprocess.TimeoutExpired:
            failure = f"Zeitüberschreitung bei der {phase}."
        except OSError:
            failure = "Proton Pass CLI konnte nicht gestartet werden."
        finally:
            env.pop("PROTON_PASS_PERSONAL_ACCESS_TOKEN", None)
            try:
                logged_out = cleanup_session(cli, env)
            except SetupError as error:
                cleanup_failure = str(error)
        if failure or cleanup_failure:
            raise SetupError(" ".join(part for part in (failure, cleanup_failure) if part))
        return logged_out


def main(argv: list[str] | None = None) -> int:
    """Run a login-only test using the local PAT file, without a keyring password."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        if sys.platform not in {"win32", "linux"}:
            raise SetupError("Dieses Skript unterstützt Windows und Linux/WSL.")
        if sys.platform == "linux" and os.geteuid() == 0:
            raise SetupError("Als normaler Benutzer starten, nicht mit sudo.")
        cli = find_cli()
        if cli is None:
            raise SetupError("Proton Pass CLI wurde nicht im PATH gefunden.")
        token = read_token()
        print("Token aus .env/ri_token.txt in einer temporären Sitzung prüfen ...", flush=True)
        try:
            logged_out = test_login(cli, token)
        finally:
            token = None
        print(
            "Erfolgreich: Proton-Anmeldung und Tresorauflistung bestätigt.\n"
            "Keine Passworteinträge angefordert; einzelnen RI-Eintrag mit check_ri_access.py prüfen."
        )
        return 0 if logged_out else 2
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
