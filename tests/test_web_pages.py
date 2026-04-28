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
        "/analyse/sitzungen/",
        "/analyse/sitzungen/does-not-exist/",
        "/analyse/jobs/",
        "/analyse/jobs/does-not-exist/",
    ],
)
def test_analysis_pages_load(path: str, client) -> None:
    response = client.get(path)

    assert response.status_code == 200
