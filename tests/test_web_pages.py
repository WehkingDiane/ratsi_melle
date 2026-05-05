from __future__ import annotations

import os
import sys
from pathlib import Path
from types import FunctionType

import pytest
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

django = pytest.importorskip("django")


CORE_TEMPLATE_ROOT = WEB_ROOT / "core" / "templates" / "core"
CORE_PARTIAL_ROOT = CORE_TEMPLATE_ROOT / "partials"
ANALYSIS_TEMPLATE_ROOT = WEB_ROOT / "analysis" / "templates" / "analysis"
DATA_TOOLS_TEMPLATE_ROOT = WEB_ROOT / "data_tools" / "templates" / "data_tools"


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
        "/analyse/prompts/",
        "/analyse/prompts/neu/",
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


def test_nested_pages_use_absolute_static_urls(client) -> None:
    response = client.get("/analyse/starten/")
    content = response.content.decode("utf-8")

    assert 'href="/static/core/css/base.css"' in content
    assert 'src="/static/core/js/service_status.js"' in content
    assert 'href="static/' not in content
    assert 'src="static/' not in content


def test_templates_are_kept_in_their_feature_apps() -> None:
    core_templates = {
        path.relative_to(WEB_ROOT / "core" / "templates").as_posix()
        for path in (WEB_ROOT / "core" / "templates").rglob("*.html")
    }
    analysis_templates = {path.name for path in ANALYSIS_TEMPLATE_ROOT.glob("*.html")}
    analysis_partials = {path.name for path in (ANALYSIS_TEMPLATE_ROOT / "partials").glob("*.html")}
    data_templates = {path.name for path in DATA_TOOLS_TEMPLATE_ROOT.glob("*.html")}

    assert core_templates == {
        "base.html",
        "core/dashboard.html",
        "core/partials/service_result.html",
        "core/partials/service_status.html",
    }
    assert {
        "analysis_start.html",
        "index.html",
        "job_detail.html",
        "job_list.html",
        "prompt_template_form.html",
        "prompt_templates.html",
        "session_detail.html",
        "session_list.html",
    }.issubset(analysis_templates)
    assert {"job_table.html", "session_table.html"}.issubset(analysis_partials)
    assert {
        "index.html",
        "service_build.html",
        "service_fetch.html",
        "service_job_detail.html",
    }.issubset(data_templates)


def test_core_views_only_expose_core_pages() -> None:
    from core import views

    public_views = {
        name
        for name, value in vars(views).items()
        if isinstance(value, FunctionType) and value.__module__ == views.__name__ and not name.startswith("_")
    }

    assert public_views == {"dashboard"}


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
    assert "Prompt-Vorlagen" in content
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


def test_navigation_dropdowns_have_expected_links(client) -> None:
    response = client.get("/")
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")

    labels = {
        menu.select_one(".nav-menu-label").get_text(strip=True): [
            link.get_text(strip=True) for link in menu.select(".nav-dropdown a")
        ]
        for menu in soup.select(".main-nav .nav-menu")
    }

    assert labels == {
        "Dashboard": ["Dashboard öffnen"],
        "Analyse": ["Analyse-Übersicht", "Prompt-Vorlagen", "KI-Analyse starten", "Sitzungen", "Analysejobs"],
        "Daten": ["Fetch: Daten holen", "Build: Datenbank-Tools"],
        "Veröffentlichung": ["Veröffentlichung öffnen"],
        "Suche": ["Suche öffnen"],
        "Einstellungen": ["Einstellungen öffnen"],
    }
    assert all(
        menu.select_one(".nav-menu-label").get("aria-haspopup") == "true"
        for menu in soup.select(".main-nav .nav-menu")
    )


