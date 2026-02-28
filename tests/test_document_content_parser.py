from __future__ import annotations

from pathlib import Path

from src.parsing.document_content import parse_document_content


def test_parse_beschlussvorlage_extracts_core_sections() -> None:
    text = """
    Beschlussvorschlag: Der Rat beschliesst die Freigabe der Mittel fuer die Sanierung.
    Begruendung: Die bestehende Infrastruktur ist schadhaft und muss ersetzt werden.
    Finanzielle Auswirkungen: Im Haushalt 2026 sind 120.000 EUR eingeplant.
    Zustaendigkeit: Ausschuss fuer Finanzen, Rat der Stadt Melle.
    """

    result = parse_document_content(
        document_type="beschlussvorlage",
        text=text,
        title="Beschlussvorlage Sanierung",
    )

    assert result.content_parser_status == "ok"
    assert result.content_parser_quality == "high"
    assert result.structured_fields["titel"] == "Beschlussvorlage Sanierung"
    assert "Freigabe der Mittel" in result.structured_fields["beschlusstext"]
    assert "Infrastruktur" in result.structured_fields["begruendung"]
    assert "120.000 EUR" in result.structured_fields["finanzbezug"]
    assert "Finanzen" in result.structured_fields["zustaendigkeit"]


def test_parse_vorlage_returns_low_quality_when_only_one_section_matches() -> None:
    text = """
    Begruendung: Fuer das Projekt besteht dringender Handlungsbedarf wegen erheblicher Schaeden.
    Weitere Hinweise: Die Umsetzung ist fuer das dritte Quartal vorgesehen.
    """

    result = parse_document_content(
        document_type="vorlage",
        text=text,
        title="Vorlage Projektstart",
    )

    assert result.content_parser_status == "ok"
    assert result.content_parser_quality == "low"
    assert result.structured_fields["titel"] == "Vorlage Projektstart"
    assert "Handlungsbedarf" in result.structured_fields["begruendung"]
    assert "beschlusstext" not in result.structured_fields


def test_parse_protokoll_extracts_decision_and_reasoning() -> None:
    text = """
    Beratung: Im Ausschuss wurde ueber mehrere Varianten diskutiert.
    Beschluss: Der Rat stimmt dem Verwaltungsvorschlag zu.
    Abstimmung: einstimmig angenommen.
    """

    result = parse_document_content(
        document_type="protokoll",
        text=text,
        title="Auszug Niederschrift",
    )

    assert result.content_parser_status == "ok"
    assert result.content_parser_quality in {"medium", "high"}
    assert "diskutiert" in result.structured_fields["begruendung"]
    assert "Verwaltungsvorschlag" in result.structured_fields["beschlusstext"]
    assert "einstimmig angenommen" in result.structured_fields["entscheidung"]


def test_parse_document_content_rejects_unsupported_document_type() -> None:
    result = parse_document_content(
        document_type="bekanntmachung",
        text="Einladung zur Sitzung am Montag.",
    )

    assert result.content_parser_status == "unsupported_document_type"
    assert result.content_parser_quality == "failed"
    assert result.structured_fields == {}


def test_parse_document_content_from_fixture_files() -> None:
    fixture_root = Path(__file__).parent / "fixtures"
    beschluss_text = (fixture_root / "document_beschlussvorlage_sessionnet.txt").read_text(encoding="utf-8")
    protokoll_text = (fixture_root / "document_protokoll_sessionnet.txt").read_text(encoding="utf-8")

    beschluss_result = parse_document_content(
        document_type="beschlussvorlage",
        text=beschluss_text,
        title="Ausbau Ganztagsbetreuung",
    )
    protokoll_result = parse_document_content(
        document_type="protokoll",
        text=protokoll_text,
        title="Niederschrift TOP Oe 7",
    )

    assert beschluss_result.content_parser_quality == "high"
    assert "350.000 EUR" in beschluss_result.structured_fields["finanzbezug"]
    assert "Bildung" in beschluss_result.structured_fields["zustaendigkeit"]

    assert protokoll_result.content_parser_status == "ok"
    assert "Verwaltungsvorschlag" in protokoll_result.structured_fields["beschlusstext"]
    assert "einstimmig angenommen" in protokoll_result.structured_fields["entscheidung"]
