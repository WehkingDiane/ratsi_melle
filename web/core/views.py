"""Core views for the standalone web UI."""

from __future__ import annotations

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from analysis import services as analysis_services
from core.services import ri_sessions
from core.services.session_inventory import dashboard_session_groups


@never_cache
def dashboard(request):
    overview = analysis_services.source_overview()
    today = timezone.localdate()
    ri_notice = ''
    try:
        ri_catalogue = ri_sessions.list_sessions()
    except ri_sessions.RiCatalogueError:
        ri_catalogue = None
        ri_notice = 'RI-Index nicht lesbar; RI-Termine und RI-Links sind derzeit nicht verfügbar.'
    try:
        ri_calendar = ri_sessions.list_calendar_sessions()
    except ri_sessions.RiCatalogueError:
        ri_calendar = []
        ri_notice = (ri_notice + ' ' if ri_notice else '') + 'RI-Onlinekalender nicht lesbar; angezeigt werden die übrigen bekannten Termine.'
    meetings = dashboard_session_groups(analysis_services.list_sessions(), today, ri_sessions=ri_catalogue, ri_online_sessions=ri_calendar)
    return render(
        request,
        "core/dashboard.html",
        {
            "active_nav": "dashboard",
            "overview": overview,
            "ri_session_count": len(ri_catalogue) if ri_catalogue is not None else None,
            "ri_notice": ri_notice,
            **meetings,
            "today": today,
        },
    )
