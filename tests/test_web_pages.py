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


def test_main_navigation_is_in_shared_layout(client) -> None:
    response = client.get("/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Ratsi Melle" in content
    assert "Lokale Arbeitsoberflaeche" in content
    assert "Dashboard" in content
    assert "Dashboard oeffnen" in content
    assert "Analyse" in content
    assert "Analyse-Uebersicht" in content
    assert "KI-Analyse starten" in content
    assert "Sitzungen" in content
    assert "Analysejobs" in content
    assert "Daten" in content
    assert "Fetch: Daten holen" in content
    assert "Build: Datenbank-Tools" in content
    assert "Veroeffentlichung" in content
    assert "Veroeffentlichung oeffnen" in content
    assert "Suche" in content
    assert "Suche oeffnen" in content
    assert "Einstellungen" in content
    assert "Einstellungen oeffnen" in content
    assert "Lokale Entwicklungsoberflaeche" in content


def test_analysis_start_page_loads_for_session(client) -> None:
    response = client.get("/analyse/starten/?session_id=does-not-exist")

    assert response.status_code == 200
    assert "KI-Analyse starten" in response.content.decode("utf-8")


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
