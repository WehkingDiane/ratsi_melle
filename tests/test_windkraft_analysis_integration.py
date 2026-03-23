"""Integration test: analyse Windkraft-PDF with Codex.

This test makes a real OpenAI API call and requires an API key stored
in the OS keychain or the OPENAI_API_KEY environment variable.

Run explicitly:
    pytest tests/test_windkraft_analysis_integration.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.analysis.extraction_pipeline import extract_text_for_analysis
from src.config.secrets import get_api_key

pytestmark = pytest.mark.live

# --------------------------------------------------------------------------- #
# Fixture: document path                                                       #
# --------------------------------------------------------------------------- #

_PDF_PATH = Path(
    "data/raw/2025/12/2025-12-08-Ortsrat-Riemsloh-6694"
    "/agenda"
    "/\u00d6-6-Berichterstattung-Windkraftanlagen-im-Ortsteil-Riemsloh-Westendorf-durch-Firma-Biocontruct"
    "/Windpotenzialfl\u00e4chen-Melle-Ortsrat-Riemsloh-016-0d933caf.pdf"
)

_PROMPT = (
    "Analysiere das folgende kommunalpolitische Dokument ueber Windkraftpotenzialflaechen "
    "in Melle-Riemsloh. Fasse die wichtigsten Aussagen zusammen: "
    "Welche Flaechen werden fuer Windkraft vorgeschlagen oder abgelehnt? "
    "Welche Bedenken oder Argumente werden genannt? "
    "Antworte auf Deutsch in maximal 300 Woertern."
)


# --------------------------------------------------------------------------- #
# Skip conditions                                                               #
# --------------------------------------------------------------------------- #

def _codex_api_key() -> str | None:
    return get_api_key("codex")


skip_no_key = pytest.mark.skipif(
    _codex_api_key() is None,
    reason="Kein Codex-API-Key verfuegbar (keychain oder OPENAI_API_KEY).",
)

skip_no_pdf = pytest.mark.skipif(
    not _PDF_PATH.exists(),
    reason=f"PDF nicht gefunden: {_PDF_PATH}",
)


# --------------------------------------------------------------------------- #
# Tests                                                                         #
# --------------------------------------------------------------------------- #

@skip_no_pdf
def test_pdf_extraction_succeeds() -> None:
    """Extraction pipeline should return usable text from the PDF."""
    result = extract_text_for_analysis(_PDF_PATH, content_type="application/pdf", max_text_chars=60_000)

    print(f"\nExtraktionsstatus : {result.extraction_status}")
    print(f"Qualitaet         : {result.parsing_quality}")
    print(f"Zeichen extrahiert: {result.extracted_char_count}")
    print(f"Seiten            : {result.page_count}")
    print(f"Abschnitte erkannt: {[s['heading'] for s in result.detected_sections]}")

    assert result.extraction_status in {"ok", "partial"}, (
        f"Unerwarteter Extraktionsstatus: {result.extraction_status!r} "
        f"(Fehler: {result.extraction_error})"
    )
    assert result.extracted_char_count > 100, "Zu wenig Text extrahiert."


@skip_no_pdf
@skip_no_key
def test_codex_analyse_windkraft_pdf() -> None:
    """Send extracted PDF text to Codex and verify a German analysis response."""
    from src.analysis.providers.codex_provider import CodexProvider

    # 1. Text aus PDF extrahieren
    extraction = extract_text_for_analysis(
        _PDF_PATH, content_type="application/pdf", max_text_chars=60_000
    )
    assert extraction.extracted_char_count > 100, (
        f"PDF-Extraktion lieferte zu wenig Text ({extraction.extracted_char_count} Zeichen). "
        f"Status: {extraction.extraction_status}"
    )

    # 2. Kontext fuer den Provider aufbauen
    context = (
        f"Dokument: Windpotenzialflaechen Melle – Ortsrat Riemsloh (Sitzung 2025-12-08)\n"
        f"Extraktionsqualitaet: {extraction.parsing_quality} "
        f"({extraction.extracted_char_count} Zeichen, {extraction.page_count} Seiten)\n\n"
        f"--- Dokumentinhalt ---\n{extraction.extracted_text}"
    )

    # 3. Codex-Provider instanziieren (Key kommt aus Keychain/Env)
    provider = CodexProvider(max_tokens=600)

    # 4. Analyse durchfuehren
    response = provider.analyze(prompt=_PROMPT, context=context)

    print(f"\nProvider  : {response.provider_id}")
    print(f"Modell    : {response.model_name}")
    print(f"Tokens    : {response.input_tokens} in / {response.output_tokens} out")
    print(f"\n--- KI-Antwort ---\n{response.response_text}")

    # 5. Assertions
    assert response.response_text, "Codex hat eine leere Antwort zurueckgegeben."
    assert len(response.response_text) > 50, "Antwort ist zu kurz."
    assert response.output_tokens > 0, "Keine Output-Tokens gezaehlt."

    # Stichprobe: Antwort sollte thematisch passen
    response_lower = response.response_text.lower()
    assert any(
        keyword in response_lower
        for keyword in ("wind", "flaeche", "fläche", "riemsloh", "melle", "anlage")
    ), "Antwort enthaelt keinen thematisch passenden Begriff."
