"""Completed sessions reuse local files while still discovering missing documents."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from hashlib import sha1
import json

import pytest

from src.fetching.models import AgendaItem, DocumentReference, SessionDetail, SessionReference
from src.fetching.sessionnet_client import SessionNetClient


pytestmark = pytest.mark.integration


def _detail(*, category="PR", days_ago=1):
    reference = SessionReference(
        committee="Rat", meeting_name="Rat", session_id="1234",
        date=date.today() - timedelta(days=days_ago), start_time=None,
        detail_url="https://example.org/si0057.asp?__ksinr=1234",
    )
    document = DocumentReference("Protokoll öffentlich", "https://example.org/getfile.asp?id=123&type=do", category)
    return SessionDetail(reference, [], datetime.now(), "", [document])


def _seed(client, detail, *, content=b"%PDF-existing", record=True):
    directory = client._build_session_directory(detail.reference)
    document = detail.session_documents[0]
    path = directory / client._normalise_filename(document, index=1, extension=".pdf")
    path.write_bytes(content)
    entry = client._build_manifest_entry(
        document=document, path=path, headers={"ETag": '"original"', "Content-Type": "application/pdf"},
        sha1=sha1(content).hexdigest(), target_dir=directory,
    )
    if record:
        client._write_manifest(directory, detail, [entry])
    return path


class _Response:
    headers = {"Content-Type": "application/pdf", "ETag": '"new"'}

    def iter_content(self, chunk_size):
        yield b"%PDF-new"

    def close(self):
        pass


@pytest.mark.parametrize("category", ["PR", "Pnö", "BÜ", "Bnö", None])
def test_completed_session_reuses_file_without_head_or_get(tmp_path, monkeypatch, category):
    detail = _detail(category=category)
    client = SessionNetClient(storage_root=tmp_path)
    path = _seed(client, detail)
    modified = path.stat().st_mtime_ns

    def no_network(*args, **kwargs):
        pytest.fail("Existing completed-session file must not cause any network request")

    monkeypatch.setattr(SessionNetClient, "_request", no_network)
    client.download_documents(detail)

    assert path.read_bytes() == b"%PDF-existing"
    assert path.stat().st_mtime_ns == modified
    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents"][0]["etag"] == '"original"'


def test_completed_session_recovers_file_without_manifest_and_ignores_renamed_title(tmp_path, monkeypatch):
    detail = _detail()
    client = SessionNetClient(storage_root=tmp_path)
    path = _seed(client, detail, record=False)
    detail.session_documents[0].title = "Protokoll öffentlich (1)"
    monkeypatch.setattr(SessionNetClient, "_request", lambda *a, **kw: pytest.fail("Unexpected request"))

    client.download_documents(detail)

    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents"][0]["title"] == "Protokoll öffentlich (1)"
    assert manifest["documents"][0]["path"] == path.name


def test_completed_session_reuses_url_after_top_and_title_change(tmp_path, monkeypatch):
    detail = _detail()
    client = SessionNetClient(storage_root=tmp_path)
    path = _seed(client, detail)
    old_document = detail.session_documents[0]
    detail.session_documents = [DocumentReference("Beschlussübersicht", "https://example.org/new", "BÜ")]
    detail.agenda_items = [AgendaItem("Ö 9", "Anderer TOP", documents=[replace(old_document, title="Neuer Titel", on_agenda_item="Ö 9")])]
    calls = []

    def request(self, method, url, **kwargs):
        calls.append((method, url))
        return _Response()

    monkeypatch.setattr(SessionNetClient, "_request", request)
    client.download_documents(detail)

    assert calls == [("GET", "https://example.org/new")]
    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents"][1]["path"] == path.name
    assert manifest["documents"][1]["agenda_item"] == "Ö 9"


@pytest.mark.parametrize("days_ago,category", [(0, "PR"), (-1, "PR"), (1, "VO")])
def test_unfinished_sessions_keep_remote_checks(tmp_path, monkeypatch, days_ago, category):
    detail = _detail(category=category, days_ago=days_ago)
    client = SessionNetClient(storage_root=tmp_path)
    _seed(client, detail)
    calls = []

    def request(self, method, url, **kwargs):
        calls.append(method)
        return _Response()

    monkeypatch.setattr(SessionNetClient, "_request", request)
    client.download_documents(detail)

    assert calls == ["HEAD", "GET"]


def test_single_top_decision_does_not_complete_session(tmp_path):
    detail = _detail(category="VO")
    detail.agenda_items = [AgendaItem("Ö 1", "Genehmigung des Protokolls", status="beschlossen")]
    assert not SessionNetClient._has_published_results(detail)
    detail.session_documents = [DocumentReference("Genehmigung des Protokolls", "https://example.org/1")]
    assert not SessionNetClient._has_published_results(detail)
    detail.session_documents = [DocumentReference("Protokollvorlage", "https://example.org/1")]
    assert not SessionNetClient._has_published_results(detail)
    detail.session_documents = []
    detail.agenda_items[0].documents = [DocumentReference("Protokoll", "https://example.org/1", "PR", "Ö 1")]
    assert not SessionNetClient._has_published_results(detail)


@pytest.mark.parametrize("state", ["missing", "empty", "truncated", "new_url", "force"])
def test_completed_session_downloads_missing_invalid_new_or_forced_documents(tmp_path, monkeypatch, state):
    detail = _detail()
    client = SessionNetClient(storage_root=tmp_path)
    path = _seed(client, detail)
    if state == "missing":
        path.unlink()
    elif state == "empty":
        path.write_bytes(b"")
    elif state == "truncated":
        path.write_bytes(b"%PDF")
    elif state == "new_url":
        detail.session_documents[0].url += "4"
    elif state == "force":
        client._document_cache[detail.session_documents[0].url] = (b"stale-cache", {})
    calls = []

    def request(self, method, url, **kwargs):
        calls.append(method)
        return _Response()

    monkeypatch.setattr(SessionNetClient, "_request", request)
    client.download_documents(detail, force_download=state == "force")

    assert calls == ["GET"]
    directory = client._build_session_directory(detail.reference)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert (directory / manifest["documents"][0]["path"]).read_bytes() == b"%PDF-new"
    if state == "new_url":
        assert path.read_bytes() == b"%PDF-existing"
