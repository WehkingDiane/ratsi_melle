"""Secure API key storage backed by the OS credential store (keyring).

Priority order when resolving a key:
  1. OS keychain via keyring  (Windows Credential Manager / macOS Keychain / …)
  2. Environment variable     (ANTHROPIC_API_KEY, OPENAI_API_KEY, …)

Keys are stored under the service name ``ratsi_melle`` with the
provider_id (e.g. ``claude``, ``codex``) as the account name.
"""

from __future__ import annotations

import os

_SERVICE = "ratsi_melle"

# Env-var fallback for each provider
_ENV_VARS: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
}


def get_api_key(provider_id: str) -> str | None:
    """Return the API key for *provider_id*, or None if not configured.

    Checks the OS keychain first, then falls back to the corresponding
    environment variable.
    """
    try:
        import keyring

        stored = keyring.get_password(_SERVICE, provider_id)
        if stored:
            return stored
    except Exception:  # noqa: BLE001
        pass

    env_var = _ENV_VARS.get(provider_id)
    if env_var:
        return os.environ.get(env_var) or None
    return None


def set_api_key(provider_id: str, key: str) -> None:
    """Persist *key* for *provider_id* in the OS keychain.

    Raises:
        ImportError: if the keyring package is not installed.
        RuntimeError: if the OS keychain is not accessible.
    """
    import keyring

    keyring.set_password(_SERVICE, provider_id, key)


def delete_api_key(provider_id: str) -> None:
    """Remove the stored key for *provider_id* from the OS keychain.

    Silently ignores the case where no key was stored.
    """
    try:
        import keyring

        keyring.delete_password(_SERVICE, provider_id)
    except Exception:  # noqa: BLE001
        pass


def has_api_key(provider_id: str) -> bool:
    """Return True if a key for *provider_id* is available from any source."""
    return get_api_key(provider_id) is not None


def key_source(provider_id: str) -> str:
    """Return a human-readable string describing where the key comes from.

    Returns one of: ``"keychain"``, ``"env"`` (*ENV_VAR_NAME*), ``"nicht gesetzt"``.
    """
    try:
        import keyring

        if keyring.get_password(_SERVICE, provider_id):
            return "keychain"
    except Exception:  # noqa: BLE001
        pass

    env_var = _ENV_VARS.get(provider_id)
    if env_var and os.environ.get(env_var):
        return f"env ({env_var})"
    return "nicht gesetzt"
