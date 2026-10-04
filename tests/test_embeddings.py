"""Tests for embedding model loading."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.analysis import embeddings
from src.analysis import bm25_sparse
from src.config.embedding_models import BM25_MODEL
from src.observability import run_cli

import pytest


def test_harrier_embedder_uses_prepared_local_model(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeSentenceTransformer:
        def __init__(self, *args, **kwargs) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(embeddings, "prepared_model_path", lambda component: Path("/models/harrier") if component == "dense_model" else None)
    monkeypatch.setattr(embeddings, "_detect_device", lambda: "cpu")
    fake_module = SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)

    with patch.dict("sys.modules", {"sentence_transformers": fake_module}):
        embeddings.HarrierEmbedder()._get_model()

    assert captured["args"] == ("/models/harrier",)
    assert captured["kwargs"]["model_kwargs"] == {"dtype": "auto"}
    assert captured["kwargs"]["local_files_only"] is True
    assert "token" not in captured["kwargs"]


def test_bm25_uses_prepared_local_snapshot(monkeypatch):
    captured = {}
    monkeypatch.setattr(bm25_sparse, "prepared_model_path", lambda component: Path("/models/bm25") if component == "sparse_model" else None)

    class FakeSparseTextEmbedding:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with patch.dict("sys.modules", {"fastembed": SimpleNamespace(SparseTextEmbedding=FakeSparseTextEmbedding)}):
        bm25_sparse.BM25Encoder()._get_model()

    assert captured == {
        "model_name": BM25_MODEL.model_id,
        "specific_model_path": "/models/bm25",
        "local_files_only": True,
    }


def test_fastembed_bm25_loads_local_snapshot_without_hub(tmp_path, monkeypatch):
    pytest.importorskip("fastembed")
    import huggingface_hub

    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "english.txt").write_text("the\nand\n", encoding="utf-8")
    monkeypatch.setattr(bm25_sparse, "prepared_model_path", lambda component: tmp_path)
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected Hub call")))

    result = bm25_sparse.BM25Encoder().encode_query("Schule und Verkehr")

    assert result["indices"]
    assert len(result["indices"]) == len(result["values"])


def test_missing_prepared_models_return_short_cli_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("RATSI_LOG_DIR", str(tmp_path / "logs"))

    with pytest.raises(SystemExit) as exit_info:
        run_cli("embedding_model_test", lambda: embeddings.HarrierEmbedder()._get_model())

    assert exit_info.value.code == 1
    output = capsys.readouterr()
    assert "prepare_embedding_models.py --download" in output.err
    assert "Traceback" not in output.out + output.err
