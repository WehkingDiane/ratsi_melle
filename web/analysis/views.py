"""Views for analysis pages."""

from __future__ import annotations

from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from . import services


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
    prompt_text = str(selected_template.get("prompt_text") or "") if selected_template else ""
    errors: list[str] = []
    messages: list[str] = []

    if request.method == "POST":
        post_data = {
            "session_id": request.POST.get("session_id", ""),
            "scope": request.POST.get("scope", "session"),
            "top_numbers": request.POST.getlist("top_numbers"),
            "purpose": request.POST.get("purpose", "content_analysis"),
            "template_id": request.POST.get("template_id", ""),
            "provider_id": request.POST.get("provider_id", "none"),
            "model_name": request.POST.get("model_name", ""),
        }
        result, errors = services.run_analysis_from_form(post_data)
        if result:
            return redirect("analysis:job_detail", job_id=services.canonical_analysis_job_id(result))
        selected_session_id = post_data["session_id"]
        selected_session = services.get_session(selected_session_id) if selected_session_id else None
        scope = post_data["scope"]
        template_id = template_id or post_data["template_id"]
        selected_template = services.get_prompt_template(template_id) if template_id else None
        prompt_text = str(selected_template.get("prompt_text") or "") if selected_template else ""

    templates = [template for template in services.list_prompt_templates(scope) if template.get("is_active")]
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
            "selected_template": selected_template,
            "selected_template_id": template_id,
            "prompt_text": prompt_text,
            "purpose_options": services.analysis_purpose_options(),
            "provider_options": services.provider_options(),
            "errors": errors,
            "messages": messages,
        },
    )


def prompt_template_list(request):
    scope = request.GET.get("scope", "")
    errors: list[str] = []
    templates = services.list_prompt_templates(scope)
    return render(
        request,
        "analysis/prompt_templates.html",
        {
            "active_nav": "analysis",
            "templates": templates,
            "scope": scope,
            "errors": errors,
        },
    )


def prompt_template_form(request, template_id: str = ""):
    template = services.get_prompt_template(template_id) if template_id else None
    errors: list[str] = []
    if request.method == "POST":
        form_data = {
            "id": template_id or request.POST.get("id", ""),
            "label": request.POST.get("label", ""),
            "scope": request.POST.get("scope", "session"),
            "description": request.POST.get("description", ""),
            "prompt_text": request.POST.get("prompt_text", ""),
            "variables": request.POST.get("variables", ""),
            "visibility": request.POST.get("visibility", "private"),
            "is_active": request.POST.get("is_active", "0"),
        }
        saved, errors = services.save_prompt_template_from_form(form_data)
        if saved:
            return redirect("analysis:prompt_template_list")
        template = form_data
    return render(
        request,
        "analysis/prompt_template_form.html",
        {
            "active_nav": "analysis",
            "template": template or {"scope": "session", "visibility": "private", "is_active": True},
            "errors": errors,
        },
    )


def prompt_template_duplicate(request, template_id: str):
    if request.method != "POST":
        return redirect("analysis:prompt_template_list")
    _template, errors = services.duplicate_prompt_template(template_id)
    if errors:
        return redirect(f"{reverse('analysis:prompt_template_list')}?error=duplicate")
    return redirect("analysis:prompt_template_list")


def prompt_template_deactivate(request, template_id: str):
    if request.method == "POST":
        services.deactivate_prompt_template(template_id)
    return redirect("analysis:prompt_template_list")


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
