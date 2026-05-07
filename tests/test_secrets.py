"""Tests for the secrets / API key management module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.config.secrets import (
    configure_huggingface_token_env,
    delete_api_key,
    get_api_key,
    has_api_key,
    key_source,
    set_api_key,
)


def _make_keyring(stored: dict[str, str]):
    """Return a mock keyring module with preset stored values."""
    mock = MagicMock()
    mock.get_password.side_effect = lambda svc, acc: stored.get(acc)
    mock.set_password.side_effect = lambda svc, acc, val: stored.update({acc: val})
    mock.delete_password.side_effect = lambda svc, acc: stored.pop(acc, None)
    return mock


def test_get_api_key_from_keyring() -> None:
    mock_kr = _make_keyring({"claude": "sk-test-claude"})
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert get_api_key("claude") == "sk-test-claude"


def test_get_api_key_falls_back_to_env(monkeypatch) -> None:
    mock_kr = _make_keyring({})  # nothing in keychain
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-claude")
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert get_api_key("claude") == "sk-env-claude"


def test_get_huggingface_token_falls_back_to_supported_env(monkeypatch) -> None:
    mock_kr = _make_keyring({})
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HUGGINGFACE_HUB_TOKEN", "hf_env_token")
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert get_api_key("huggingface") == "hf_env_token"


def test_get_api_key_returns_none_when_not_set(monkeypatch) -> None:
    mock_kr = _make_keyring({})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert get_api_key("claude") is None


def test_get_api_key_keyring_error_falls_back_to_env(monkeypatch) -> None:
    mock_kr = MagicMock()
    mock_kr.get_password.side_effect = RuntimeError("keychain not available")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-openai")
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert get_api_key("codex") == "sk-env-openai"


def test_set_api_key_stores_in_keyring() -> None:
    stored: dict = {}
    mock_kr = _make_keyring(stored)
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        set_api_key("claude", "sk-new-key")
    assert stored["claude"] == "sk-new-key"


def test_delete_api_key_removes_entry() -> None:
    stored: dict = {"claude": "sk-old"}
    mock_kr = _make_keyring(stored)
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        delete_api_key("claude")
    assert "claude" not in stored


def test_delete_api_key_silently_ignores_missing() -> None:
    mock_kr = _make_keyring({})
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        delete_api_key("claude")  # should not raise


def test_has_api_key_true_when_in_keyring() -> None:
    mock_kr = _make_keyring({"codex": "sk-openai"})
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert has_api_key("codex") is True


def test_has_api_key_false_when_missing(monkeypatch) -> None:
    mock_kr = _make_keyring({})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert has_api_key("codex") is False


def test_key_source_keychain() -> None:
    mock_kr = _make_keyring({"claude": "sk-x"})
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert key_source("claude") == "keychain"


def test_key_source_env(monkeypatch) -> None:
    mock_kr = _make_keyring({})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        src = key_source("claude")
    assert "env" in src and "ANTHROPIC_API_KEY" in src


def test_configure_huggingface_token_env_sets_hub_env_vars(monkeypatch) -> None:
    mock_kr = _make_keyring({"huggingface": "hf_stored"})
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        configure_huggingface_token_env()

    assert os.environ["HF_TOKEN"] == "hf_stored"
    assert os.environ["HUGGINGFACE_HUB_TOKEN"] == "hf_stored"


def test_key_source_not_set(monkeypatch) -> None:
    mock_kr = _make_keyring({})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch.dict("sys.modules", {"keyring": mock_kr}):
        assert key_source("claude") == "nicht gesetzt"
