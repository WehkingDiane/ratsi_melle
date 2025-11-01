from datetime import date
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.sessionnet_client import SessionNetClient


def test_parse_month_page_extracts_events(tmp_path):
    html = Path("tests/fixtures/si0040_oct2025.html").read_text(encoding="utf-8")
    client = SessionNetClient(storage_root=tmp_path)

    sessions = client._parse_overview(html, year=2025, month=10)

    assert [s.meeting_name for s in sessions] == [
        "Sitzung Ortsrat Oldendorf",
        "Sitzung Finanzen und Beteiligungen",
        "Stadtrat Melle",
    ]

    first = sessions[0]
    assert first.committee == "Ortsrat Oldendorf"
    assert first.session_id == "6773"
    assert first.date == date(2025, 10, 4)
    assert first.start_time == "19:00 Uhr"
    assert first.location == "Rathaus Oldendorf"
    assert first.detail_url == "https://session.melle.info/bi/si0057.asp?__ksinr=6773"

    second = sessions[1]
    assert second.committee == "Ausschuss für Finanzen und Beteiligungen"
    assert second.date == date(2025, 10, 12)
    assert second.location == "Rathaus, Ratssaal"

    third = sessions[2]
    assert third.committee == "Stadtrat Melle"
    assert third.date == date(2025, 10, 23)
    assert third.start_time == "18:00 Uhr"
    assert third.location == "Stadthalle Melle"
