"""Read the sole shared RI login using a local token file and temporary CLI session."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_TOKEN_LENGTH = 16000


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+/=-]{7,1023}\Z")


class RiAccessError(RuntimeError):
    """Safe message for the operator; never include native errors or secret data."""


@dataclass(frozen=True)
class RiReference:
    """Non-secret reference to exactly one approved vault and item."""

    share_id: str
    item_id: str

    def __post_init__(self):
        if not all(isinstance(value, str) and _ID.fullmatch(value) for value in (self.share_id, self.item_id)):
            raise RiAccessError("Ungültige lokale RI-Eintragsreferenz.")


@dataclass(frozen=True, repr=False)
class RiCredentials:
    """Keep login values out of representations and console diagnostics."""

    username: str = field(repr=False)
    password: str = field(repr=False)

    def __repr__(self):
        return "RiCredentials(<geschützt>)"


def token_path() -> Path:
    """Locate the local token file independently of the working directory."""
    return REPO_ROOT / ".env" / "ri_token.txt"


def read_token() -> str:
    """Read only a bounded plain-text PAT, never include its contents in errors."""
    path = token_path()
    try:
        with path.open(encoding="utf-8-sig") as source:
            value = source.read(MAX_TOKEN_LENGTH + 3)
    except FileNotFoundError:
        raise RiAccessError(f"Token-Datei fehlt: {path}. Vollständigen Proton-Pass-Token dort als einzelne Zeile einfügen.") from None
    except (OSError, UnicodeError):
        raise RiAccessError(f"Token-Datei nicht lesbar: {path}. UTF-8-Textdatei und Zugriffsrechte prüfen.") from None
    token = value.rstrip("\r\n")
    identifier, separator, key = token.partition("::")
    if (not token or len(value) > MAX_TOKEN_LENGTH + 2 or len(token) > MAX_TOKEN_LENGTH
            or not identifier.startswith("pst_") or len(identifier) <= 4
            or separator != "::" or not key or "::" in key
            or any(char.isspace() or ord(char) < 32 for char in token)):
        raise RiAccessError(f"Token-Datei leer oder ungültig: {path}. Nur den vollständigen Token eintragen, ohne Anführungszeichen.")
    return token


def find_cli() -> str | None:
    """Find the CLI in PATH or its official per-user Windows install directory."""
    cli = shutil.which("pass-cli.exe" if sys.platform == "win32" else "pass-cli")
    if cli is None and sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        candidate = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "ProtonPass" / "pass-cli.exe"
        if candidate.is_file():
            cli = str(candidate)
    return cli


class ProtonRiSession:
    """Short-lived PAT session exposing only metadata and fixed login fields."""

    def __init__(self, token: str, *, cli: str | None = None):
        self._token = token
        self._cli = cli or find_cli()
        self._directory = None
        self._env = None
        self.cleanup_warning = False

    def __repr__(self):
        return "ProtonRiSession(<geschützt>)"

    def _call(self, operation: str, reference: RiReference | None = None, share_id: str | None = None) -> str:
        # Callers choose an operation, never arbitrary command-line arguments.
        commands = {
            "version": ["--version"], "login": ["login"],
            "logout": ["logout"], "cleanup": ["logout", "--force"],
            "vaults": ["vault", "list", "--output", "json"],
        }
        if operation == "items" and share_id and _ID.fullmatch(share_id):
            args = ["item", "list", "--share-id=" + share_id, "--filter-state", "active", "--output", "json"]
        elif operation in {"username", "email", "password"} and reference is not None:
            args = ["item", "view", "--share-id=" + reference.share_id, "--item-id=" + reference.item_id,
                    "--field", operation, "--output", "human"]
        elif operation in commands:
            args = commands[operation]
        else:
            raise RiAccessError("Nicht erlaubte Operation für den RI-Zugang.")
        if not self._cli or self._env is None:
            raise RiAccessError("Proton-Testsitzung ist nicht verfügbar.")
        env = dict(self._env)
        if operation == "login":
            env["PROTON_PASS_PERSONAL_ACCESS_TOKEN"] = self._token
        try:
            result = subprocess.run(
                [self._cli, *args], env=env, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", timeout=45 if operation == "login" else 30,
                check=False,
            )
            if result.returncode:
                raise RiAccessError("Proton-Zugriff fehlgeschlagen; Token in .env/ri_token.txt, dessen Gültigkeit und Netzwerk prüfen.")
            return result.stdout
        except (OSError, subprocess.TimeoutExpired):
            raise RiAccessError("Proton CLI nicht erreichbar oder Zeitüberschreitung.") from None
        finally:
            env.pop("PROTON_PASS_PERSONAL_ACCESS_TOKEN", None)

    def __enter__(self):
        if not self._cli:
            raise RiAccessError("Proton Pass CLI fehlt im PATH.")
        self._directory = TemporaryDirectory(prefix="ratsi_ri_credentials_")
        self._env = {key: value for key, value in os.environ.items()
                     if not key.startswith(("PROTON_PASS_", "PASS_"))}
        self._env.update(PROTON_PASS_SESSION_DIR=self._directory.name,
                         PROTON_PASS_KEY_PROVIDER="fs", PASS_LOG_LEVEL="off")
        try:
            if not re.search(r"\b2\.7\.0\b", self._call("version")):
                raise RiAccessError("Dieser RI-Test ist für Proton Pass CLI 2.7.0 geprüft.")
            self._call("login")
            self._token = None
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        """Close only this session, keeping remote logout uncertainty explicit."""
        if self._env is None:
            return
        try:
            self._call("logout")
        except RiAccessError:
            self.cleanup_warning = True
            try:
                self._call("cleanup")
            except RiAccessError:
                pass
        finally:
            self._token = None
            self._env.clear()
            self._env = None
            if self._directory is not None:
                self._directory.cleanup()
                self._directory = None

    def __exit__(self, *args):
        self.close()

    def discover_reference(self) -> RiReference:
        """Accept exactly one accessible vault containing exactly one active login."""
        try:
            vaults = json.loads(self._call("vaults"))["vaults"]
            if not isinstance(vaults, list) or len(vaults) != 1:
                raise ValueError
            share_id = vaults[0]["share_id"]
            if not isinstance(share_id, str) or not _ID.fullmatch(share_id):
                raise ValueError
            items = json.loads(self._call("items", share_id=share_id))["items"]
            if not isinstance(items, list) or len(items) != 1:
                raise ValueError
            item = items[0]
            if item["share_id"] != share_id or item["item_type"].casefold() != "login" or item["state"].casefold() != "active":
                raise ValueError
            return RiReference(share_id, item["id"])
        except (ValueError, TypeError, KeyError, AttributeError):
            raise RiAccessError(
                "Erforderlich ist genau ein freigegebener Tresor mit genau einem aktiven Login-Eintrag."
            ) from None

    def credentials(self) -> RiCredentials:
        """Read fields only after verifying exactly one shared vault and active login."""
        reference = self.discover_reference()
        username = self._field("username", reference)
        if not username:
            username = self._field("email", reference)
        password = self._field("password", reference)
        if not username or not password or len(username) > 1024 or len(password) > 16000 or any(c in username + password for c in "\r\n\0"):
            raise RiAccessError("RI-Eintrag enthält keinen unterstützten vollständigen Zugang.")
        return RiCredentials(username, password)

    def _field(self, name: str, reference: RiReference) -> str:
        value = self._call(name, reference=reference)
        # Strip only the CLI's line terminator; password spaces remain significant.
        if value.endswith("\r\n"):
            return value[:-2]
        return value.removesuffix("\n")
