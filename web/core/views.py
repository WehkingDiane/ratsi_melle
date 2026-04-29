"""Core views for the standalone web UI."""

from __future__ import annotations

from django.shortcuts import render

from . import services


def dashboard(request):
    overview = services.source_overview()
    recent_sessions = services.list_sessions()[:5]
    recent_jobs = services.list_analysis_outputs()[:5]
    return render(
        request,
        "core/dashboard.html",
        {
            "active_nav": "dashboard",
            "overview": overview,
            "recent_sessions": recent_sessions,
            "recent_jobs": recent_jobs,
        },
    )
