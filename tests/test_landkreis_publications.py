from __future__ import annotations

from datetime import date

from src.fetching.landkreis import LandkreisClient, LandkreisPublicationStore, LandkreisStorage
from src.fetching.landkreis.database import LandkreisPublicationStore as Store
from src.fetching.landkreis.models import LandkreisDocument, LandkreisPublication


def _client(tmp_path):
    return LandkreisClient(
        storage=LandkreisStorage(tmp_path / "raw-landkreis"),
        store=LandkreisPublicationStore(tmp_path / "landkreis.sqlite"),
        min_request_interval=0,
    )


def test_parse_bekanntmachungen_list_extracts_dates_and_links(tmp_path):
    html = """
    <main>
      <h1>Öffentliche / Ortsübliche Bekanntmachungen</h1>
      <div class="views-row">
        <span>15.04.2026</span>
        <a href="/node/123">Bestellung eines Bezirksschornsteinfeger für Melle IV</a>
      </div>
      <div class="views-row">
        <span>28.08.2025</span>
        <a href="/node/456">Vorprüfung der Umweltverträglichkeit: Radweg zwischen Melle und Wellingholzhausen</a>
      </div>
      <nav><a href="?page=2">Page 2</a></nav>
    </main>
    """

    entries = _client(tmp_path).parse_list(
        "bekanntmachungen",
        html,
        "https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/bekanntmachungen",
    )

    assert [entry.date for entry in entries] == [date(2026, 4, 15), date(2025, 8, 28)]
    assert entries[0].source == "bekanntmachungen"
    assert entries[0].title == "Bestellung eines Bezirksschornsteinfeger für Melle IV"
    assert entries[0].detail_url == "https://www.landkreis-osnabrueck.de/node/123"


def test_parse_amtsblaetter_list_extracts_only_amtsblatt_entries(tmp_path):
    html = """
    <main>
      <h1>Amtsblatt</h1>
      <h6>Amtsblatt 2026</h6>
      <div><span>15.07.2026</span><a href="/node/700">Amtsblatt 13 / 2026</a></div>
      <div><span>30.06.2026</span><a href="/node/701">Amtsblatt 12 / 2026</a></div>
      <a href="/node/999">Veröffentlichungstermine Amtsblatt 2026</a>
    </main>
    """

    entries = _client(tmp_path).parse_list(
        "amtsblaetter",
        html,
        "https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/amtsblaetter",
    )

    assert [entry.title for entry in entries] == ["Amtsblatt 13 / 2026", "Amtsblatt 12 / 2026"]
    assert [entry.date for entry in entries] == [date(2026, 7, 15), date(2026, 6, 30)]


def test_storage_can_use_external_root_and_keeps_relative_paths(tmp_path):
    storage = LandkreisStorage(tmp_path / "external" / "landkreis")
    publication = LandkreisPublication(
        source="bekanntmachungen",
        publication_id="abc",
        date=date(2026, 4, 15),
        title="Bekanntmachung Melle",
        detail_url="https://www.landkreis-osnabrueck.de/node/123",
        list_url="https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/bekanntmachungen",
    )

    html_path = storage.write_publication_html(publication, "<html></html>")
    relative = storage.relative_path(html_path)

    assert not relative.startswith("/")
    assert storage.resolve_relative_path(relative) == html_path.resolve()
    assert "bekanntmachungen/2026/2026-04-15_bekanntmachung-melle/detail.html" in relative


def test_store_search_uses_separated_database_and_extracted_text(tmp_path):
    store = Store(tmp_path / "landkreis.sqlite")
    publication = LandkreisPublication(
        source="bekanntmachungen",
        publication_id="pub-1",
        date=date(2026, 4, 15),
        title="Bekanntmachung Melle",
        detail_url="https://www.landkreis-osnabrueck.de/node/123",
        list_url="https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/bekanntmachungen",
        page_text="Hinweis zu einer Genehmigung in Melle.",
        documents=[
            LandkreisDocument(
                title="anlage.pdf",
                url="https://www.landkreis-osnabrueck.de/system/files?file=anlage.pdf",
                local_path="bekanntmachungen/2026/example/documents/001_anlage.pdf",
            )
        ],
    )

    store.upsert_publication(publication)
    document_id = store.document_rows()[0]["id"]
    store.upsert_extraction(
        document_id,
        {
            "extraction_status": "ok",
            "parsing_quality": "high",
            "extracted_text": "Immissionsschutzrechtliche Genehmigung fuer eine Anlage in Melle.",
            "extracted_char_count": 72,
            "page_count": 1,
            "extraction_error": None,
            "ocr_needed": False,
            "extraction_pipeline_version": "test",
            "extracted_at": "2026-07-17T00:00:00Z",
        },
    )

    rows = store.search("Melle Genehmigung")

    assert len(rows) == 1
    assert rows[0]["publication_id"] == "pub-1"
