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


def test_fetch_month_uses_extended_query_params(tmp_path, monkeypatch):
    html = Path("tests/fixtures/si0040_oct2025.html").read_text(encoding="utf-8")
    captured: dict = {}

    def fake_get(self, path, params=None):
        captured["path"] = path
        captured["params"] = params

        class _Response:
            text = html

        return _Response()

    client = SessionNetClient(storage_root=tmp_path)
    monkeypatch.setattr(SessionNetClient, "_get", fake_get, raising=False)

    client.fetch_month(year=2025, month=10)

    assert captured["path"] == "si0040.asp"
    assert captured["params"] == {
        "month": "10",
        "year": "2025",
        "__cjahr": "2025",
        "__cmonat": "10",
        "__cmandant": "2",
        "__canz": "1",
        "__cselect": "0",
    }


def test_parse_month_page_accepts_full_date_strings(tmp_path):
    html = """
    <table id="smc_page_si0040_contenttable1">
      <tr class="smc-row">
        <td class="siday">
          <div class="date">
            <span class="weekday">Mi, 04.03.2026</span>
          </div>
        </td>
        <td class="silink">
          <div class="smc-el-h">Ortsrat Bruchmuehlen</div>
          <a class="smc-link-normal" href="si0057.asp?__ksinr=7001">Ortsrat Bruchmuehlen</a>
          <ul class="list-inline smc-detail-list">
            <li>19:00 Uhr</li>
            <li>Gemeindehaus</li>
          </ul>
        </td>
      </tr>
      <tr class="smc-row">
        <td class="siday">
          <div class="date">
            <span class="weekday">Fr., 20.03.26</span>
          </div>
        </td>
        <td class="silink">
          <div class="smc-el-h">Ortsrat Melle-Mitte</div>
          <a class="smc-link-normal" href="si0057.asp?__ksinr=7002">Ortsrat Melle-Mitte</a>
          <ul class="list-inline smc-detail-list">
            <li>18:30 Uhr</li>
            <li>Rathaus</li>
          </ul>
        </td>
      </tr>
    </table>
    """
    client = SessionNetClient(storage_root=tmp_path)

    sessions = client._parse_overview(html, year=2026, month=3)

    assert [session.session_id for session in sessions] == ["7001", "7002"]
    assert [session.date for session in sessions] == [date(2026, 3, 4), date(2026, 3, 20)]


def test_parse_month_page_falls_back_to_date_in_link_metadata(tmp_path):
    html = """
    <table id="smc_page_si0040_contenttable1">
      <tr>
        <td class="smc_fct_day_991"></td>
        <td class="smc_fct_day"></td>
        <td class="smc_fct_daytext"></td>
        <td class="silink">
          <div class="smc-el-h">
            <a
              class="smc-link-normal"
              href="si0057.asp?__ksinr=8207"
              title="Details anzeigen: Ortsrat Bruchmuehlen 10.03.2026"
            >Ortsrat Bruchmuehlen</a>
          </div>
          <ul class="list-inline smc-detail-list">
            <li>19:00 Uhr</li>
            <li>Saal Torbogenhaus</li>
          </ul>
        </td>
      </tr>
      <tr>
        <td class="smc_fct_day_991"></td>
        <td class="smc_fct_day"></td>
        <td class="smc_fct_daytext"></td>
        <td class="silink">
          <div class="smc-el-h">
            <a
              class="smc-link-normal"
              href="si0057.asp?__ksinr=8185"
              aria-label="Details anzeigen: Ortsrat Melle-Mitte 10.03.2026"
            >Ortsrat Melle-Mitte</a>
          </div>
          <ul class="list-inline smc-detail-list">
            <li>19:00 Uhr</li>
            <li>Ratssaal</li>
          </ul>
        </td>
      </tr>
    </table>
    """
    client = SessionNetClient(storage_root=tmp_path)

    sessions = client._parse_overview(html, year=2026, month=3)

    assert [session.session_id for session in sessions] == ["8207", "8185"]
    assert [session.date for session in sessions] == [date(2026, 3, 10), date(2026, 3, 10)]
