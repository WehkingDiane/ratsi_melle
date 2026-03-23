"""OpenAI (Codex / ChatGPT) provider for KI analysis."""

from __future__ import annotations

from src.analysis.providers.base import KiProvider, KiResponse
from src.config.secrets import get_api_key as _get_api_key

_DEFAULT_MODEL = "gpt-4o-mini"
_MAX_CONTEXT_CHARS = 100_000


class CodexProvider(KiProvider):
    """Calls the OpenAI Chat Completions API using the openai SDK."""

    def __init__(self, api_key: str | None = None, *, max_tokens: int = 2048) -> None:
        """
        Args:
            api_key: OpenAI API key. Falls back to OS keychain, then
                     ``OPENAI_API_KEY`` env var.
            max_tokens: Maximum tokens to generate in the response.
        """
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "openai SDK not installed. Run: pip install openai"
            ) from exc

        resolved_key = api_key or _get_api_key("codex")
        self._client = openai.OpenAI(api_key=resolved_key) if resolved_key else openai.OpenAI()
        self._max_tokens = max_tokens

    @property
    def provider_id(self) -> str:
        return "codex"

    @property
    def default_model(self) -> str:
        return _DEFAULT_MODEL

    def analyze(self, *, prompt: str, context: str, model: str | None = None) -> KiResponse:
        model_name = model or self.default_model
        user_message = _build_user_message(prompt, context)

        completion = self._client.chat.completions.create(
            model=model_name,
            max_tokens=self._max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du analysierst kommunalpolitische Dokumente aus dem "
                        "Ratsinformationssystem Melle. Antworte auf Deutsch."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
        )
        choice = completion.choices[0] if completion.choices else None
        response_text = choice.message.content or "" if choice else ""
        usage = completion.usage
        return KiResponse(
            provider_id=self.provider_id,
            model_name=model_name,
            response_text=response_text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


def _build_user_message(prompt: str, context: str) -> str:
    truncated_context = context[:_MAX_CONTEXT_CHARS]
    return (
        f"## Analysegrundlage\n\n{truncated_context}\n\n"
        f"## Analyseauftrag\n\n{prompt}"
    )
