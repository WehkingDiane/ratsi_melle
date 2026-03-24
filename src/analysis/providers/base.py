"""Abstract base for KI provider integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KiResponse:
    """Result of a KI provider call."""

    provider_id: str
    model_name: str
    response_text: str
    input_tokens: int = 0
    output_tokens: int = 0


class KiProvider(ABC):
    """Exchangeable interface for KI model providers (Claude, Codex, Ollama, …)."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier, e.g. 'claude', 'codex', 'ollama'."""

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model name used when caller does not override."""

    @abstractmethod
    def analyze(
        self,
        *,
        prompt: str,
        context: str,
        model: str | None = None,
        pdf_paths: list[Path] | None = None,
    ) -> KiResponse:
        """Send prompt and context to the model and return the response.

        Args:
            prompt: The user-provided analysis instruction.
            context: Local document inventory / scope markdown as background.
            model: Override model name; uses ``default_model`` when None.
            pdf_paths: Optional list of PDF files to attach natively (provider
                support varies; falls back to text extraction where unavailable).
        """
