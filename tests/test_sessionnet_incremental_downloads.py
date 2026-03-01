from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.models import DocumentReference, SessionDetail, SessionReference
from src.fetching.sessionnet_client import SessionNetClient


def _reference() -> SessionReference:
    return SessionReference(
        committee="Rat",
        meeting_name="Ratssitzung",
        session_id="5555",
        date=date(2026, 3, 10),
        start_time="19:00 Uhr",
        detail_url="https://session.melle.info/bi/si0057.asp?__ksinr=5555",
    )


def _detail(url: str) -> SessionDetail:
    return SessionDetail(
        reference=_reference(),
        agenda_items=[],
        session_documents=[DocumentReference(title="Vorlage", url=url, category="VO")],
        retrieved_at=datetime(2026, 3, 10, 12, 0, 0),
        raw_html="",
    )


def test_download_documents_skips_unchanged_remote_file(tmp_path, monkeypatch) -> None:
    url = "https://example.org/documents/vorlage"
    detail = _detail(url)

    client = SessionNetClient(storage_root=tmp_path)
    original_get = SessionNetClient._get

    class _GetResponse:
        def __init__(self, content: bytes):
            self.content = content
            self.headers = {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=vorlage.pdf",
                "Content-Length": str(len(content)),
                "ETag": '"etag-same"',
                "Last-Modified": "Mon, 10 Mar 2026 12:00:00 GMT",
            }

    monkeypatch.setattr(
        SessionNetClient,
        "_get",
        lambda self, requested_url, params=None: _GetResponse(b"version-1"),
        raising=False,
    )
    client.download_documents(detail)

    reused_client = SessionNetClient(storage_root=tmp_path)
    request_calls: list[str] = []
    monkeypatch.setattr(SessionNetClient, "_get", original_get, raising=False)

    class _HeadResponse:
        headers = {
            "ETag": '"etag-same"',
            "Last-Modified": "Mon, 10 Mar 2026 12:00:00 GMT",
            "Content-Length": str(len(b"version-1")),
        }

    def fake_request(self, method, path, params=None):
        request_calls.append(method)
        if method == "HEAD":
            return _HeadResponse()
        raise AssertionError("GET should not be called for unchanged documents")

    monkeypatch.setattr(SessionNetClient, "_request", fake_request, raising=False)

    reused_client.download_documents(detail)

    assert request_calls == ["HEAD"]
    manifest = json.loads((reused_client._build_session_directory(_reference()) / "manifest.json").read_text("utf-8"))
    assert manifest["documents"][0]["etag"] == '"etag-same"'


def test_download_documents_redownloads_changed_remote_file(tmp_path, monkeypatch) -> None:
    url = "https://example.org/documents/vorlage"
    detail = _detail(url)

    client = SessionNetClient(storage_root=tmp_path)
    original_get = SessionNetClient._get

    class _GetResponse:
        def __init__(self, content: bytes, *, etag: str):
            self.content = content
            self.headers = {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=vorlage.pdf",
                "Content-Length": str(len(content)),
                "ETag": etag,
                "Last-Modified": "Mon, 10 Mar 2026 12:00:00 GMT",
            }

    monkeypatch.setattr(
        SessionNetClient,
        "_get",
        lambda self, requested_url, params=None: _GetResponse(b"version-1", etag='"etag-old"'),
        raising=False,
    )
    client.download_documents(detail)

    updated_client = SessionNetClient(storage_root=tmp_path)
    get_calls = 0
    monkeypatch.setattr(SessionNetClient, "_get", original_get, raising=False)

    class _HeadResponse:
        headers = {
            "ETag": '"etag-new"',
            "Last-Modified": "Tue, 11 Mar 2026 12:00:00 GMT",
            "Content-Length": str(len(b"version-2")),
        }

    def fake_request(self, method, path, params=None):
        nonlocal get_calls
        if method == "HEAD":
            return _HeadResponse()
        if method == "GET":
            get_calls += 1
            return _GetResponse(b"version-2", etag='"etag-new"')
        raise AssertionError(f"Unexpected method {method}")

    monkeypatch.setattr(SessionNetClient, "_request", fake_request, raising=False)

    updated_client.download_documents(detail)

    assert get_calls == 1
    session_dir = updated_client._build_session_directory(_reference())
    manifest = json.loads((session_dir / "manifest.json").read_text("utf-8"))
    assert manifest["documents"][0]["etag"] == '"etag-new"'
    relative_path = manifest["documents"][0]["path"]
    assert (session_dir / relative_path).read_bytes() == b"version-2"
