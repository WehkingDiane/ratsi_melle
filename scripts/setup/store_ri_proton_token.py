"""Proton-Pass-Token verdeckt eingeben und im lokalen OS-Schlüsselspeicher ersetzen."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.setup.setup_ri_secret_storage import (
    PROBE_ERRORS, SetupError, classify_error, read_password, select_backend,
)

SERVICE = "ratsi_melle_ri"
USERNAME = "proton_pass_pat"
MAX_TOKEN_LENGTH = 16000


def valid_token(token: str) -> bool:
    """Check the documented PAT shape locally, without verifying access or expiry."""
    identifier, separator, key = token.partition("::")
    return (
        len(token) <= MAX_TOKEN_LENGTH
        and identifier.startswith("pst_") and len(identifier) > 4
        and separator == "::" and bool(key) and "::" not in key
        and not any(character.isspace() or ord(character) < 32 for character in token)
    )


def store_token(backend, token: str) -> None:
    """Replace only the fixed RI credential and verify it without displaying it."""
    if not valid_token(token):
        raise SetupError("Kein vollständiger Proton-Pass-Token im erwarteten Format.")
    backend.set_password(SERVICE, USERNAME, token)
    if backend.get_password(SERVICE, USERNAME) != token:
        raise SetupError("Die gespeicherte Eingabe konnte nicht bestätigt werden.", code=16)


def worker() -> int:
    """Accept the token only over stdin; return fixed codes, never native messages."""
    try:
        token = sys.stdin.read(MAX_TOKEN_LENGTH + 1)
        store_token(select_backend(sys.platform), token)
    except Exception as error:
        return classify_error(error)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Prompt locally; send the secret through a pipe to a bounded store process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.store_worker:
        return worker()
    try:
        if sys.platform not in {"win32", "linux"}:
            raise SetupError("Dieses Skript unterstützt Windows und Linux/WSL.")
        if sys.platform == "linux" and os.geteuid() == 0:
            raise SetupError("Als normaler Benutzer starten, nicht mit sudo.")
        print(
            "RI-Token im lokalen Betriebssystemspeicher ablegen.\n"
            "Ein bereits dort hinterlegter RI-Token wird ersetzt.\n"
            "Es erfolgt keine Anmeldung bei Proton; Rechte und Ablauf werden nicht geprüft.",
            flush=True,
        )
        token = read_password("Vollständigen Proton-Pass-Token einfügen (unsichtbar): ")
        if not valid_token(token):
            raise SetupError("Kein vollständiger Proton-Pass-Token im erwarteten Format.")
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--store-worker"],
                input=token, text=True, capture_output=True, timeout=20, check=False,
            )
        finally:
            token = None
        if result.returncode:
            detail = PROBE_ERRORS.get(result.returncode, "Tokenablage fehlgeschlagen.")
            raise SetupError(detail + " Der neue Token ist nicht als erfolgreich gespeichert bestätigt.")
        print(
            "Token gespeichert und intern geprüft.\n"
            "Derselbe Aufruf kann später einen neuen Token hinterlegen.\n"
            "Proton-Anmeldung und Beschränkung auf den RI-Eintrag sind noch separat zu prüfen."
        )
        return 0
    except subprocess.TimeoutExpired:
        print(
            "Abbruch: Der Schlüsselspeicher antwortet nicht rechtzeitig. "
            "Die Speicherung ist nicht bestätigt; nach Entsperrung erneut starten.",
            file=sys.stderr,
        )
        return 1
    except SetupError as error:
        print(f"Abbruch: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nAbgebrochen.", file=sys.stderr)
        return 1
    except Exception:
        print("Abbruch: Tokenablage fehlgeschlagen; keine Fehlerdetails ausgegeben.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
