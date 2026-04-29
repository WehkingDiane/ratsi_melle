from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

django = pytest.importorskip("django")


CORE_TEMPLATE_ROOT = WEB_ROOT / "core" / "templates" / "core"


@pytest.fixture()
def client():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
    django.setup()
    from django.test import Client

    return Client()


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/analyse/",
        "/analyse/starten/",
        "/analyse/sitzungen/",
        "/analyse/sitzungen/does-not-exist/",
        "/analyse/jobs/",
        "/analyse/jobs/does-not-exist/",
        "/daten/",
        "/daten/fetch/",
        "/daten/build/",
        "/daten/jobs/status/",
        "/veroeffentlichung/",
        "/suche/",
        "/einstellungen/",
    ],
)
def test_analysis_pages_load(path: str, client) -> None:
    response = client.get(path)

    assert response.status_code == 200


def test_core_templates_do_not_contain_feature_page_duplicates() -> None:
    template_files = {path.name for path in CORE_TEMPLATE_ROOT.glob("*.html")}

    assert template_files == {"dashboard.html"}


def test_main_navigation_is_in_shared_layout(client) -> None:
    response = client.get("/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Ratsi Melle" in content
    assert "Lokale Arbeitsoberfläche" in content
    assert "Dashboard" in content
    assert "Dashboard öffnen" in content
    assert "Analyse" in content
    assert "Analyse-Übersicht" in content
    assert "KI-Analyse starten" in content
    assert "Sitzungen" in content
    assert "Analysejobs" in content
    assert "Daten" in content
    assert "Fetch: Daten holen" in content
    assert "Build: Datenbank-Tools" in content
    assert "Veröffentlichung" in content
    assert "Veröffentlichung öffnen" in content
    assert "Suche" in content
    assert "Suche öffnen" in content
    assert "Einstellungen" in content
    assert "Einstellungen öffnen" in content
    assert "Lokale Entwicklungsoberfläche" in content


def test_job_indicator_is_hidden_without_active_job(client) -> None:
    response = client.get("/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'id="job-indicator"' in content
    assert 'id="job-indicator" href="/daten/" hidden' in content


def test_analysis_start_page_loads_for_session(client) -> None:
    response = client.get("/analyse/starten/?session_id=does-not-exist")

    assert response.status_code == 200
    assert "KI-Analyse starten" in response.content.decode("utf-8")


def test_analysis_start_explains_session_document_transfer(client, monkeypatch) -> None:
    from core import views

    session = {
        "session_id": "7123",
        "date": "2026-03-11",
        "display_date": "11.03.2026",
        "committee": "Rat",
        "meeting_name": "Ratssitzung",
        "source_status": {"available_count": 2, "document_count": 3},
        "agenda_items": [
            {
                "number": "Oe 1",
                "title": "Mit Dokument",
                "analysis_document_count": 2,
                "has_analysis_documents": True,
                "decision": "angenommen",
            },
            {
                "number": "Oe 2",
                "title": "Ohne Dokument",
                "analysis_document_count": 0,
                "has_analysis_documents": False,
                "decision": "",
            },
        ],
    }
    monkeypatch.setattr(views.services, "get_session", lambda _session_id: session)
    monkeypatch.setattr(views.services, "list_sessions", lambda: [session])

    response = client.get("/analyse/starten/?session_id=7123")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "KI-Dokumentübergabe" in content
    assert "Bei „Ganze Sitzung“ werden alle lokal verfügbaren Dokumente" in content
    assert "2 von 3 lokalen Dokumenten verfügbar" in content
    assert "0 analysierbare Dokumente" in content
    assert "nicht auswählbar" in content
    assert 'value="Oe 2" disabled' in content


def test_analysis_start_post_redirects_to_created_job(client, monkeypatch) -> None:
    from core import views

    monkeypatch.setattr(
        views.services,
        "run_analysis_from_form",
        lambda _data: ({"job_id": 99}, []),
    )

    response = client.post(
        "/analyse/starten/",
        {
            "session_id": "7123",
            "scope": "session",
            "purpose": "content_analysis",
            "prompt_text": "Analysiere die Sitzung.",
            "provider_id": "none",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/analyse/jobs/99/"


def test_service_post_starts_background_job(client, monkeypatch) -> None:
    from data_tools import views

    class Job:
        job_id = "abc123"

    monkeypatch.setattr(
        views.services,
        "build_service_command",
        lambda _action, _data: (["python", "scripts/build_local_index.py"], []),
    )
    monkeypatch.setattr(
        views.service_jobs,
        "start_service_job",
        lambda _action, _command, _cwd: Job(),
    )

    response = client.post(
        "/daten/build/",
        {"action": "build_local_index"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/daten/jobs/abc123/"


def test_service_job_status_detail_returns_live_output(client, monkeypatch) -> None:
    from data_tools import views

    class Job:
        def to_dict(self):
            return {
                "job_id": "abc123",
                "action": "build_local_index",
                "status": "running",
                "output": "Zeile 1\nZeile 2",
                "exit_code": None,
                "started_at": "01.01.2026 10:00:00",
                "finished_at": "",
            }

    monkeypatch.setattr(views.service_jobs, "get_service_job", lambda _job_id: Job())

    response = client.get("/daten/jobs/abc123/status/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["job"]["output"] == "Zeile 1\nZeile 2"
    assert payload["job"]["status"] == "running"


def test_old_analysis_service_urls_redirect_to_data_area(client) -> None:
    response = client.get("/analyse/service/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/daten/"


def test_legacy_v1_analysis_output_page_loads(client, monkeypatch, tmp_path) -> None:
    import json

    from core import services

    outputs = tmp_path / "analysis_outputs"
    outputs.mkdir()
    (outputs / "job_4.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": 4,
                "ki_response": "Antwort",
                "markdown": "# Analyse",
                "prompt_text": "Bitte analysieren",
                "status": "done",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(services, "ANALYSIS_OUTPUTS_DIR", outputs)

    response = client.get("/analyse/jobs/4/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Antwort" in content
