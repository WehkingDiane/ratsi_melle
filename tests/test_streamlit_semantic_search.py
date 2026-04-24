from __future__ import annotations

import importlib
from pathlib import Path

from src.interfaces.web import streamlit_app
from src.paths import LOCAL_INDEX_DB, QDRANT_DIR


def test_developer_script_options_include_all_build_paths() -> None:
    options = streamlit_app._developer_script_options()

    assert options["Sitzungen abrufen (fetch_sessions)"] == "fetch_sessions"
    assert options["Lokalen Index aufbauen (build_local_index)"] == "build_local_index"
    assert options["Online-Index aufbauen (build_online_index_db)"] == "build_online_index_db"
    assert options["Vektorindex aufbauen (build_vector_index)"] == "build_vector_index"


def test_collect_data_status_reports_existing_selected_db(tmp_path: Path) -> None:
    db_path = tmp_path / "local_index.sqlite"
    db_path.write_text("", encoding="utf-8")

    snapshot = streamlit_app._collect_data_status(db_path)

    assert snapshot["selected_db_name"] == "local_index.sqlite"
    assert snapshot["selected_db_exists"] is True


def test_collect_data_status_uses_cached_snapshot(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "local_index.sqlite"
    db_path.write_text("", encoding="utf-8")
    calls = {"count": 0}

    def fake_cached(db_path_str: str):
        calls["count"] += 1
        return {"selected_db_name": Path(db_path_str).name}

    monkeypatch.setattr(streamlit_app, "_collect_data_status_cached", fake_cached)

    first = streamlit_app._collect_data_status(db_path)
    second = streamlit_app._collect_data_status(db_path)

    assert first == {"selected_db_name": "local_index.sqlite"}
    assert second == {"selected_db_name": "local_index.sqlite"}
    assert calls["count"] == 2


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


def test_developer_preset_commands_use_selected_year_and_months() -> None:
    commands = streamlit_app._developer_preset_commands(
        "Fetch + Build Local",
        year=2026,
        months=["4", "5"],
    )

    assert commands[0][-4:] == ["2026", "--months", "4", "5"]
    assert commands[1][-1] == str(streamlit_app.REPO_ROOT / "scripts" / "build_local_index.py")


def test_developer_preset_commands_allow_empty_month_selection() -> None:
    commands = streamlit_app._developer_preset_commands(
        "Build Online Index",
        year=2027,
        months=[],
    )

    assert commands == [
        [streamlit_app.sys.executable, str(streamlit_app.REPO_ROOT / "scripts" / "build_online_index_db.py"), "2027"]
    ]
