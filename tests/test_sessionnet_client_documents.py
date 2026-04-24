from pathlib import Path
import sys
from unittest.mock import Mock

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.models import DocumentReference
from src.fetching.sessionnet_client import FetchingError, SessionNetClient


def test_detect_extension_uses_content_disposition_filename(tmp_path):
    client = SessionNetClient(storage_root=tmp_path)
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="protokoll.pdf"',
    }
    document = DocumentReference(title="Protokoll", url="https://session.melle.info/bi/getfile.asp?id=123")

    assert client._detect_extension(document, headers) == ".pdf"


def test_detect_extension_supports_filename_star(tmp_path):
    client = SessionNetClient(storage_root=tmp_path)
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": "attachment; filename*=UTF-8''Haushalt%20Plan.pdf",
    }
    document = DocumentReference(title="Haushalt", url="https://session.melle.info/bi/vo0050.asp?__kvonr=456")

    assert client._detect_extension(document, headers) == ".pdf"


def test_resolve_existing_document_path_rejects_manifest_traversal(tmp_path: Path) -> None:
    client = SessionNetClient(storage_root=tmp_path)
    target_dir = tmp_path / "2026" / "03" / "2026-03-10_Rat_7001"
    target_dir.mkdir(parents=True, exist_ok=True)
    outside_file = tmp_path / "outside.pdf"
    outside_file.write_bytes(b"payload")

    resolved = client._resolve_existing_document_path(
        target_dir,
        {"path": "../../../outside.pdf"},
    )

    assert resolved is None


def test_fetch_document_payload_rejects_oversized_download(tmp_path: Path, monkeypatch) -> None:
    client = SessionNetClient(storage_root=tmp_path, max_document_bytes=4)
    response = Mock()
    response.headers.copy.return_value = {"Content-Length": "10"}
    response.close = Mock()
    monkeypatch.setattr(
        SessionNetClient,
        "_request",
        lambda self, method, path, params=None, *, stream=False: response,
    )
    document = DocumentReference(title="Gross", url="https://session.melle.info/bi/getfile.asp?id=9")

    try:
        client._fetch_document_payload(document)
    except FetchingError as exc:
        assert "size limit" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected oversized download to be rejected")

    response.close.assert_called_once()


def test_fetch_document_payload_wraps_stream_errors(tmp_path: Path, monkeypatch) -> None:
    client = SessionNetClient(storage_root=tmp_path, max_document_bytes=1024)
    response = Mock()
    response.headers.copy.return_value = {}
    response.close = Mock()
    response.iter_content.side_effect = requests.RequestException("stream boom")
    monkeypatch.setattr(
        SessionNetClient,
        "_request",
        lambda self, method, path, params=None, *, stream=False: response,
    )
    document = DocumentReference(title="Fehler", url="https://session.melle.info/bi/getfile.asp?id=10")

    try:
        client._fetch_document_payload(document)
    except FetchingError as exc:
        assert "stream boom" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected stream error to be wrapped as FetchingError")

    response.close.assert_called_once()
