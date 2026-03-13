from __future__ import annotations

from pathlib import Path

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis


def test_enrich_documents_for_analysis_adds_structured_fields_from_local_file(tmp_path: Path) -> None:
    session_dir = tmp_path / "2026-01-15_Rat_902"
    document_dir = session_dir / "agenda" / "o1"
    document_dir.mkdir(parents=True, exist_ok=True)
    document_path = document_dir / "beschlussvorlage.txt"
    document_path.write_text(
        "\n".join(
            [
                "Beschlussvorschlag: Der Rat beschliesst die Umsetzung des Projekts.",
                "Begruendung: Die Massnahme ist fuer die Sicherstellung des Betriebs erforderlich.",
                "Finanzielle Auswirkungen: 25.000 EUR im Haushaltsjahr 2026.",
                "Zustaendigkeit: Rat der Stadt Melle.",
            ]
        ),
        encoding="utf-8",
    )

    documents = [
        {
            "agenda_item": "Oe 1",
            "title": "Beschlussvorlage Projekt",
            "document_type": "beschlussvorlage",
            "local_path": "agenda/o1/beschlussvorlage.txt",
            "session_path": str(session_dir),
            "content_type": "text/plain",
        }
    ]

    enriched = enrich_documents_for_analysis(documents)

    assert len(enriched) == 1
    entry = enriched[0]
    assert entry["extraction_status"] == "ok"
    assert entry["content_parser_status"] == "ok"
    assert "25.000 EUR" in entry["structured_fields"]["finanzbezug"]


def test_build_analysis_markdown_includes_structured_document_context() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        mode="summary",
        scope="tops",
        selected_tops=["Oe 1"],
        documents=[
            {
                "agenda_item": "Oe 1",
                "title": "Beschlussvorlage Projekt",
                "document_type": "beschlussvorlage",
                "extraction_status": "ok",
                "content_parser_quality": "high",
                "url": "https://example.org/vorlage",
                "resolved_local_path": "data/raw/2026/01/test.txt",
                "structured_fields": {
                    "beschlusstext": "Der Rat beschliesst die Umsetzung des Projekts.",
                    "finanzbezug": "25.000 EUR im Haushaltsjahr 2026.",
                },
            }
        ],
        prompt="Bitte Kernthemen und Kosten benennen.",
    )

    assert "## Dokumentkontext" in markdown
    assert "beschlussvorlage" in markdown
    assert "25.000 EUR" in markdown
    assert "Bitte Kernthemen und Kosten benennen." in markdown
    assert "## Quellen" in markdown


def test_build_analysis_markdown_applies_mode_specific_fields() -> None:
    documents = [
        {
            "agenda_item": "Oe 1",
            "title": "Vorlage",
            "document_type": "vorlage",
            "extraction_status": "ok",
            "content_parser_quality": "high",
            "structured_fields": {
                "beschlusstext": "Beschluss A",
                "entscheidung": "angenommen",
                "finanzbezug": "100 EUR",
                "zustaendigkeit": "Rat",
            },
        }
    ]
    decision_md = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        mode="decision_brief",
        scope="session",
        selected_tops=[],
        documents=documents,
        prompt="",
        uncertainty_flags=["parser_low"],
        plausibility_flags=["conflicting_decision_signals"],
        bias_metrics={"source_balance": "single_document", "evidence_balance": "moderate", "document_type_diversity": 1},
    )
    financial_md = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        mode="financial_impact",
        scope="session",
        selected_tops=[],
        documents=documents,
        prompt="",
    )

    assert "entscheidung: angenommen" in decision_md
    assert "zustaendigkeit: Rat" in decision_md
    assert "Unsicherheit: parser_low" in decision_md
    assert "Plausibilitaet: conflicting_decision_signals" in decision_md
    assert "Bias-Metriken: source_balance=single_document" in decision_md
    assert "finanzbezug: 100 EUR" in financial_md


