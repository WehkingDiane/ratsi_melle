"""Core routes for the standalone web UI."""

from __future__ import annotations

from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
