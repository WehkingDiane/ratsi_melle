"""Core views for the standalone web UI."""

from __future__ import annotations

from django.shortcuts import render
from django.utils import timezone

from analysis import services as analysis_services
from core.services.session_inventory import dashboard_session_groups


def dashboard(request):
    overview = analysis_services.source_overview()
    today = timezone.localdate()
    meetings = dashboard_session_groups(analysis_services.list_sessions(), today)
    return render(
        request,
        "core/dashboard.html",
        {
            "active_nav": "dashboard",
            "overview": overview,
            **meetings,
            "today": today,
        },
    )
