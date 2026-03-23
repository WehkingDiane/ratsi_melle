"""Anthropic Claude provider for KI analysis."""

from __future__ import annotations

import base64
from pathlib import Path

from src.analysis.providers.base import KiProvider, KiResponse
from src.config.secrets import get_api_key as _get_api_key

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

        resolved_key = api_key or _get_api_key("claude")
        self._client = anthropic.Anthropic(api_key=resolved_key) if resolved_key else anthropic.Anthropic()
        self._max_tokens = max_tokens

    @property
    def provider_id(self) -> str:
        return "claude"

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
        content = _build_content_blocks(prompt, context, pdf_paths)

        message = self._client.messages.create(
            model=model_name,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        response_text = message.content[0].text if message.content else ""
        return KiResponse(
            provider_id=self.provider_id,
            model_name=model_name,
            response_text=response_text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


def _build_content_blocks(
    prompt: str, context: str, pdf_paths: list[Path] | None
) -> list[dict] | str:
    """Build the message content – plain string when no PDFs, list of blocks otherwise."""
    if not pdf_paths:
        return _build_text_message(prompt, context)

    blocks: list[dict] = []
    if context:
        truncated = context[:_MAX_CONTEXT_CHARS]
        blocks.append({"type": "text", "text": f"## Analysegrundlage\n\n{truncated}"})

    for pdf_path in pdf_paths:
        try:
            pdf_data = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")
            blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_data,
                },
            })
        except OSError:
            blocks.append({
                "type": "text",
                "text": f"[PDF nicht lesbar: {pdf_path.name}]",
            })

    blocks.append({"type": "text", "text": f"## Analyseauftrag\n\n{prompt}"})
    return blocks


def _build_text_message(prompt: str, context: str) -> str:
    truncated_context = context[:_MAX_CONTEXT_CHARS]
    return (
        f"## Analysegrundlage\n\n{truncated_context}\n\n"
        f"## Analyseauftrag\n\n{prompt}"
    )
