from __future__ import annotations

import importlib
from pathlib import Path

from src.interfaces.web import streamlit_app
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR


def test_semantic_search_dependency_error_mentions_fastembed(monkeypatch) -> None:
    def fake_import_module(name: str):
        if name == "fastembed":
            raise ImportError("missing fastembed")
        return object()

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    message = streamlit_app._semantic_search_dependency_error()

    assert message is not None
    assert "`fastembed`" in message
    assert "pip install qdrant-client sentence-transformers fastembed" in message


def test_semantic_search_vector_dir_uses_local_index_mapping() -> None:
    assert streamlit_app._semantic_search_vector_dir(LOCAL_INDEX_DB) == QDRANT_DIR


def test_semantic_search_vector_dir_disables_other_databases(tmp_path: Path) -> None:
    other_db = tmp_path / "online_session_index.sqlite"

    assert streamlit_app._semantic_search_vector_dir(other_db) is None


def test_format_rrf_score_does_not_render_percent() -> None:
    assert streamlit_app._format_rrf_score(0.0327868852) == "0.0328"
