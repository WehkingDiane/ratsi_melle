from datetime import date, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.models import AgendaItem, DocumentReference, SessionDetail, SessionReference
from src.fetching.sessionnet_client import SessionNetClient


def _sample_reference() -> SessionReference:
    return SessionReference(
        committee="Rat",
        meeting_name="Ratssitzung",
        session_id="1234",
        date=date(2025, 10, 8),
        start_time="17:00 Uhr",
        detail_url="https://session.melle.info/bi/si0057.asp?__ksinr=1234",
    )


def test_parse_session_detail_collects_documents(tmp_path):
    html = Path("tests/fixtures/si0057_sample.html").read_text(encoding="utf-8")
    client = SessionNetClient(storage_root=tmp_path)

    detail = client._parse_session_detail(_sample_reference(), html)

    assert [doc.title for doc in detail.session_documents] == [
        "Amtliche Bekanntmachung",
        "Protokoll öffentlich",
    ]
    assert detail.session_documents[0].category == "BM"
    assert detail.session_documents[1].category == "PR"

    assert len(detail.agenda_items) == 3
    first_item = detail.agenda_items[0]
    assert first_item.number == "Ö 1"
    assert first_item.title == "Genehmigung des Protokolls"
    assert first_item.reporter == "Ratsvorsitzender Boßmann"
    assert [doc.title for doc in first_item.documents] == ["Vorlage Protokoll"]
    assert first_item.documents[0].on_agenda_item == "Ö 1"

    second_item = detail.agenda_items[1]
    assert second_item.title == "Haushalt 2025"
    assert second_item.reporter == "Fachbereich Finanzen"
    assert [doc.title for doc in second_item.documents] == ["Entwurf", "Anlage"]


def test_download_documents_writes_manifest(tmp_path, monkeypatch):
    reference = _sample_reference()
    detail = SessionDetail(
        reference=reference,
        agenda_items=[
            AgendaItem(
                number="Ö 1",
                title="Genehmigung des Protokolls vom 25.06.2025 - Berichterstatter Ratsvorsitzender Boßmann",
                status="beschlossen",
                reporter="Ratsvorsitzender Boßmann",
                documents=[
                    DocumentReference(
                        title="Vorlage",
                        url="https://example.org/documents/vorlage",
                        on_agenda_item="Ö 1",
                    )
                ],
            ),
            AgendaItem(number="Ö 2", title="Haushalt 2026", status=None, documents=[]),
        ],
        session_documents=[
            DocumentReference(title="Protokoll", url="https://example.org/documents/protokoll", category="PR")
        ],
        retrieved_at=datetime(2025, 10, 1, 12, 0, 0),
        raw_html="",
    )
    client = SessionNetClient(storage_root=tmp_path)

    class _Response:
        def __init__(self, body: bytes, *, disposition: str):
            self.content = body
            self.headers = {
                "Content-Type": "application/pdf",
                "Content-Disposition": disposition,
                "Content-Length": str(len(body)),
            }

    responses = {
        "https://example.org/documents/vorlage": _Response(b"agenda", disposition="attachment; filename=vorlage.pdf"),
        "https://example.org/documents/protokoll": _Response(
            b"session", disposition="attachment; filename=protokoll.pdf"
        ),
    }

    def fake_get(self, url, params=None):
        return responses[url]

    monkeypatch.setattr(SessionNetClient, "_get", fake_get, raising=False)

    client.download_documents(detail)

    session_dir = client._build_session_directory(reference)
    manifest_path = session_dir / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert {entry["title"] for entry in manifest["documents"]} == {"Vorlage", "Protokoll"}
    paths = [entry["path"] for entry in manifest["documents"]]
    assert any(path.startswith("session-documents/") for path in paths)
    assert any(path.startswith("agenda/") for path in paths)
    for entry in manifest["documents"]:
        assert entry["content_type"] == "application/pdf"
        assert entry["content_length"] > 0
        assert entry["content_disposition"].startswith("attachment; filename=")

    agenda_dir = session_dir / "agenda"
    assert agenda_dir.exists()
    assert list(agenda_dir.rglob("*.pdf"))
    agenda_subdirs = [path.name for path in agenda_dir.iterdir() if path.is_dir()]
    assert "Ö-1-Genehmigung-des-Protokolls-vom-25-06-2025" in agenda_subdirs
    assert all("Berichterstatter" not in name for name in agenda_subdirs)

    summary_path = session_dir / "agenda_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["agenda_items"][0]["reporter"] == "Ratsvorsitzender Boßmann"
    assert summary["agenda_items"][0]["decision"] == "accepted"
    assert summary["agenda_items"][1]["decision"] is None
    assert summary["agenda_items"][1]["documents_present"] is False


def test_download_documents_reuses_cache(tmp_path, monkeypatch):
    reference = _sample_reference()
    shared_url = "https://example.org/documents/shared"
    detail = SessionDetail(
        reference=reference,
        agenda_items=[
            AgendaItem(
                number="Ö 1",
                title="TOP 1",
                documents=[DocumentReference(title="Protokoll", url=shared_url, on_agenda_item="Ö 1")],
            ),
            AgendaItem(
                number="Ö 2",
                title="TOP 2",
                documents=[DocumentReference(title="Protokoll", url=shared_url, on_agenda_item="Ö 2")],
            ),
        ],
        session_documents=[DocumentReference(title="Protokoll", url=shared_url)],
        retrieved_at=datetime(2025, 10, 1, 12, 0, 0),
        raw_html="",
    )
    client = SessionNetClient(storage_root=tmp_path)

    call_count = 0

    class _Response:
        def __init__(self):
            self.content = b"shared"
            self.headers = {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=shared.pdf",
                "Content-Length": "6",
            }

    def fake_get(self, url, params=None):
        nonlocal call_count
        call_count += 1
        return _Response()

    monkeypatch.setattr(SessionNetClient, "_get", fake_get, raising=False)

    client.download_documents(detail)

    assert call_count == 1
    manifest = (client._build_session_directory(reference) / "manifest.json").read_text(encoding="utf-8")
    entries = json.loads(manifest)["documents"]
    assert len(entries) == 3
