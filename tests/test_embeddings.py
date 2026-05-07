"""Tests for embedding model loading."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.analysis import embeddings


def test_harrier_embedder_passes_configured_huggingface_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeSentenceTransformer:
        def __init__(self, *args, **kwargs) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(
        embeddings,
        "configure_huggingface_token_env",
        lambda: "hf_stored",
    )
    monkeypatch.setattr(embeddings, "_detect_device", lambda: "cpu")
    fake_module = SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)

    with patch.dict("sys.modules", {"sentence_transformers": fake_module}):
        embeddings.HarrierEmbedder()._get_model()

    assert captured["kwargs"]["token"] == "hf_stored"
