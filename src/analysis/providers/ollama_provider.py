"""Local Ollama provider for KI analysis (models up to 8B parameters)."""

from __future__ import annotations

from pathlib import Path

from src.analysis.providers.base import KiProvider, KiResponse
from src.analysis.providers._pdf_utils import extract_pdf_text

_DEFAULT_MODEL = "llama3.2:3b"
_DEFAULT_BASE_URL = "http://localhost:11434"
_MAX_CONTEXT_CHARS = 24_000  # conservative for small local models

# Models known to work well with Ollama (up to ~8B parameters).
# Used to populate model selection in the GUI.
SUPPORTED_MODELS: tuple[str, ...] = (
    "llama3.2:3b",
    "llama3.2:1b",
    "llama3.1:8b",
    "phi3:mini",
    "phi3:3.8b",
    "phi4-mini:3.8b",
    "gemma3:4b",
    "gemma3:1b",
    "mistral:7b",
    "qwen2.5:7b",
    "qwen2.5:3b",
    "qwen3:8b",
)


class OllamaProvider(KiProvider):
    """Calls a locally running Ollama instance via its HTTP API (no SDK required)."""

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        *,
        timeout: int = 120,
    ) -> None:
        """
        Args:
            base_url: URL of the Ollama server (default: http://localhost:11434).
            timeout: Request timeout in seconds.
        """
        try:
            import requests
        except ImportError as exc:
            raise ImportError(
                "requests library not installed. Run: pip install requests"
            ) from exc

        self._requests = requests
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def provider_id(self) -> str:
        return "ollama"

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

        options: dict = {"temperature": 0.3}

        payload = {
            "model": model_name,
            "prompt": user_message,
            "stream": False,
            "options": options,
        }
        response = self._requests.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data: dict = response.json()
        response_text = data.get("response", "")
        return KiResponse(
            provider_id=self.provider_id,
            model_name=model_name,
            response_text=response_text,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )

    def list_local_models(self) -> list[str]:
        """Return model names currently available in the local Ollama instance."""
        response = self._requests.get(f"{self._base_url}/api/tags", timeout=10)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]


def _append_pdf_text(context: str, pdf_paths: list[Path] | None) -> str:
    """Append extracted PDF text to the context (text-extraction fallback for Ollama)."""
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
        "Du analysierst kommunalpolitische Dokumente. Antworte auf Deutsch.\n\n"
        f"## Analysegrundlage\n\n{truncated_context}\n\n"
        f"## Analyseauftrag\n\n{prompt}"
    )
