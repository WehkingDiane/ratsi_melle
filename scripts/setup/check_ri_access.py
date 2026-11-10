"""Einzigen freigegebenen Proton-Login und RI-Anmeldung ohne Dokumentdownload prüfen."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.ri_proton import (
    ProtonRiSession, RiAccessError, read_token,
)


def main(argv: list[str] | None = None) -> int:
    """Check the sole shared RI login without persistent binding or credential output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        if sys.platform == "linux" and os.geteuid() == 0:
            raise RiAccessError("Als normaler Benutzer starten, nicht mit sudo.")
        print("Geschützten Proton-Zugang öffnen ...", flush=True)
        token = read_token()
        proton = ProtonRiSession(token)
        token = None
        with proton:
            credentials = proton.credentials()
            print("Zugang aus dem einzigen freigegebenen RI-Login intern gelesen.", flush=True)
            from src.fetching.ri_login import verify_ri_login
            try:
                verify_ri_login(credentials)
            finally:
                credentials = None
            print("RI-Anmeldung und RI-Abmeldung bestätigt. Keine Sitzungsunterlagen heruntergeladen.")
        if proton.cleanup_warning:
            print("Hinweis: Proton-Abmeldung nicht vollständig bestätigt; entfernte Testsitzung kann bis zum Ablauf bestehen bleiben.")
            return 2
        return 0
    except RiAccessError as error:
        print(f"Abbruch: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nRI-Zugriffstest abgebrochen.", file=sys.stderr)
        return 1
    except Exception:
        print("Abbruch: RI-Zugriffstest fehlgeschlagen; keine vertraulichen Details ausgegeben.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
