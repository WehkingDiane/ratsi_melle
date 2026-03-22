"""Provider-Tests mit echtem Dokumenttext aus dem Windkraft-PDF.

Fixture: tests/fixtures/windkraft_riemsloh_extracted.txt
  Quelle: Windpotenzialflaechen-Melle-Ortsrat-Riemsloh, Sitzung 2025-12-08
  Extrahiert via GPT-4o (Texterkennung aus originalem PDF)

Jeder Provider-Test laeuft nur, wenn ein API-Key verfuegbar ist.
Ollama laeuft nur, wenn ein lokaler Server erreichbar ist.

Explizit starten:
    pytest tests/test_windkraft_provider_analysis.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.secrets import get_api_key

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

_FIXTURE = Path("tests/fixtures/windkraft_riemsloh_extracted.txt")

_PROMPT = (
    "Fasse das Dokument in maximal 150 Woertern zusammen. "
    "Nenne: vorgeschlagene Flaechen, Anzahl moeglicher Windanlagen, "
    "Abstaende zur Wohnbebauung und wirtschaftliche Vorteile. "
    "Antworte auf Deutsch."
)


@pytest.fixture(scope="module")
def windkraft_text() -> str:
    assert _FIXTURE.exists(), f"Fixture fehlt: {_FIXTURE}"
    return _FIXTURE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Skip-Marker
# ---------------------------------------------------------------------------

skip_no_codex = pytest.mark.skipif(
    get_api_key("codex") is None,
    reason="Kein Codex-API-Key (keychain oder OPENAI_API_KEY).",
)
skip_no_claude = pytest.mark.skipif(
    get_api_key("claude") is None,
    reason="Kein Claude-API-Key (keychain oder ANTHROPIC_API_KEY).",
)


def _ollama_available_model() -> str | None:
    """Return the name of the first available Ollama model, or None."""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return models[0] if models else None
    except Exception:
        return None


_OLLAMA_MODEL = _ollama_available_model()

skip_no_ollama = pytest.mark.skipif(
    _OLLAMA_MODEL is None,
    reason="Ollama nicht erreichbar oder kein Modell geladen (localhost:11434).",
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_response(response, provider_id: str) -> None:
    print(f"\nProvider : {response.provider_id}")
    print(f"Modell   : {response.model_name}")
    print(f"Tokens   : {response.input_tokens} in / {response.output_tokens} out")
    print(f"\n--- Antwort ---\n{response.response_text}")

    assert response.provider_id == provider_id
    assert response.response_text, "Leere Antwort."
    assert len(response.response_text) > 40, "Antwort zu kurz."
    assert any(
        kw in response.response_text.lower()
        for kw in ("wind", "flaeche", "fläche", "anlage", "melle", "riemsloh", "wea")
    ), "Antwort enthaelt keinen thematisch passenden Begriff."


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@skip_no_codex
def test_codex_windkraft(windkraft_text: str) -> None:
    """Codex (gpt-4o-mini) analysiert den Windkraft-Dokumenttext."""
    from src.analysis.providers.codex_provider import CodexProvider

    provider = CodexProvider(max_tokens=400)
    response = provider.analyze(prompt=_PROMPT, context=windkraft_text)
    _assert_response(response, "codex")


@skip_no_claude
def test_claude_windkraft(windkraft_text: str) -> None:
    """Claude (haiku) analysiert den Windkraft-Dokumenttext."""
    from src.analysis.providers.claude_provider import ClaudeProvider

    provider = ClaudeProvider(max_tokens=400)
    response = provider.analyze(prompt=_PROMPT, context=windkraft_text)
    _assert_response(response, "claude")


@skip_no_ollama
def test_ollama_windkraft(windkraft_text: str) -> None:
    """Lokales Ollama-Modell analysiert den Windkraft-Dokumenttext."""
    from src.analysis.providers.ollama_provider import OllamaProvider

    print(f"\nVerwende Ollama-Modell: {_OLLAMA_MODEL}")
    provider = OllamaProvider(timeout=300)

    # qwen3-Modelle unterstuetzen einen Thinking-Modus der sehr langsam ist;
    # 'think: false' deaktiviert ihn fuer schnellere Antworten.
    extra: dict = {"think": False} if _OLLAMA_MODEL and "qwen3" in _OLLAMA_MODEL else {}

    response = provider.analyze(
        prompt=_PROMPT,
        context=windkraft_text,
        model=_OLLAMA_MODEL,
        extra_options=extra or None,
    )
    _assert_response(response, "ollama")
