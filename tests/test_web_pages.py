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
        "/daten/vektor/",
        "/daten/status/",
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
        "service_vector.html",
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
    assert "Build: Vektorindex" in content
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
        "Daten": ["Fetch: Daten holen", "Build: Datenbank-Tools", "Build: Vektorindex"],
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


def test_settings_page_exposes_huggingface_token_form(client, monkeypatch) -> None:
    from settings_ui import views

    monkeypatch.setattr(views, "key_source", lambda provider_id: "nicht gesetzt")

    response = client.get("/einstellungen/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Hugging Face Token" in content
    assert 'name="provider_id" value="huggingface"' in content
    assert 'type="password" name="token"' in content
    assert "HF_TOKEN oder HUGGING_FACE_HUB_TOKEN" in content


def test_settings_page_saves_huggingface_token(client, monkeypatch) -> None:
    from settings_ui import views

    saved = {}
    monkeypatch.setattr(views, "set_api_key", lambda provider_id, token: saved.update({provider_id: token}))
    monkeypatch.setattr(views, "key_source", lambda provider_id: "keychain" if provider_id in saved else "nicht gesetzt")

    response = client.post(
        "/einstellungen/",
        {
            "action": "save_token",
            "provider_id": "huggingface",
            "token": "hf_test_token",
        },
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert saved == {"huggingface": "hf_test_token"}
    assert "Hugging Face-Token gespeichert" in content
    assert "hf_test_token" not in content


def test_settings_page_deletes_huggingface_token(client, monkeypatch) -> None:
    from settings_ui import views

    deleted = []
    monkeypatch.setattr(views, "delete_api_key", lambda provider_id: deleted.append(provider_id))
    monkeypatch.setattr(views, "key_source", lambda provider_id: "nicht gesetzt")

    response = client.post(
        "/einstellungen/",
        {
            "action": "delete_token",
            "provider_id": "huggingface",
        },
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert deleted == ["huggingface"]
    assert "Hugging Face-Token geloescht" in content


def test_job_indicator_is_hidden_without_active_job(client) -> None:
    response = client.get("/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'id="job-indicator"' in content
    assert 'id="job-indicator" href="/daten/" hidden' in content


def test_analysis_start_page_loads_for_session(client) -> None:
    response = client.get("/analyse/starten/?session_id=does-not-exist")

    assert response.status_code == 200
    assert "Sitzung vorbereiten" in response.content.decode("utf-8")


def test_search_page_renders_document_results(client, monkeypatch) -> None:
    from search import views

    monkeypatch.setattr(
        views.services,
        "search_semantic_documents",
        lambda _query, source="ratsinfo": {
            "results": [
                {
                    "rank": 1,
                    "display_score": "0.0328",
                    "session_id": "7123",
                    "display_date": "11.03.2026",
                    "date": "2026-03-11",
                    "committee": "Rat",
                    "meeting_name": "Ratssitzung",
                    "agenda_item": "Oe 7",
                    "title": "Windkraft in Riemsloh",
                    "document_type": "beschlussvorlage",
                    "display_type": "beschlussvorlage",
                }
            ],
            "error": "",
            "warning": "Ergebnisse stammen aus der hybriden Vektorsuche.",
        },
    )

    response = client.get("/suche/?q=windkraft")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Vektortreffer" in content
    assert "0.0328" in content
    assert "Windkraft in Riemsloh" in content
    assert "/analyse/sitzungen/7123/" in content
    assert '<option value="ratsinfo" selected>Ratsinfo</option>' in content


def test_search_page_renders_landkreis_results_without_session_links(client, monkeypatch) -> None:
    from search import views

    captured = {}

    def fake_search(query, source="ratsinfo"):
        captured["query"] = query
        captured["source"] = source
        return {
            "results": [
                {
                    "rank": 1,
                    "display_score": "0.0400",
                    "display_date": "11.03.2026",
                    "date": "2026-03-11",
                    "source": "amtsblaetter",
                    "title": "Amtsblatt 10",
                    "document_title": "PDF Anlage",
                    "url": "https://example.test/a.pdf",
                    "local_path": "/tmp/a.pdf",
                }
            ],
            "error": "",
            "warning": "Ergebnisse stammen aus der hybriden Landkreis-Vektorsuche.",
        }

    monkeypatch.setattr(views.services, "search_semantic_documents", fake_search)

    response = client.get("/suche/?q=Melle&source=landkreis")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert captured == {"query": "Melle", "source": "landkreis"}
    assert '<option value="landkreis" selected>Landkreis</option>' in content
    assert "amtsblaetter" in content
    assert "Amtsblatt 10" in content
    assert "PDF Anlage" in content
    assert "/analyse/sitzungen/7123/" not in content


def test_session_detail_links_document_source_to_session_page(client, monkeypatch) -> None:
    from analysis import views

    monkeypatch.setattr(
        views.services,
        "get_session",
        lambda _session_id: {
            "session_id": "7123",
            "date": "2026-03-11",
            "display_date": "11.03.2026",
            "committee": "Rat",
            "meeting_name": "Ratssitzung",
            "location": "Rathaus",
            "detail_url": "https://example.test/si0057.asp",
            "source_status": {"document_count": 1, "available_count": 1, "missing_count": 0},
            "agenda_items": [],
            "documents": [
                {
                    "id": 4,
                    "agenda_item": "Oe 7",
                    "title": "Windkraft in Riemsloh",
                    "document_type": "beschlussvorlage",
                    "display_type": "beschlussvorlage",
                    "url": "https://example.test/do.asp",
                    "pdf_view_available": True,
                }
            ],
        },
    )

    response = client.get("/analyse/sitzungen/7123/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'href="https://example.test/si0057.asp">Sitzung</a>' in content
    assert 'href="/analyse/sitzungen/7123/dokumente/4/pdf/" target="_blank"' in content
    assert "PDF öffnen" in content
    assert "https://example.test/do.asp" not in content


def test_document_pdf_view_streams_local_pdf(client, monkeypatch, tmp_path) -> None:
    from analysis import views

    pdf_path = tmp_path / "vorlage.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    monkeypatch.setattr(
        views.services,
        "get_local_pdf_document",
        lambda _session_id, _document_id: {
            "path": pdf_path,
            "title": "Vorlage",
            "content_type": "application/pdf",
        },
    )

    response = client.get("/analyse/sitzungen/7123/dokumente/4/pdf/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'inline; filename="vorlage.pdf"'


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
    assert "Quellen und Nutzung" in content
    assert "Die Analysegrundlage enthält Sitzungsdaten" in content
    assert "2 von 3 lokalen Dokumenten verfügbar" in content
    assert "0 analysierbare Dokumente" in content
    assert "nicht auswählbar" in content
    assert 'value="Oe 2" disabled' in content

    assert 'id="analysis-start-submit"' in content
    assert "Analyse wurde gestartet" in content
    assert 'aria-live="polite"' in content
    assert "submitButton.disabled = true" in content
    assert "TOP analysieren" in content
    assert "ChatGPT Plus kann nicht direkt über die API genutzt werden" in content
    assert 'value="meeting_briefing" selected' in content
    assert 'value="none" selected' in content
    assert 'placeholder="gpt-5.6-terra"' in content


def test_analysis_start_scope_switch_filters_prompt_templates(client, monkeypatch) -> None:
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
    templates_by_scope = {
        "session": [
            {
                "id": "session_tpl",
                "label": "Session Vorlage",
                "is_active": True,
                "prompt_text": "Session Prompt",
            }
        ],
        "tops": [
            {
                "id": "tops_tpl",
                "label": "TOP Vorlage",
                "is_active": True,
                "prompt_text": "TOP Prompt",
            }
        ],
    }

    monkeypatch.setattr(views.services, "get_session", lambda _session_id: session)
    monkeypatch.setattr(views.services, "list_sessions", lambda: [session])
    monkeypatch.setattr(
        views.services,
        "list_prompt_templates",
        lambda scope="": templates_by_scope.get(scope, []),
    )
    monkeypatch.setattr(
        views.services,
        "get_prompt_template",
        lambda template_id: next(
            (
                template
                for templates in templates_by_scope.values()
                for template in templates
                if template["id"] == template_id
            ),
            None,
        ),
    )

    response = client.get("/analyse/starten/?session_id=7123&scope=session&template_id=session_tpl")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Session Vorlage" in content
    assert "TOP Vorlage" not in content
    assert 'value="meeting_briefing" selected' in content
    assert 'href="/analyse/starten/?session_id=7123&amp;scope=session"' in content
    assert 'url.searchParams.delete("template_id")' in content

    response = client.get("/analyse/starten/?session_id=7123&scope=tops")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "TOP Vorlage" in content
    assert "Session Vorlage" not in content
    assert 'value="top_deep_dive" selected' in content
    assert 'href="/analyse/starten/?session_id=7123&amp;scope=tops"' in content
    assert 'value="session_tpl" selected' not in content


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


def test_prompt_template_list_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.get("/analyse/prompts/")

    assert response.status_code == 200
    assert "Prompt-Vorlagen" in response.content.decode("utf-8")


def test_analysis_start_handles_invalid_prompt_template_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.get("/analyse/starten/")

    assert response.status_code == 200
    assert "KI-Analyse starten" in response.content.decode("utf-8")


def test_prompt_template_create_post_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.post(
        "/analyse/prompts/neu/",
        {
            "label": "Kaputte Vorlage",
            "scope": "session",
            "description": "",
            "prompt_text": "Analysiere {{session_title}}.",
            "variables": "session_title",
            "visibility": "private",
            "is_active": "1",
        },
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Prompt-Vorlagen konnten nicht gelesen werden" in content


def test_prompt_template_edit_post_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.post(
        "/analyse/prompts/kaputt/",
        {
            "label": "Kaputte Vorlage",
            "scope": "session",
            "description": "",
            "prompt_text": "Analysiere {{session_title}}.",
            "variables": "session_title",
            "visibility": "private",
            "is_active": "1",
        },
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Prompt-Vorlagen konnten nicht gelesen werden" in content


def test_prompt_template_edit_get_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.get("/analyse/prompts/kaputt/")

    assert response.status_code == 200
    assert "Prompt-Vorlage" in response.content.decode("utf-8")


def test_prompt_template_duplicate_post_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.post("/analyse/prompts/kaputt/duplizieren/")

    assert response.status_code == 302


def test_prompt_template_deactivate_post_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.post("/analyse/prompts/kaputt/deaktivieren/")

    assert response.status_code == 302


def test_analysis_start_with_template_id_handles_invalid_store(client, monkeypatch, tmp_path) -> None:
    from analysis import services

    template_path = tmp_path / "private" / "prompt_templates.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{not json", encoding="utf-8")
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    response = client.get("/analyse/starten/?template_id=kaputt")

    assert response.status_code == 200
    assert "KI-Analyse starten" in response.content.decode("utf-8")


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


def test_service_build_page_excludes_vector_build(client) -> None:
    response = client.get("/daten/build/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Lokalen Index bauen" in content
    assert "Online-Index bauen" in content
    assert "Landkreis-Datenbank bauen" in content
    assert "Vektorindex bauen" not in content
    assert "SQLite-Dokumente" not in content


def test_service_fetch_page_includes_landkreis_fetch(client) -> None:
    response = client.get("/daten/fetch/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Landkreis-Veröffentlichungen laden" in content
    assert 'name="action" value="fetch_landkreis_publications"' in content
    assert "Bekanntmachungen" in content
    assert "Amtsblaetter" in content
    assert "Datenwurzel" in content


def test_service_pages_expose_manual_status_refresh(client) -> None:
    response = client.get("/daten/")
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")

    status_panel = soup.select_one('[data-service-status][data-status-url="/daten/status/"]')

    assert response.status_code == 200
    assert status_panel is not None
    assert status_panel.select_one("h2").get_text(strip=True) == "Aktueller Status"
    assert status_panel.select_one("[data-service-status-refresh]").get_text(strip=True) == "Status aktualisieren"
    assert {
        node["data-status-field"]
        for node in status_panel.select("[data-status-field]")
    } == {
        "raw_data_summary",
        "local_index_summary",
        "online_index_summary",
        "qdrant_summary",
    }


def test_service_status_returns_fresh_values(client, monkeypatch) -> None:
    from data_tools import views

    initial = {
        "raw_data_exists": False,
        "raw_data_summary": "fehlt",
        "local_index_exists": False,
        "local_index_summary": "fehlt",
        "online_index_exists": False,
        "online_index_summary": "fehlt",
        "qdrant_exists": False,
        "qdrant_summary": "fehlt",
    }
    refreshed = {
        "raw_data_exists": True,
        "raw_data_summary": "3 Sitzungsordner",
        "local_index_exists": True,
        "local_index_summary": "2 Sitzungen / 4 Dokumente",
        "online_index_exists": False,
        "online_index_summary": "fehlt",
        "qdrant_exists": True,
        "qdrant_summary": "vorhanden",
    }
    status_values = iter((initial, refreshed))
    monkeypatch.setattr(views.services, "service_status", lambda: next(status_values))

    initial_response = client.get("/daten/status/")
    refreshed_response = client.get("/daten/status/")

    assert initial_response.status_code == 200
    assert initial_response.json() == {"status": initial}
    assert refreshed_response.status_code == 200
    assert refreshed_response.json() == {"status": refreshed}


def test_service_vector_page_renders_vector_status(client, monkeypatch) -> None:
    from data_tools import views

    monkeypatch.setattr(
        views.services,
        "vector_index_status",
        lambda: {
            "status": "needs_update",
            "sqlite_document_count": 10,
            "indexable_document_count": 9,
            "indexed_vector_count": 7,
            "missing_vector_count": 2,
            "orphaned_vector_count": 1,
            "coverage_percent": 77.8,
            "latest_session_date": "2026-03-11",
            "warnings": ["Vektorindex ist nicht vollstaendig."],
        },
    )
    monkeypatch.setattr(
        views.services,
        "landkreis_vector_index_status",
        lambda: {
            "status": "missing_qdrant",
            "sqlite_document_count": 5,
            "indexable_document_count": 4,
            "indexed_vector_count": 0,
            "missing_vector_count": None,
            "orphaned_vector_count": None,
            "coverage_percent": None,
            "latest_document_date": "2026-04-01",
            "warnings": ["Qdrant-Collection fehlt: landkreis_publications"],
        },
    )

    response = client.get("/daten/vektor/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Ratsinfo-Vektorindex bauen" in content
    assert "Landkreis-Vektorindex bauen" in content
    assert "Ratsinfo-Vektorstatus" in content
    assert "Landkreis-Vektorstatus" in content
    assert "SQLite-Dokumente" in content
    assert "10" in content
    assert "5" in content
    assert "77,8 %" in content
    assert "Vektorindex ist nicht vollstaendig." in content
    assert "Qdrant-Collection fehlt: landkreis_publications" in content


def test_build_vector_index_form_starts_existing_service_job(client, monkeypatch) -> None:
    from data_tools import views

    captured = {}

    class Job:
        job_id = "vector123"

    def fake_build_service_command(action, data):
        captured["action"] = action
        captured["limit"] = data.get("limit")
        return (["python", "scripts/build_vector_index.py", "--limit", "25"], [])

    def fake_start_service_job(action, command, cwd):
        captured["job_action"] = action
        captured["command"] = command
        captured["cwd"] = cwd
        return Job()

    monkeypatch.setattr(views.services, "build_service_command", fake_build_service_command)
    monkeypatch.setattr(views.service_jobs, "start_service_job", fake_start_service_job)

    response = client.post(
        "/daten/vektor/",
        {"action": "build_vector_index", "limit": "25"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/daten/jobs/vector123/"
    assert captured["action"] == "build_vector_index"
    assert captured["limit"] == "25"
    assert captured["job_action"] == "build_vector_index"
    assert captured["command"] == ["python", "scripts/build_vector_index.py", "--limit", "25"]


def test_landkreis_vector_index_form_starts_service_job(client, monkeypatch) -> None:
    from data_tools import views

    captured = {}

    class Job:
        job_id = "landkreis-vector123"

    def fake_build_service_command(action, data):
        captured["action"] = action
        captured["data_dir"] = data.get("data_dir")
        captured["limit"] = data.get("limit")
        captured["max_text_chars"] = data.get("max_text_chars")
        return (
            [
                "python",
                "scripts/build_landkreis_vector_index.py",
                "--data-dir",
                "/mnt/d/landkreis_osnabrueck",
                "--limit",
                "10",
                "--max-text-chars",
                "3000",
            ],
            [],
        )

    def fake_start_service_job(action, command, cwd):
        captured["job_action"] = action
        captured["command"] = command
        return Job()

    monkeypatch.setattr(views.services, "build_service_command", fake_build_service_command)
    monkeypatch.setattr(views.service_jobs, "start_service_job", fake_start_service_job)

    response = client.post(
        "/daten/vektor/",
        {
            "action": "build_landkreis_vector_index",
            "data_dir": "/mnt/d/landkreis_osnabrueck",
            "limit": "10",
            "max_text_chars": "3000",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/daten/jobs/landkreis-vector123/"
    assert captured["action"] == "build_landkreis_vector_index"
    assert captured["data_dir"] == "/mnt/d/landkreis_osnabrueck"
    assert captured["limit"] == "10"
    assert captured["max_text_chars"] == "3000"
    assert captured["job_action"] == "build_landkreis_vector_index"
    assert captured["command"] == [
        "python",
        "scripts/build_landkreis_vector_index.py",
        "--data-dir",
        "/mnt/d/landkreis_osnabrueck",
        "--limit",
        "10",
        "--max-text-chars",
        "3000",
    ]


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
        status_label = "läuft"

    monkeypatch.setattr(views.service_jobs, "get_service_job", lambda _job_id: Job())

    response = client.get("/daten/jobs/abc123/")
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")

    assert response.status_code == 200
    assert soup.select_one("[data-service-job-id]")["data-service-job-id"] == "abc123"
    assert soup.select_one("#job-status").get_text(strip=True) == "läuft"
    assert soup.select_one("#job-output").get_text(strip=True) == "Zeile 1"
    assert soup.select_one("#job-running-banner") is not None
    assert soup.select_one("#job-completion-message").has_attr("hidden")
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
    assert "KI-Analyse" in headings
    assert "Analysegrundlage und Quellenkontext" in headings
    assert soup.find("summary", string="Verwendeter Prompt") is not None
    assert "Strukturierte Daten" in headings
    assert "Quellen" in headings
    assert "data/analysis_outputs/job_7.raw.json" in soup.get_text()