def test_build_analysis_markdown_groups_documents_by_top_and_marks_inconsistencies() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        mode="topic_classifier",
        scope="tops",
        selected_tops=["Oe 1", "Oe 2"],
        documents=[
            {
                "agenda_item": "Oe 1",
                "agenda_title": "Haushalt 2026",
                "title": "Vorlage Haushalt",
                "document_type": "vorlage",
                "extraction_status": "ok",
                "content_parser_quality": "high",
                "structured_fields": {"finanzbezug": "100 EUR", "beschlusstext": "Annahme"},
                "extracted_text": "Haushalt und Kosten fuer 2026.",
            },
            {
                "agenda_item": "Oe 1",
                "agenda_title": "Haushalt 2026",
                "title": "Protokoll Haushalt",
                "document_type": "protokoll",
                "extraction_status": "ok",
                "content_parser_quality": "high",
                "structured_fields": {"entscheidung": "vertagt", "finanzbezug": "150 EUR"},
                "extracted_text": "Finanzberatung im Ausschuss.",
            },
        ],
        prompt="",
    )

    assert "## TOP-Analyse" in markdown
    assert "### Oe 1 - Haushalt 2026" in markdown
    assert "Inkonsistenzen: abweichende Beschlusssignale, abweichende Finanzangaben" in markdown
    assert "Themenklassifikation: Finanzen" in markdown


def test_build_analysis_markdown_adds_session_summary_for_journalistic_brief() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat", "meeting_name": "Ratssitzung Januar"},
        mode="journalistic_brief",
        scope="session",
        selected_tops=[],
        documents=[
            {
                "agenda_item": "Oe 1",
                "agenda_title": "Haushalt 2026",
                "title": "Vorlage Haushalt",
                "document_type": "vorlage",
                "extraction_status": "ok",
                "content_parser_quality": "high",
                "structured_fields": {
                    "beschlusstext": "Annahme des Haushalts",
                    "finanzbezug": "100 EUR",
                    "zustaendigkeit": "Kaemmerei",
                },
                "extracted_text": "Haushalt, Kosten und Finanzierung.",
            },
            {
                "agenda_item": "Oe 2",
                "agenda_title": "Verkehrskonzept",
                "title": "Protokoll Verkehr",
                "document_type": "protokoll",
                "extraction_status": "ocr_needed",
                "content_parser_quality": "low",
                "structured_fields": {"entscheidung": "vertagt"},
                "extracted_text": "Verkehr und Strasse.",
            },
        ],
        prompt="",
    )

    assert "## Sitzungsanalyse" in markdown
    assert "Sitzung: Ratssitzung Januar" in markdown
    assert "Konfliktlinien:" in markdown
    assert "Offene Fragen:" in markdown
    assert "Priorisierte Folgeaufgaben:" in markdown


def test_build_analysis_markdown_adds_change_monitor_sections() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat", "meeting_name": "Ratssitzung Januar"},
        mode="change_monitor",
        scope="tops",
        selected_tops=["Oe 1"],
        documents=[
            {
                "agenda_item": "Oe 1",
                "agenda_title": "Projektbeschluss",
                "title": "Vorlage Projekt",
                "document_type": "vorlage",
                "extraction_status": "ok",
                "content_parser_quality": "high",
                "structured_fields": {"beschlusstext": "Annahme", "finanzbezug": "100 EUR"},
                "extracted_text": "Projekt und Kosten.",
            },
            {
                "agenda_item": "Oe 1",
                "agenda_title": "Projektbeschluss",
                "title": "Protokoll Projekt",
                "document_type": "protokoll",
                "extraction_status": "ok",
                "content_parser_quality": "high",
                "structured_fields": {"entscheidung": "vertagt", "finanzbezug": "150 EUR"},
                "extracted_text": "Projekt, Abstimmung und Kosten.",
            },
        ],
        prompt="",
    )

    assert "## Sitzungsanalyse" in markdown
    assert "Beobachtete Aenderungen:" in markdown
    assert "## TOP-Analyse" in markdown
    assert "Aenderungssignale: mehrere Dokumenttypen, veraenderter Beschlussstand, veraenderter Finanzbezug" in markdown


def test_enrich_documents_for_analysis_accepts_legacy_session_path(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2026" / "01" / "2026-01-15_Rat_902"
    document_dir = session_dir / "agenda" / "o1"
    document_dir.mkdir(parents=True, exist_ok=True)
    document_path = document_dir / "beschlussvorlage.txt"
    document_path.write_text(
        "Beschlussvorschlag: Der Rat beschliesst die Umsetzung.",
        encoding="utf-8",
    )

    documents = [
        {
            "agenda_item": "Oe 1",
            "title": "Beschlussvorlage Projekt",
            "document_type": "beschlussvorlage",
            "local_path": "agenda/o1/beschlussvorlage.txt",
            "session_path": str(tmp_path / "data" / "raw" / "2026" / "2026-01-15_Rat_902"),
            "content_type": "text/plain",
        }
    ]

    enriched = enrich_documents_for_analysis(documents)

    assert enriched[0]["resolved_local_path"] == str(document_path)
    assert enriched[0]["extraction_status"] in {"ok", "partial"}
