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
        "/analyse/",
        "/analyse/starten/",
        "/analyse/sitzungen/",
        "/analyse/sitzungen/does-not-exist/",
        "/analyse/jobs/",
        "/analyse/jobs/does-not-exist/",
        "/analyse/service/",
        "/analyse/service/fetch/",
        "/analyse/service/build/",
        "/analyse/service/jobs/status/",
    ],
)
def test_analysis_pages_load(path: str, client) -> None:
    response = client.get(path)

    assert response.status_code == 200


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
    from core import views

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
        "/analyse/service/build/",
        {"action": "build_local_index"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/analyse/service/jobs/abc123/"
