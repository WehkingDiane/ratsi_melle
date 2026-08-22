"""Views for analysis pages."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import content_disposition_header

from . import services
from .markdown_preview import render_markdown_preview


LIST_PAGE_SIZE = 20


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
    all_sessions = services.list_sessions()
    query = request.GET.get("q", "").strip()
    committee = request.GET.get("committee", "").strip()
    year = request.GET.get("year", "").strip()
    sessions = [
        session for session in all_sessions
        if _matches_session_filters(session, query=query, committee=committee, year=year)
    ]
    page_obj = Paginator(sessions, LIST_PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "analysis/session_list.html",
        {
            "active_nav": "analysis",
            "sessions": list(page_obj.object_list),
            "page_obj": page_obj,
            "result_count": len(sessions),
            "query": query,
            "selected_committee": committee,
            "selected_year": year,
            "committees": sorted({str(item.get("committee") or "") for item in all_sessions if item.get("committee")}),
            "years": sorted({_session_year(item) for item in all_sessions if _session_year(item)}, reverse=True),
            "filter_query": _query_without_page(request),
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


def document_pdf(request, session_id: str, document_id: int):
    document = services.get_local_pdf_document(session_id, document_id)
    if document is None:
        raise Http404("PDF-Dokument nicht gefunden.")

    path = document["path"]
    response = FileResponse(open(path, "rb"), content_type=document["content_type"])
    response["Content-Disposition"] = content_disposition_header(False, path.name)
    return response


def analysis_start(request):
    selected_session_id = request.GET.get("session_id", "")
    selected_session = services.get_session(selected_session_id) if selected_session_id else None
    scope = request.POST.get("scope", request.GET.get("scope", "session"))
    if scope not in {"session", "tops"}:
        scope = "session"
    purpose = request.POST.get("purpose", request.GET.get("purpose", services.default_purpose_for_scope(scope)))
    provider_id = request.POST.get("provider_id", request.GET.get("provider_id", services.default_provider_id()))
    model_name = request.POST.get("model_name", request.GET.get("model_name", ""))
    template_id = request.POST.get("template_id", request.GET.get("template_id", ""))
    if not template_id:
        template_id = services.default_template_id(scope, purpose)
    selected_template = services.get_prompt_template(template_id) if template_id else None
    prompt_text = str(selected_template.get("prompt_text") or "") if selected_template else ""
    errors: list[str] = []
    messages: list[str] = []

    if request.method == "POST":
        post_data = {
            "session_id": request.POST.get("session_id", ""),
            "scope": request.POST.get("scope", "session"),
            "top_numbers": request.POST.getlist("top_numbers"),
            "purpose": request.POST.get("purpose", services.default_purpose_for_scope(scope)),
            "template_id": request.POST.get("template_id", ""),
            "provider_id": request.POST.get("provider_id", services.default_provider_id()),
            "model_name": request.POST.get("model_name", ""),
        }
        result, errors = services.run_analysis_from_form(post_data)
        if result:
            return redirect("analysis:job_detail", job_id=services.canonical_analysis_job_id(result))
        selected_session_id = post_data["session_id"]
        selected_session = services.get_session(selected_session_id) if selected_session_id else None
        scope = post_data["scope"]
        purpose = post_data["purpose"]
        provider_id = post_data["provider_id"]
        model_name = post_data["model_name"]
        template_id = post_data["template_id"] or services.default_template_id(scope, purpose)
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
            "selected_purpose": purpose,
            "selected_provider_id": provider_id,
            "model_name": model_name,
            "default_model_name": "gpt-5.6-terra",
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
            "allow_update": bool(template_id),
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
    all_jobs = services.list_analysis_outputs()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    jobs = [job for job in all_jobs if _matches_job_filters(job, query=query, status=status)]
    page_obj = Paginator(jobs, LIST_PAGE_SIZE).get_page(request.GET.get("page"))
    status_options = sorted(
        {
            (str(job.get("status") or ""), str(job.get("display_status") or job.get("status") or "-"))
            for job in all_jobs
            if job.get("status")
        },
        key=lambda item: item[1].casefold(),
    )
    return render(
        request,
        "analysis/job_list.html",
        {
            "active_nav": "analysis",
            "jobs": list(page_obj.object_list),
            "page_obj": page_obj,
            "result_count": len(jobs),
            "query": query,
            "selected_status": status,
            "status_options": status_options,
            "filter_query": _query_without_page(request),
        },
    )


def answer_reader(request):
    """Show readable AI answers without the technical job context."""

    answers = []
    for job in services.list_analysis_outputs():
        answer_markdown, has_readable_analysis = _job_markdown_preview(job)
        if not has_readable_analysis:
            continue
        answer = dict(job)
        answer["answer_markdown"] = answer_markdown
        answers.append(answer)

    requested_job_id = request.GET.get("job_id", "").strip()
    selected_job = next(
        (
            answer
            for answer in answers
            if requested_job_id
            and requested_job_id
            in {
                str(answer.get("job_id") or ""),
                str(answer.get("display_job_id") or ""),
            }
        ),
        None,
    )
    if selected_job is None and answers:
        selected_job = answers[0]

    return render(
        request,
        "analysis/answer_reader.html",
        {
            "active_nav": "analysis",
            "answers": answers,
            "selected_job": selected_job,
            "answer_preview": render_markdown_preview(
                str(selected_job.get("answer_markdown") or "") if selected_job else ""
            ),
        },
    )


def job_detail(request, job_id: str):
    job = services.get_analysis_output(job_id)
    errors: list[str] = []
    if request.method == "POST" and job:
        _result, errors = services.execute_prepared_analysis(
            job_id,
            request.POST.get("provider_id", ""),
            request.POST.get("model_name", ""),
        )
        job = services.get_analysis_output(job_id)
    preview_text, has_readable_analysis = _job_markdown_preview(job)
    provider_options = [
        option for option in services.provider_options() if option["value"] != "none"
    ]
    stored_model_name = str(job.get("model_name") or "") if job else ""
    provider_sentinels = {"none"} | {option["value"] for option in provider_options}
    return render(
        request,
        "analysis/job_detail.html",
        {
            "active_nav": "analysis",
            "job": job,
            "job_id": job_id,
            "markdown_preview": render_markdown_preview(preview_text),
            "has_readable_analysis": has_readable_analysis,
            "provider_options": provider_options,
            "retry_model_name": "" if stored_model_name in provider_sentinels else stored_model_name,
            "errors": errors,
        },
    )


def _job_markdown_preview(job: dict | None) -> tuple[str, bool]:
    """Prefer the readable KI section over the full analysis context."""

    markdown = str(job.get("markdown") or "") if job else ""
    marker = "## KI-Analyse"
    if marker not in markdown:
        return markdown, False
    _context, _marker, analysis = markdown.partition(marker)
    if analysis.strip():
        return analysis.strip(), True
    return markdown, False


def _matches_session_filters(session: dict, *, query: str, committee: str, year: str) -> bool:
    searchable = " ".join(
        str(session.get(key) or "")
        for key in ("session_id", "meeting_name", "committee", "location")
    ).casefold()
    return (
        (not query or query.casefold() in searchable)
        and (not committee or str(session.get("committee") or "") == committee)
        and (not year or _session_year(session) == year)
    )


def _session_year(session: dict) -> str:
    return str(session.get("date") or "")[:4]


def _matches_job_filters(job: dict, *, query: str, status: str) -> bool:
    searchable = " ".join(
        str(job.get(key) or "")
        for key in ("job_id", "session_id", "purpose", "output_type", "model_name")
    ).casefold()
    return (
        (not query or query.casefold() in searchable)
        and (not status or str(job.get("status") or "") == status)
    )


def _query_without_page(request) -> str:
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()
