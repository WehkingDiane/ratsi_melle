"""Views for the initial analysis web UI."""

from __future__ import annotations

from django.shortcuts import render

from . import services


def analysis_home(request):
    overview = services.source_overview()
    recent_sessions = services.list_sessions()[:5]
    recent_jobs = services.list_analysis_outputs()[:5]
    return render(
        request,
        "core/analysis_home.html",
        {
            "active_nav": "analysis",
            "overview": overview,
            "recent_sessions": recent_sessions,
            "recent_jobs": recent_jobs,
        },
    )


def session_list(request):
    sessions = services.list_sessions()
    return render(
        request,
        "core/session_list.html",
        {
            "active_nav": "sessions",
            "sessions": sessions,
        },
    )


def session_detail(request, session_id: str):
    session = services.get_session(session_id)
    return render(
        request,
        "core/session_detail.html",
        {
            "active_nav": "sessions",
            "session": session,
            "session_id": session_id,
        },
    )


def job_list(request):
    jobs = services.list_analysis_outputs()
    return render(
        request,
        "core/job_list.html",
        {
            "active_nav": "jobs",
            "jobs": jobs,
        },
    )


def job_detail(request, job_id: str):
    job = services.get_analysis_output(job_id)
    return render(
        request,
        "core/job_detail.html",
        {
            "active_nav": "jobs",
            "job": job,
            "job_id": job_id,
        },
    )
