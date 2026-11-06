"""Read one pinned RI login from Proton Pass without exposing credential values."""

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


SERVICE = "ratsi_melle_ri"
TOKEN_USERNAME = "proton_pass_pat"
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


def reference_path() -> Path:
    """Return the OS-specific local configuration path outside the repository."""
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise RiAccessError("Windows-Benutzerdatenverzeichnis ist nicht verfügbar.")
        return Path(root) / "ratsi_melle" / "ri_proton_access.json"
    if sys.platform == "linux":
        return Path.home() / ".local" / "share" / "ratsi_melle" / "ri_proton_access.json"
    raise RiAccessError("RI-Zugang unterstützt Windows und Linux/WSL.")


def load_reference(path: Path) -> RiReference:
    """Load only the two fixed reference IDs, never account credentials."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if set(data) != {"share_id", "item_id"}:
            raise ValueError
        return RiReference(**data)
    except (OSError, ValueError, TypeError):
        raise RiAccessError(
            "RI-Eintragsbindung fehlt oder ist ungültig. Zuerst --configure ausführen."
        ) from None


def save_reference(path: Path, reference: RiReference) -> None:
    """Create the local reference once; never silently rebind an existing entry."""
    if path.exists():
        if load_reference(path) != reference:
            raise RiAccessError("Vorhandene RI-Eintragsbindung weicht ab; kein automatischer Wechsel.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as target:
            if sys.platform != "win32":
                os.chmod(path, 0o600)
            json.dump({"share_id": reference.share_id, "item_id": reference.item_id}, target)
            target.write("\n")
    except OSError:
        raise RiAccessError("Lokale RI-Eintragsbindung konnte nicht gespeichert werden.") from None


def read_os_token() -> str:
    """Read the PAT from an explicit OS backend with no plaintext fallback."""
    try:
        if sys.platform == "win32":
            from keyring.backends.Windows import WinVaultKeyring
            backend = WinVaultKeyring()
        elif sys.platform == "linux":
            from keyring.backends.SecretService import Keyring
            import secretstorage

            class LoginKeyring(Keyring):
                def get_preferred_collection(self):
                    bus = secretstorage.dbus_init()
                    try:
                        collection = secretstorage.Collection(bus, "/org/freedesktop/secrets/collection/login")
                        if collection.is_locked():
                            raise RiAccessError("Lokalen WSL-Schlüsselspeicher zuerst entsperren.")
                        return collection
                    except Exception:
                        bus.close()
                        raise
            backend = LoginKeyring()
        else:
            raise RiAccessError("RI-Zugang unterstützt Windows und Linux/WSL.")
        token = backend.get_password(SERVICE, TOKEN_USERNAME)
        if not isinstance(token, str) or not token.startswith("pst_") or "::" not in token:
            raise RiAccessError("Kein vollständiger RI-Token im lokalen Speicher hinterlegt.")
        return token
    except RiAccessError:
        raise
    except Exception:
        raise RiAccessError("RI-Token konnte nicht aus dem geschützten Speicher gelesen werden.") from None


class ProtonRiSession:
    """Short-lived PAT session exposing only metadata and fixed login fields."""

    def __init__(self, token: str, *, cli: str | None = None):
        self._token = token
        self._cli = cli or shutil.which("pass-cli.exe" if sys.platform == "win32" else "pass-cli")
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
                raise RiAccessError("Proton-Zugriff fehlgeschlagen; Token, Ablauf oder Speicher prüfen.")
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
                         PROTON_PASS_KEY_PROVIDER="keyring", PASS_LOG_LEVEL="off")
        if sys.platform == "linux":
            self._env["PROTON_PASS_LINUX_KEYRING"] = "dbus"
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

    def credentials(self, reference: RiReference) -> RiCredentials:
        """Read only the pinned entry; refuse additional or changed entries first."""
        if self.discover_reference() != reference:
            raise RiAccessError("RI-Eintragsbindung stimmt nicht; kein automatischer Wechsel.")
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
