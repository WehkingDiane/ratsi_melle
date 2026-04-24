from __future__ import annotations

from pathlib import Path

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis


def test_enrich_documents_for_analysis_adds_source_path_metadata(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2026" / "01" / "2026-01-15_Rat_902"
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
    assert entry["source_file_available"] is True
    assert entry["resolved_local_path"] == str(document_path)


def test_build_analysis_markdown_includes_source_list() -> None:
    markdown = build_analysis_markdown(
        session={"date": "2026-01-15", "committee": "Rat"},
        scope="tops",
        selected_tops=["Oe 1"],
        documents=[
            {
                "agenda_item": "Oe 1",
                "title": "Beschlussvorlage Projekt",
                "document_type": "beschlussvorlage",
                "resolved_local_path": "/tmp/beschlussvorlage.txt",
                "source_file_available": True,
                "url": "https://example.org/beschlussvorlage",
            }
        ],
        prompt="Bitte Kernthemen und Kosten benennen.",
    )

    assert "## Quellen im Scope" in markdown
    assert "beschlussvorlage" in markdown
    assert "/tmp/beschlussvorlage.txt" in markdown
    assert "Bitte Kernthemen und Kosten benennen." in markdown


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
    assert enriched[0]["source_file_available"] is True


def test_enrich_documents_for_analysis_marks_missing_resolved_file_as_unavailable(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2026" / "01" / "2026-01-15_Rat_902"
    session_dir.mkdir(parents=True, exist_ok=True)

    documents = [
        {
            "agenda_item": "Oe 1",
            "title": "Beschlussvorlage Projekt",
            "document_type": "beschlussvorlage",
            "local_path": "agenda/o1/fehlend.txt",
            "session_path": str(session_dir),
            "content_type": "text/plain",
        }
    ]

    enriched = enrich_documents_for_analysis(documents)

    assert enriched[0]["resolved_local_path"] is not None
    assert enriched[0]["source_file_available"] is False
