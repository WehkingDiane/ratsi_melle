"""Harrier embedding service with lazy model loading."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from src.config.secrets import configure_huggingface_token_env

# Suppress HuggingFace Hub unauthenticated-request warning – no token needed
# for public models and we don't want to prompt users to create an account.
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "microsoft/harrier-oss-v1-0.6b"
_QUERY_INSTRUCTION = (
    "Instruct: Retrieve semantically similar municipal council documents\nQuery: "
)


def _detect_device() -> str:
    """Return the best available compute device: xpu > cpu."""
    try:
        import torch
        if torch.xpu.is_available():
            return "xpu"
    except (ImportError, AttributeError):
        pass
    return "cpu"


class HarrierEmbedder:
    """Embedding service backed by the Harrier OSS model.

    The model is loaded on first use (lazy loading) to avoid startup overhead.
    Automatically uses Intel XPU (Arc GPU) when available, falls back to CPU.
    """

    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_model(self) -> "SentenceTransformer":
        if self._model is None:
            configure_huggingface_token_env()
            from sentence_transformers import SentenceTransformer

            device = _detect_device()
            self._model = SentenceTransformer(
                _MODEL_NAME,
                device=device,
                model_kwargs={"torch_dtype": "auto"},
            )
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents for indexing (no instruction prompt).

        Args:
            texts: Plaintext strings to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        model = self._get_model()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query with the instruction prompt.

        Args:
            text: The user's search query.

        Returns:
            A single embedding vector.
        """
        model = self._get_model()
        prompted = _QUERY_INSTRUCTION + text
        vector = model.encode(
            prompted,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()
