"""Top-level routes for the standalone web UI."""

from __future__ import annotations

from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="analysis:index", permanent=False)),
    path("analyse/", include("core.urls")),
]
