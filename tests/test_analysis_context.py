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


def test_build_analysis_markdown_includes_title_based_document_context() -> None:
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

    assert "## Dokumenttitel" in markdown
    assert "beschlussvorlage" in markdown
    assert "beleg_excerpt:" not in markdown
    assert "Bitte Kernthemen und Kosten benennen." in markdown
    assert "## Quellen" in markdown


def test_build_analysis_markdown_shows_title_based_quality_signals() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        mode="summary",
        scope="session",
        selected_tops=[],
        documents=[
            {
                "agenda_item": "Oe 1",
                "title": "Vorlage",
                "document_type": "vorlage",
            }
        ],
        prompt="",
        uncertainty_flags=["parser_low"],
        plausibility_flags=["title_only_local_analysis"],
        bias_metrics={"source_balance": "single_document", "evidence_balance": "moderate", "document_type_diversity": 1},
    )

    assert "Unsicherheit: parser_low" in markdown
    assert "Plausibilitaet: title_only_local_analysis" in markdown
    assert "Bias-Metriken: source_balance=single_document" in markdown


def test_build_analysis_markdown_groups_documents_by_top_and_classifies_topics() -> None:
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
    assert "Themenklassifikation: Finanzen" in markdown


def test_build_analysis_markdown_adds_session_overview_for_summary() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat", "meeting_name": "Ratssitzung Januar"},
        mode="summary",
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

    assert "## Sitzungsueberblick" in markdown
    assert "Sitzung: Ratssitzung Januar" in markdown
    assert "Hinweis: lokale Analyse nutzt nur TOP- und Dokumenttitel" in markdown
    assert "Dominante Titelthemen:" in markdown


def test_build_analysis_markdown_omits_excerpts_for_title_based_output() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        mode="summary",
        scope="session",
        selected_tops=[],
        documents=[
            {
                "agenda_item": "Oe 1",
                "title": "Unlesbares Dokument",
                "document_type": "sonstiges",
                "extraction_status": "ok",
                "content_parser_quality": "failed",
                "extracted_text": "qzxv ## @@ %% 1234 qzxv @@ ## %% qzxv ### @@ %% 1234 qzxv @@ ## %% qzxv",
                "structured_fields": {},
            }
        ],
        prompt="",
    )

    assert "beleg_excerpt:" not in markdown
    assert "qzxv ## @@" not in markdown


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
