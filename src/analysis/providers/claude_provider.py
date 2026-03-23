"""Anthropic Claude provider for KI analysis."""

from __future__ import annotations

from src.analysis.providers.base import KiProvider, KiResponse


def _resolve_key(provider_id: str) -> str | None:
    try:
        from src.config.secrets import get_api_key
        return get_api_key(provider_id)
    except Exception:  # noqa: BLE001
        return None

_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_MAX_CONTEXT_CHARS = 180_000  # safe margin below 200k token context


class ClaudeProvider(KiProvider):
    """Calls the Anthropic Claude API using the anthropic SDK."""

    def __init__(self, api_key: str | None = None, *, max_tokens: int = 2048) -> None:
        """
        Args:
            api_key: Anthropic API key. Falls back to OS keychain, then
                     ``ANTHROPIC_API_KEY`` env var.
            max_tokens: Maximum tokens to generate in the response.
        """
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic SDK not installed. Run: pip install anthropic"
            ) from exc

        resolved_key = api_key or _resolve_key("claude")
        self._client = anthropic.Anthropic(api_key=resolved_key) if resolved_key else anthropic.Anthropic()
        self._max_tokens = max_tokens

    @property
    def provider_id(self) -> str:
        return "claude"

    @property
    def default_model(self) -> str:
        return _DEFAULT_MODEL

    def analyze(self, *, prompt: str, context: str, model: str | None = None) -> KiResponse:
        model_name = model or self.default_model
        user_message = _build_user_message(prompt, context)

        message = self._client.messages.create(
            model=model_name,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": user_message}],
        )
        response_text = message.content[0].text if message.content else ""
        return KiResponse(
            provider_id=self.provider_id,
            model_name=model_name,
            response_text=response_text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


def _build_user_message(prompt: str, context: str) -> str:
    truncated_context = context[:_MAX_CONTEXT_CHARS]
    return (
        f"## Analysegrundlage\n\n{truncated_context}\n\n"
        f"## Analyseauftrag\n\n{prompt}"
    )
