from __future__ import annotations

from datetime import date
from dataclasses import replace

from src.fetching.landkreis import LandkreisClient, LandkreisPublicationStore, LandkreisStorage
from src.fetching.landkreis.builder import build_landkreis_publications_db
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


def test_fetch_bekanntmachung_stores_document_metadata_without_downloading(tmp_path, monkeypatch):
    client = _client(tmp_path)
    publication = LandkreisPublication(
        source="bekanntmachungen",
        publication_id="pub-2",
        date=date(2026, 4, 15),
        title="Bekanntmachung Melle",
        detail_url="https://www.landkreis-osnabrueck.de/node/123",
        list_url="https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/bekanntmachungen",
    )

    class Response:
        text = """
        <main>
          <p>Bekanntmachung fuer Melle.</p>
          <a href="/system/files?file=bekanntmachung.pdf">PDF Bekanntmachung</a>
        </main>
        """

    monkeypatch.setattr(client, "_get", lambda url: Response())

    def fail_download(url):
        raise AssertionError("Bekanntmachungs-PDFs must not be downloaded")

    monkeypatch.setattr(client, "_download_document", fail_download)

    stored = client.fetch_publication(publication)

    assert stored.documents == [
        LandkreisDocument(
            title="PDF Bekanntmachung",
            url="https://www.landkreis-osnabrueck.de/system/files?file=bekanntmachung.pdf",
        )
    ]
    assert not (client.storage.publication_dir(publication) / "documents").exists()


def test_fetch_amtsblatt_reuses_existing_document_without_redownload(tmp_path, monkeypatch):
    client = _client(tmp_path)
    publication = LandkreisPublication(
        source="amtsblaetter",
        publication_id="pub-3",
        date=date(2026, 7, 15),
        title="Amtsblatt 13 / 2026",
        detail_url="https://www.landkreis-osnabrueck.de/node/700",
        list_url="https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/amtsblaetter",
    )
    document_url = "https://www.landkreis-osnabrueck.de/system/files?file=amtsblatt-13-2026.pdf"
    existing_path = client.storage.document_path(publication, document_url, 1)
    existing_path.parent.mkdir(parents=True)
    existing_path.write_bytes(b"existing")

    class Response:
        text = f"""
        <main>
          <a href="{document_url}">Amtsblatt 13 / 2026 PDF</a>
        </main>
        """

    monkeypatch.setattr(client, "_get", lambda url: Response())

    def fail_download(url):
        raise AssertionError("Existing Amtsblatt PDFs must not be downloaded again")

    monkeypatch.setattr(client, "_download_document", fail_download)

    stored = client.fetch_publication(publication, refresh_existing=True)

    assert stored.documents[0].local_path == client.storage.relative_path(existing_path)
    assert existing_path.read_bytes() == b"existing"


def test_crawl_amtsblaetter_skips_existing_manifests(tmp_path, monkeypatch):
    client = _client(tmp_path)
    publication = LandkreisPublication(
        source="amtsblaetter",
        publication_id="pub-5",
        date=date(2026, 7, 15),
        title="Amtsblatt 13 / 2026",
        detail_url="https://www.landkreis-osnabrueck.de/node/700",
        list_url="https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/amtsblaetter",
    )
    client.storage.write_manifest(publication)
    monkeypatch.setattr(client, "iter_publication_references", lambda source: iter([publication]))

    def fail_fetch(publication, *, refresh_existing=False):
        raise AssertionError("Existing Amtsblatt publications must be skipped")

    monkeypatch.setattr(client, "fetch_publication", fail_fetch)

    publications = client.crawl(source="amtsblaetter")

    assert publications == []


def test_build_landkreis_db_from_raw_manifests(tmp_path):
    storage = LandkreisStorage(tmp_path / "raw-landkreis")
    publication = LandkreisPublication(
        source="amtsblaetter",
        publication_id="pub-4",
        date=date(2026, 7, 15),
        title="Amtsblatt 13 / 2026",
        detail_url="https://www.landkreis-osnabrueck.de/node/700",
        list_url="https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/amtsblaetter",
        page_text="Amtsblatt mit Genehmigung in Melle.",
    )
    document_path = storage.publication_dir(publication) / "documents" / "001_amtsblatt.txt"
    document_path.parent.mkdir(parents=True)
    document_path.write_text("Genehmigung fuer Melle im Amtsblatt.", encoding="utf-8")
    stored = replace(
        publication,
        local_dir=storage.relative_path(document_path.parent.parent),
        documents=[
            LandkreisDocument(
                title="Amtsblatt Text",
                url="https://www.landkreis-osnabrueck.de/system/files?file=amtsblatt.txt",
                local_path=storage.relative_path(document_path),
                content_type="text/plain",
                content_length=document_path.stat().st_size,
            )
        ],
    )
    storage.write_manifest(stored)

    counts = build_landkreis_publications_db(
        data_root=storage.data_root,
        db_path=tmp_path / "landkreis.sqlite",
    )
    rows = Store(tmp_path / "landkreis.sqlite").search("Melle Genehmigung")

    assert counts == (1, 1, 1)
    assert [row["publication_id"] for row in rows] == ["pub-4"]
