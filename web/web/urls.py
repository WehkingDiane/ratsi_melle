"""Top-level routes for the standalone web UI."""

from __future__ import annotations

from django.urls import include, path


urlpatterns = [
    path("", include("core.urls")),
    path("analyse/", include("analysis.urls")),
    path("daten/", include("data_tools.urls")),
    path("veroeffentlichung/", include("publishing.urls")),
    path("suche/", include("search.urls")),
    path("einstellungen/", include("settings_ui.urls")),
]