@pytest.mark.parametrize(
    ("path", "active_label"),
    [
        ("/", "Dashboard"),
        ("/analyse/", "Analyse"),
        ("/daten/", "Daten"),
        ("/veroeffentlichung/", "Veröffentlichung"),
        ("/suche/", "Suche"),
        ("/einstellungen/", "Einstellungen"),
    ],
)
def test_active_navigation_matches_section(path: str, active_label: str, client) -> None:
    response = client.get(path)
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
    active_items = [item.get_text(strip=True) for item in soup.select(".nav-menu-label.active")]

    assert response.status_code == 200
    assert active_items == [active_label]


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
    from analysis import views

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
    from analysis import views

    monkeypatch.setattr(
        views.services,
        "run_analysis_from_form",
        lambda _data: ({"job_id": 99}, []),
    )
    monkeypatch.setattr(
        views.services,
        "canonical_analysis_job_id",
        lambda _result: "workflow:7",
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
    assert response.headers["Location"] == "/analyse/jobs/workflow:7/"


def test_prompt_template_management_create_edit_duplicate_deactivate(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", tmp_path / "private" / "prompt_templates.json")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.get("/analyse/prompts/")
    assert response.status_code == 200
    assert "Prompt-Vorlagen" in response.content.decode("utf-8")

    response = client.post(
        "/analyse/prompts/neu/",
        {
            "id": "session_test",
            "label": "Session Test",
            "scope": "session",
            "description": "Beschreibung",
            "prompt_text": "Analysiere {{session_title}}.",
            "variables": "session_title",
            "visibility": "private",
            "is_active": "1",
        },
    )
    assert response.status_code == 302

    response = client.post(
        "/analyse/prompts/session_test/",
        {
            "label": "Session Test 2",
            "scope": "session",
            "description": "Beschreibung",
            "prompt_text": "Analysiere {{session_title}} fuer {{analysis_goal}}.",
            "variables": "session_title, analysis_goal",
            "visibility": "private",
            "is_active": "1",
        },
    )
    assert response.status_code == 302

    response = client.get("/analyse/prompts/session_test/duplizieren/")
    assert response.status_code == 302
    assert services.get_prompt_template("session_test_copy") is None

    response = client.post("/analyse/prompts/session_test/duplizieren/")
    assert response.status_code == 302
    assert services.get_prompt_template("session_test_copy") is not None

    response = client.post("/analyse/prompts/session_test/deaktivieren/")
    assert response.status_code == 302
    assert services.get_prompt_template("session_test")["is_active"] is False


def test_analysis_start_filters_active_templates_by_scope(client, monkeypatch) -> None:
    from analysis import views

    session = {
        "session_id": "7123",
        "date": "2026-03-11",
        "display_date": "11.03.2026",
        "committee": "Rat",
        "meeting_name": "Ratssitzung",
        "source_status": {"available_count": 1, "document_count": 1},
        "agenda_items": [],
    }
    monkeypatch.setattr(views.services, "get_session", lambda _session_id: session)
    monkeypatch.setattr(views.services, "list_sessions", lambda: [session])
    monkeypatch.setattr(
        views.services,
        "list_prompt_templates",
        lambda scope: [
            {
                "id": "session_active",
                "label": "Aktiv",
                "scope": "session",
                "description": "Aktive Vorlage",
                "prompt_text": "Prompt",
                "is_active": True,
            },
            {
                "id": "session_inactive",
                "label": "Inaktiv",
                "scope": "session",
                "description": "",
                "prompt_text": "Prompt",
                "is_active": False,
            },
        ] if scope == "session" else [],
    )

    response = client.get("/analyse/starten/?session_id=7123")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Aktiv" in content
    assert "Inaktiv" not in content


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


def test_service_post_requires_csrf_when_enforced(monkeypatch) -> None:
    from django.test import Client

    from data_tools import views

    monkeypatch.setattr(
        views.services,
        "build_service_command",
        lambda _action, _data: (["python", "scripts/build_local_index.py"], []),
    )

    response = Client(enforce_csrf_checks=True).post(
        "/daten/build/",
        {
            "action": "build_local_index",
            "refresh_existing": "1",
        },
    )

    assert response.status_code == 403


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


def test_service_job_detail_exposes_live_update_hooks(client, monkeypatch) -> None:
    from data_tools import views

    class Job:
        job_id = "abc123"
        action = "build_local_index"
        status = "running"
        exit_code = None
        started_at = "01.01.2026 10:00:00"
        finished_at = ""
        command_text = "python scripts/build_local_index.py"
        output = "Zeile 1"

    monkeypatch.setattr(views.service_jobs, "get_service_job", lambda _job_id: Job())

    response = client.get("/daten/jobs/abc123/")
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")

    assert response.status_code == 200
    assert soup.select_one("[data-service-job-id]")["data-service-job-id"] == "abc123"
    assert soup.select_one("#job-status").get_text(strip=True) == "running"
    assert soup.select_one("#job-output").get_text(strip=True) == "Zeile 1"
    assert soup.select_one("#job-running-banner") is not None
    assert soup.select_one('script[src="/static/core/js/service_job_detail.js"]') is not None


def test_old_analysis_service_urls_redirect_to_data_area(client) -> None:
    response = client.get("/analyse/service/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/daten/"


def test_legacy_v1_analysis_output_page_loads(client, monkeypatch, tmp_path) -> None:
    import json

    from analysis import services

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


def test_analysis_job_detail_renders_result_sections(client, monkeypatch) -> None:
    from analysis import views

    monkeypatch.setattr(
        views.services,
        "get_analysis_output",
        lambda _job_id: {
            "job_id": "workflow:7",
            "session_id": "7123",
            "purpose": "content_analysis",
            "status": "done",
            "schema_version": "2.0",
            "output_type": "raw_analysis",
            "model_name": "none",
            "prompt_version": "web",
            "markdown": "# Analyse",
            "ki_response": "KI-Antwort",
            "prompt_text": "Prompt aus Datei",
            "structured_outputs": [{"output_type": "raw_analysis"}],
            "sources": ["data/analysis_outputs/job_7.raw.json"],
            "has_content": True,
            "error_message": "",
        },
    )

    response = client.get("/analyse/jobs/workflow:7/")
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
    headings = [heading.get_text(strip=True) for heading in soup.select("h2")]

    assert response.status_code == 200
    assert "Metadaten" in headings
    assert "Markdown" in headings
    assert "KI-Antwort" in headings
    assert "Prompt" in headings
    assert "Strukturierte Daten" in headings
    assert "Quellen" in headings
    assert "data/analysis_outputs/job_7.raw.json" in soup.get_text()
