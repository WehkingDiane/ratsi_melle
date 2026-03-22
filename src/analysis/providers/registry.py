"""Provider registry: maps provider_id strings to KiProvider instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.providers.base import KiProvider

# Built-in provider IDs
PROVIDER_NONE = "none"
PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"
PROVIDER_OLLAMA = "ollama"

KNOWN_PROVIDER_IDS: tuple[str, ...] = (
    PROVIDER_NONE,
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    PROVIDER_OLLAMA,
)


def build_provider(provider_id: str, **kwargs: object) -> KiProvider:
    """Instantiate a KiProvider by its identifier.

    Args:
        provider_id: One of the PROVIDER_* constants.
        **kwargs: Forwarded to the provider constructor (e.g. api_key, base_url).

    Raises:
        ValueError: If provider_id is not known or is ``PROVIDER_NONE``.
        ImportError: If the required SDK is not installed.
    """
    if provider_id == PROVIDER_NONE:
        raise ValueError("provider_id 'none' has no associated KiProvider.")

    if provider_id == PROVIDER_CLAUDE:
        from src.analysis.providers.claude_provider import ClaudeProvider

        return ClaudeProvider(**kwargs)  # type: ignore[arg-type]

    if provider_id == PROVIDER_CODEX:
        from src.analysis.providers.codex_provider import CodexProvider

        return CodexProvider(**kwargs)  # type: ignore[arg-type]

    if provider_id == PROVIDER_OLLAMA:
        from src.analysis.providers.ollama_provider import OllamaProvider

        return OllamaProvider(**kwargs)  # type: ignore[arg-type]

    raise ValueError(
        f"Unknown provider_id {provider_id!r}. Known: {', '.join(KNOWN_PROVIDER_IDS)}"
    )
