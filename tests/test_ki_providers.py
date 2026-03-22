"""Tests for KI provider infrastructure (no real API calls)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.analysis.providers.base import KiProvider, KiResponse
from src.analysis.providers.registry import (
    KNOWN_PROVIDER_IDS,
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    PROVIDER_NONE,
    PROVIDER_OLLAMA,
    build_provider,
)
from src.analysis.service import AnalysisRequest, AnalysisService


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_known_provider_ids_contains_all() -> None:
    assert PROVIDER_NONE in KNOWN_PROVIDER_IDS
    assert PROVIDER_CLAUDE in KNOWN_PROVIDER_IDS
    assert PROVIDER_CODEX in KNOWN_PROVIDER_IDS
    assert PROVIDER_OLLAMA in KNOWN_PROVIDER_IDS


def test_build_provider_none_raises() -> None:
    with pytest.raises(ValueError, match="none"):
        build_provider(PROVIDER_NONE)


def test_build_provider_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown_xyz"):
        build_provider("unknown_xyz")


# ---------------------------------------------------------------------------
# Claude provider (mocked anthropic SDK)
# ---------------------------------------------------------------------------


def _make_anthropic_mock(response_text: str = "KI-Antwort", in_tok: int = 10, out_tok: int = 20):
    mock_anthropic = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    msg.usage.input_tokens = in_tok
    msg.usage.output_tokens = out_tok
    mock_anthropic.Anthropic.return_value.messages.create.return_value = msg
    return mock_anthropic


def test_claude_provider_analyze() -> None:
    mock_anthropic = _make_anthropic_mock("Zusammenfassung der Sitzung.")
    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        provider = build_provider(PROVIDER_CLAUDE, api_key="test-key")
        result = provider.analyze(prompt="Fasse zusammen.", context="Dokument A, Dokument B")

    assert result.provider_id == PROVIDER_CLAUDE
    assert result.response_text == "Zusammenfassung der Sitzung."
    assert result.input_tokens == 10
    assert result.output_tokens == 20


def test_claude_provider_uses_default_model() -> None:
    mock_anthropic = _make_anthropic_mock()
    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        provider = build_provider(PROVIDER_CLAUDE, api_key="test-key")
        result = provider.analyze(prompt="Test", context="ctx")

    assert "haiku" in result.model_name or "claude" in result.model_name


def test_claude_provider_missing_sdk_raises() -> None:
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises((ImportError, TypeError)):
            build_provider(PROVIDER_CLAUDE)


# ---------------------------------------------------------------------------
# Codex provider (mocked openai SDK)
# ---------------------------------------------------------------------------


def _make_openai_mock(response_text: str = "OpenAI-Antwort"):
    mock_openai = MagicMock()
    choice = MagicMock()
    choice.message.content = response_text
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage.prompt_tokens = 15
    completion.usage.completion_tokens = 25
    mock_openai.OpenAI.return_value.chat.completions.create.return_value = completion
    return mock_openai


def test_codex_provider_analyze() -> None:
    mock_openai = _make_openai_mock("OpenAI-Ergebnis")
    with patch.dict("sys.modules", {"openai": mock_openai}):
        provider = build_provider(PROVIDER_CODEX, api_key="test-key")
        result = provider.analyze(prompt="Analysiere.", context="Sitzung 2026")

    assert result.provider_id == PROVIDER_CODEX
    assert result.response_text == "OpenAI-Ergebnis"
    assert result.input_tokens == 15
    assert result.output_tokens == 25


# ---------------------------------------------------------------------------
# Ollama provider (mocked requests)
# ---------------------------------------------------------------------------


def _make_requests_mock(response_text: str = "Lokale Antwort"):
    mock_requests = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {
        "response": response_text,
        "prompt_eval_count": 50,
        "eval_count": 30,
    }
    resp.raise_for_status = MagicMock()
    mock_requests.post.return_value = resp
    return mock_requests


def test_ollama_provider_analyze() -> None:
    mock_requests = _make_requests_mock("Ollama Ergebnis")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        provider = build_provider(PROVIDER_OLLAMA)
        result = provider.analyze(prompt="Erkläre.", context="TOP 3: Haushalt")

    assert result.provider_id == PROVIDER_OLLAMA
    assert result.response_text == "Ollama Ergebnis"
    assert result.input_tokens == 50
    assert result.output_tokens == 30


def test_ollama_provider_model_override() -> None:
    mock_requests = _make_requests_mock()
    with patch.dict("sys.modules", {"requests": mock_requests}):
        provider = build_provider(PROVIDER_OLLAMA)
        result = provider.analyze(prompt="Test", context="ctx", model="phi3:mini")

    assert result.model_name == "phi3:mini"


# ---------------------------------------------------------------------------
# AnalysisService integration with provider (mocked)
# ---------------------------------------------------------------------------


def _build_test_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "local_index.sqlite"
    session_dir = tmp_path / "sessions" / "2026-03-10_Rat"
    session_dir.mkdir(parents=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT, committee TEXT,
                meeting_name TEXT, session_path TEXT
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, agenda_item TEXT, title TEXT,
                document_type TEXT, local_path TEXT, url TEXT, content_type TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
            ("9001", "2026-03-10", "Rat", "Ratssitzung", str(session_dir)),
        )
        conn.commit()

    session = {"session_id": "9001", "date": "2026-03-10", "committee": "Rat"}
    return db_path, session


def test_service_with_ollama_provider(tmp_path: Path, monkeypatch) -> None:
    db_path, session = _build_test_db(tmp_path)

    summaries_dir = tmp_path / "summaries"
    prompts_dir = tmp_path / "prompts"
    latest_md = summaries_dir / "analysis_latest.md"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_SUMMARIES_DIR", summaries_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)

    mock_requests = _make_requests_mock("Ollama hat analysiert.")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        request = AnalysisRequest(
            db_path=db_path,
            session=session,
            scope="session",
            selected_tops=[],
            prompt="Was ist wichtig?",
            provider_id=PROVIDER_OLLAMA,
        )
        record = AnalysisService().run_journalistic_analysis(request)

    assert record.ki_response == "Ollama hat analysiert."
    assert record.model_name  # should be set from provider default


def test_service_without_provider_leaves_ki_response_empty(tmp_path: Path, monkeypatch) -> None:
    db_path, session = _build_test_db(tmp_path)

    summaries_dir = tmp_path / "summaries"
    prompts_dir = tmp_path / "prompts"
    latest_md = summaries_dir / "analysis_latest.md"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_SUMMARIES_DIR", summaries_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)

    request = AnalysisRequest(
        db_path=db_path,
        session=session,
        scope="session",
        selected_tops=[],
        prompt="Test",
        provider_id=PROVIDER_NONE,
    )
    record = AnalysisService().run_journalistic_analysis(request)
    assert record.ki_response == ""


def test_service_provider_error_stored_in_db(tmp_path: Path, monkeypatch) -> None:
    db_path, session = _build_test_db(tmp_path)

    summaries_dir = tmp_path / "summaries"
    prompts_dir = tmp_path / "prompts"
    latest_md = summaries_dir / "analysis_latest.md"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_SUMMARIES_DIR", summaries_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)

    mock_requests = MagicMock()
    mock_requests.post.side_effect = ConnectionError("Ollama nicht erreichbar")
    with patch.dict("sys.modules", {"requests": mock_requests}):
        request = AnalysisRequest(
            db_path=db_path,
            session=session,
            scope="session",
            selected_tops=[],
            prompt="Test",
            provider_id=PROVIDER_OLLAMA,
        )
        record = AnalysisService().run_journalistic_analysis(request)

    assert record.ki_response == ""

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, error_message FROM analysis_jobs WHERE id = ?", (record.job_id,)
        ).fetchone()
    assert row[0] == "error"
    assert "Ollama nicht erreichbar" in row[1]
