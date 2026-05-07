"""Secure API key storage backed by the OS credential store (keyring).

Priority order when resolving a key:
  1. OS keychain via keyring  (Windows Credential Manager / macOS Keychain / …)
  2. Environment variable     (ANTHROPIC_API_KEY, OPENAI_API_KEY, HF_TOKEN, …)

Keys are stored under the service name ``ratsi_melle`` with the
provider_id (e.g. ``claude``, ``codex``, ``huggingface``) as the account name.
"""

from __future__ import annotations

import os

_SERVICE = "ratsi_melle"

# Env-var fallback for each provider. The first name is used for status text.
_ENV_VARS: dict[str, tuple[str, ...]] = {
    "claude": ("ANTHROPIC_API_KEY",),
    "codex": ("OPENAI_API_KEY",),
    "huggingface": ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
}
_MANAGED_HUGGINGFACE_TOKEN: str | None = None


def _get_keyring_key(provider_id: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(_SERVICE, provider_id)
    except Exception:  # noqa: BLE001
        return None


def _get_env_key(provider_id: str) -> str | None:
    for env_var in _ENV_VARS.get(provider_id, ()):
        value = os.environ.get(env_var)
        if value and not (
            provider_id == "huggingface"
            and _MANAGED_HUGGINGFACE_TOKEN
            and value == _MANAGED_HUGGINGFACE_TOKEN
        ):
            return value
    return None


def _clear_managed_huggingface_env() -> None:
    global _MANAGED_HUGGINGFACE_TOKEN

    if not _MANAGED_HUGGINGFACE_TOKEN:
        return
    for env_var in _ENV_VARS["huggingface"]:
        if os.environ.get(env_var) == _MANAGED_HUGGINGFACE_TOKEN:
            os.environ.pop(env_var, None)
    _MANAGED_HUGGINGFACE_TOKEN = None


def get_api_key(provider_id: str) -> str | None:
    """Return the API key for *provider_id*, or None if not configured.

    Checks the OS keychain first, then falls back to the corresponding
    environment variable.
    """
    stored = _get_keyring_key(provider_id)
    if stored:
        return stored
    return _get_env_key(provider_id)


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
    if provider_id == "huggingface":
        _clear_managed_huggingface_env()


def has_api_key(provider_id: str) -> bool:
    """Return True if a key for *provider_id* is available from any source."""
    return get_api_key(provider_id) is not None


def key_source(provider_id: str) -> str:
    """Return a human-readable string describing where the key comes from.

    Returns one of: ``"keychain"``, ``"env"`` (*ENV_VAR_NAME*), ``"nicht gesetzt"``.
    """
    if _get_keyring_key(provider_id):
        return "keychain"

    for env_var in _ENV_VARS.get(provider_id, ()):
        value = os.environ.get(env_var)
        if value and not (
            provider_id == "huggingface"
            and _MANAGED_HUGGINGFACE_TOKEN
            and value == _MANAGED_HUGGINGFACE_TOKEN
        ):
            return f"env ({env_var})"
    return "nicht gesetzt"


def configure_huggingface_token_env() -> str | None:
    """Expose the configured Hugging Face token to libraries that read env vars."""
    global _MANAGED_HUGGINGFACE_TOKEN

    token = _get_keyring_key("huggingface")
    if not token:
        _clear_managed_huggingface_env()
        return _get_env_key("huggingface")
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGING_FACE_HUB_TOKEN"] = token
    _MANAGED_HUGGINGFACE_TOKEN = token
    return token
