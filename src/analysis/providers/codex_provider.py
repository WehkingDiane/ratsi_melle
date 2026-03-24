"""OpenAI (Codex / ChatGPT) provider for KI analysis."""

from __future__ import annotations

from pathlib import Path

from src.analysis.providers.base import KiProvider, KiResponse
from src.analysis.providers._pdf_utils import extract_pdf_text
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

    def analyze(
        self,
        *,
        prompt: str,
        context: str,
        model: str | None = None,
        pdf_paths: list[Path] | None = None,
    ) -> KiResponse:
        model_name = model or self.default_model
        full_context = _append_pdf_text(context, pdf_paths)
        user_message = _build_user_message(prompt, full_context)

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


def _append_pdf_text(context: str, pdf_paths: list[Path] | None) -> str:
    """Append extracted PDF text to the context string (text-extraction fallback)."""
    if not pdf_paths:
        return context
    parts = [context] if context else []
    for pdf_path in pdf_paths:
        text = extract_pdf_text(pdf_path)
        if text:
            parts.append(f"\n\n### PDF: {pdf_path.name}\n\n{text}")
        else:
            parts.append(f"\n\n### PDF: {pdf_path.name}\n\n[Text nicht extrahierbar]")
    return "".join(parts)


def _build_user_message(prompt: str, context: str) -> str:
    truncated_context = context[:_MAX_CONTEXT_CHARS]
    return (
        f"## Analysegrundlage\n\n{truncated_context}\n\n"
        f"## Analyseauftrag\n\n{prompt}"
    )
