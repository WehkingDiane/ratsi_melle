"""Shared and legacy views for the standalone web UI."""

from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import render
from django.shortcuts import redirect
from django.utils import timezone

from . import services
from . import service_jobs


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


def analysis_home(request):
    overview = services.source_overview()
    recent_sessions = services.list_sessions()[:5]
    recent_jobs = services.list_analysis_outputs()[:5]
    return render(
        request,
        "analysis/index.html",
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
        "analysis/session_list.html",
        {
            "active_nav": "analysis",
            "sessions": sessions,
        },
    )


def session_detail(request, session_id: str):
    session = services.get_session(session_id)
    return render(
        request,
        "analysis/session_detail.html",
        {
            "active_nav": "analysis",
            "session": session,
            "session_id": session_id,
        },
    )


def analysis_start(request):
    selected_session_id = request.GET.get("session_id", "")
    selected_session = services.get_session(selected_session_id) if selected_session_id else None
    scope = request.POST.get("scope", request.GET.get("scope", "session"))
    template_id = request.POST.get("template_id", request.GET.get("template_id", ""))
    selected_template = services.get_prompt_template(template_id) if template_id else None
    prompt_text = request.POST.get(
        "prompt_text",
        str(selected_template.get("text") or "") if selected_template else "",
    )
    errors: list[str] = []

    if request.method == "POST":
        post_data = {
            "session_id": request.POST.get("session_id", ""),
            "scope": request.POST.get("scope", "session"),
            "top_numbers": request.POST.getlist("top_numbers"),
            "purpose": request.POST.get("purpose", "content_analysis"),
            "template_id": request.POST.get("template_id", ""),
            "prompt_text": request.POST.get("prompt_text", ""),
            "provider_id": request.POST.get("provider_id", "none"),
            "model_name": request.POST.get("model_name", ""),
        }
        result, errors = services.run_analysis_from_form(post_data)
        if result:
            return redirect("analysis:job_detail", job_id=result["job_id"])
        selected_session_id = post_data["session_id"]
        selected_session = services.get_session(selected_session_id) if selected_session_id else None
        scope = post_data["scope"]
        template_id = post_data["template_id"]
        prompt_text = post_data["prompt_text"]

    templates = services.list_prompt_templates(scope)
    return render(
        request,
        "analysis/analysis_start.html",
        {
            "active_nav": "analysis",
            "sessions": services.list_sessions(),
            "selected_session": selected_session,
            "selected_session_id": selected_session_id,
            "scope": scope,
            "templates": templates,
            "selected_template_id": template_id,
            "prompt_text": prompt_text,
            "purpose_options": services.analysis_purpose_options(),
            "provider_options": services.provider_options(),
            "errors": errors,
        },
    )


def job_list(request):
    jobs = services.list_analysis_outputs()
    return render(
        request,
        "analysis/job_list.html",
        {
            "active_nav": "analysis",
            "jobs": jobs,
        },
    )


def job_detail(request, job_id: str):
    job = services.get_analysis_output(job_id)
    return render(
        request,
        "analysis/job_detail.html",
        {
            "active_nav": "analysis",
            "job": job,
            "job_id": job_id,
        },
    )


def service_home(request):
    return render(
        request,
        "data_tools/index.html",
        {
            "active_nav": "data",
            "status": services.service_status(),
            "jobs": service_jobs.list_service_jobs(),
        },
    )


def service_fetch(request):
    result = None
    errors: list[str] = []
    current_year = timezone.now().year
    if request.method == "POST":
        command, errors = services.build_service_command(
            request.POST.get("action", ""),
            request.POST,
        )
        if command:
            job = service_jobs.start_service_job(request.POST.get("action", ""), command, services.REPO_ROOT)
            return redirect("data_tools:service_job_detail", job_id=job.job_id)
    return render(
        request,
        "data_tools/service_fetch.html",
        {
            "active_nav": "data",
            "status": services.service_status(),
            "errors": errors,
            "current_year": current_year,
        },
    )


def service_build(request):
    result = None
    errors: list[str] = []
    current_year = timezone.now().year
    if request.method == "POST":
        command, errors = services.build_service_command(
            request.POST.get("action", ""),
            request.POST,
        )
        if command:
            job = service_jobs.start_service_job(request.POST.get("action", ""), command, services.REPO_ROOT)
            return redirect("data_tools:service_job_detail", job_id=job.job_id)
    return render(
        request,
        "data_tools/service_build.html",
        {
            "active_nav": "data",
            "status": services.service_status(),
            "errors": errors,
            "current_year": current_year,
        },
    )


def service_job_detail(request, job_id: str):
    job = service_jobs.get_service_job(job_id)
    return render(
        request,
        "data_tools/service_job_detail.html",
        {
            "active_nav": "data",
            "job": job,
            "job_id": job_id,
            "status": services.service_status(),
        },
    )


def service_job_status(request):
    active = [job.to_dict() for job in service_jobs.active_service_jobs()]
    recent = [job.to_dict() for job in service_jobs.list_service_jobs(limit=5)]
    return JsonResponse({"active": active, "recent": recent})
