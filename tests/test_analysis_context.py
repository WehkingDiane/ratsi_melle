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
    assert "finanzbezug: 100 EUR" in financial_md


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
