"""Eigenen Proton-Eintrag binden und die RI-Anmeldung ohne Dokumentdownload prüfen."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.ri_proton import (
    ProtonRiSession, RiAccessError, load_reference, read_os_token, reference_path, save_reference,
)


def main(argv: list[str] | None = None) -> int:
    """Configure non-secret references or test RI login without displaying content."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure", action="store_true", help="Einzigen freigegebenen RI-Eintrag lokal binden; noch kein RI-Login.")
    args = parser.parse_args(argv)
    try:
        if sys.platform == "linux" and os.geteuid() == 0:
            raise RiAccessError("Als normaler Benutzer starten, nicht mit sudo.")
        path = reference_path()
        reference = None if args.configure else load_reference(path)
        print("Geschützten Proton-Zugang öffnen ...", flush=True)
        token = read_os_token()
        proton = ProtonRiSession(token)
        token = None
        with proton:
            if args.configure:
                save_reference(path, proton.discover_reference())
                print("RI-Eintragsbindung gespeichert. Keine Benutzernamen oder Passwörter gespeichert.")
            else:
                credentials = proton.credentials(reference)
                print("Zugang aus dem fest gebundenen RI-Eintrag intern gelesen.", flush=True)
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
