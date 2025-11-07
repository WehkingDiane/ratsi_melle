from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.models import DocumentReference
from src.fetching.sessionnet_client import SessionNetClient


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
