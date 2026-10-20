"""Top-level routes for the standalone web UI."""

from __future__ import annotations

from django.urls import include, path
from settings_ui import views as settings_views


urlpatterns = [
    path("", include("core.urls")),
    path("analyse/", include("analysis.urls")),
    path("daten/", include("data_tools.urls")),
    path("veroeffentlichung/", include("publishing.urls")),
    path("suche/", include("search.urls")),
    path("service/", include("data_tools.service_urls")),
    path("service/einstellungen/", include("settings_ui.urls")),
    path("einstellungen/", settings_views.index),
]
