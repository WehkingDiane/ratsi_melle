"""Views for local data and service tools."""

from __future__ import annotations

from django.http import HttpResponseBadRequest
from django.http import HttpResponseNotFound
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_safe

from core import service_jobs

from . import services


SOURCE_ACTIONS = {
    "ratsinfo": {"fetch_sessions", "fetch_session_from_index", "build_local_index", "build_online_index", "build_vector_index"},
    "landkreis": {"fetch_landkreis_publications", "build_landkreis_publications_db", "build_landkreis_vector_index"},
}

MAINTENANCE_ACTIONS = frozenset({
    "check_embedding_models", "prepare_embedding_models", "inspect_legacy_index", "apply_legacy_index",
})


def _start_job(request, command):
    action = request.POST.get("action", "")
    if action == "apply_legacy_index":
        return service_jobs.start_service_job(action, command, services.REPO_ROOT,
                                             application_context=services.confirmed_application_payload(request.POST))
    if action == "inspect_legacy_index":
        return service_jobs.start_service_job(action, command, services.REPO_ROOT,
                                             inspection_context=services.confirmed_inspection_context(request.POST))
    if action == "prepare_embedding_models":
        return service_jobs.start_service_job(
            action, command, services.REPO_ROOT,
            preparation_binding=services.confirmed_preparation_binding(request.POST),
        )
    return service_jobs.start_service_job(action, command, services.REPO_ROOT)


def service_home(request, source=None):
    if source and request.method == "POST":
        allowed = SOURCE_ACTIONS[source]
        if request.POST.get("action") not in allowed:
            return HttpResponseBadRequest("Diese Aktion gehört nicht zum gewählten Bereich.")
    return render(
        request,
        "data_tools/index.html",
        {
            "active_nav": "data", "scoped_source": source,
            "area_label": "Landkreis" if source == "landkreis" else "Bürgerinformation" if source else "Daten",
            "status": services.service_status(),
            "jobs": [job for job in service_jobs.list_service_jobs(limit=service_jobs.MAX_RETAINED_JOBS)
                     if job.action not in MAINTENANCE_ACTIONS and (not source or job.action in SOURCE_ACTIONS[source])][:20],
        },
    )


@require_safe
def service_status_detail(request):
    return render(request, "data_tools/service_status_detail.html", {
        "active_nav": "data", "inventory": services.yearly_session_inventory(),
        "status": services.service_status(),
    })


def service_fetch(request, source=None):
    if source and request.method == "POST":
        allowed = SOURCE_ACTIONS[source]
        if request.POST.get("action") not in allowed:
            return HttpResponseBadRequest("Diese Aktion gehört nicht zum gewählten Bereich.")
    errors: list[str] = []
    current_year = timezone.now().year
    if request.method == "POST":
        command, errors = services.build_service_command(
            request.POST.get("action", ""),
            request.POST,
        )
        if command:
            try:
                job = _start_job(request, command)
            except (service_jobs.ServiceJobStartError, ValueError) as error:
                errors.append(str(error))
            else:
                return redirect("data_tools:service_job_detail", job_id=job.job_id)
    return render(
        request,
        "data_tools/service_fetch.html",
        {
            "active_nav": "data", "scoped_source": source,
            "area_label": "Landkreis" if source == "landkreis" else "Bürgerinformation" if source else "Daten",
            "status": services.service_status(),
            "errors": errors,
            "current_year": current_year,
        },
    )


def service_build(request, source=None):
    if source and request.method == "POST":
        allowed = SOURCE_ACTIONS[source]
        if request.POST.get("action") not in allowed:
            return HttpResponseBadRequest("Diese Aktion gehört nicht zum gewählten Bereich.")
    errors: list[str] = []
    current_year = timezone.now().year
    if request.method == "POST":
        command, errors = services.build_service_command(
            request.POST.get("action", ""),
            request.POST,
        )
        if command:
            try:
                job = _start_job(request, command)
            except (service_jobs.ServiceJobStartError, ValueError) as error:
                errors.append(str(error))
            else:
                return redirect("data_tools:service_job_detail", job_id=job.job_id)
    return render(
        request,
        "data_tools/service_build.html",
        {
            "active_nav": "data", "scoped_source": source,
            "area_label": "Landkreis" if source == "landkreis" else "Bürgerinformation" if source else "Daten",
            "status": services.service_status(),
            "errors": errors,
            "current_year": current_year,
        },
    )


def service_vector(request, source=None):
    if source and request.method == "POST":
        allowed = SOURCE_ACTIONS[source]
        if request.POST.get("action") not in allowed:
            return HttpResponseBadRequest("Diese Aktion gehört nicht zum gewählten Bereich.")
    errors: list[str] = []
    if request.method == "POST":
        if request.POST.get("action") not in {"build_vector_index", "build_landkreis_vector_index"}:
            command, errors = None, ["Prüfungen und Modellverwaltung befinden sich unter Service → Wartung."]
        else:
            command, errors = services.build_service_command(
                request.POST.get("action", ""), request.POST,
            )
        if command:
            try:
                job = _start_job(request, command)
            except (service_jobs.ServiceJobStartError, ValueError) as error:
                errors.append(str(error))
            else:
                return redirect("data_tools:service_job_detail", job_id=job.job_id)
    return render(request, "data_tools/service_vector.html", {
        "active_nav": "data", "scoped_source": source,
            "area_label": "Landkreis" if source == "landkreis" else "Bürgerinformation" if source else "Daten", "status": services.service_status(),
        "vector_status": services.vector_index_status(),
        "landkreis_vector_status": services.landkreis_vector_index_status(), "errors": errors,
    })


@require_safe
def service_overview(request):
    """Open maintenance and settings without starting any service operation."""
    return render(request, "data_tools/service_overview.html", {
        "active_nav": "service",
        "jobs": [job for job in service_jobs.list_service_jobs(limit=service_jobs.MAX_RETAINED_JOBS)
                 if job.action in MAINTENANCE_ACTIONS][:20],
    })


def service_maintenance(request):
    """Keep explicit model preparation and legacy inspection in the Service area."""
    errors = []
    if request.method == "POST":
        if request.POST.get("action") not in MAINTENANCE_ACTIONS - {"apply_legacy_index"}:
            command, errors = None, ["Hier sind nur Wartungsaufträge verfügbar. Normale Builds stehen unter Daten."]
        else:
            command, errors = services.build_service_command(request.POST.get("action", ""), request.POST)
        if command:
            try:
                job = _start_job(request, command)
            except (service_jobs.ServiceJobStartError, ValueError) as error:
                errors.append(str(error))
            else:
                return redirect("service:job_detail", job_id=job.job_id)
    try:
        confirmation = services.preparation_confirmation()
    except (ValueError, OSError, RuntimeError):
        confirmation = None
    try:
        legacy_forms = services.legacy_inspection_forms()
    except (ValueError, OSError, RuntimeError):
        legacy_forms = []
    return render(
        request,
        "data_tools/service_maintenance.html",
        {
            "active_nav": "service",
            "status": services.service_status(),
            "preparation_confirmation": confirmation,
            "legacy_inspection_forms": legacy_forms,
            "errors": errors,
        },
    )


def service_job_detail(request, job_id: str):
    job = service_jobs.get_service_job(job_id)
    errors = []
    if request.method == "POST":
        if request.POST.get("action") != "apply_legacy_index" or request.POST.get("inspection_job_id") != job_id:
            errors.append("Übernahme muss zum angezeigten Prüfjob gehören.")
        else:
            command, errors = services.build_service_command("apply_legacy_index", request.POST)
            if command:
                try:
                    started = _start_job(request, command)
                except (service_jobs.ServiceJobStartError, ValueError) as error:
                    errors.append(str(error))
                else:
                    return redirect("service:job_detail", job_id=started.job_id)
    status = services.service_status()
    return render(
        request,
        "data_tools/service_job_detail.html",
        {
            "active_nav": "service" if job and job.action in MAINTENANCE_ACTIONS else "data",
            "job_label": "Wartungsjob" if job and job.action in MAINTENANCE_ACTIONS else "Datenjob",
            "job_detail_route": "service:job_detail" if job and job.action in MAINTENANCE_ACTIONS else "data_tools:service_job_detail",
            "job": job,
            "job_id": job_id,
            "legacy_report": services.inspection_result(job),
            "model_job_evidence": services.model_job_detail(job, status["embedding_models"]),
            "application_confirmation": services.application_confirmation(job) if job and job.action == "inspect_legacy_index" else None,
            "errors": errors,
            "status": status,
        },
    )


def service_status(request):
    """Return freshly calculated service status values for manual refreshes."""

    return JsonResponse({"status": services.service_status()})


def service_model_history_status(request):
    """Refresh model evidence without opening Qdrant or executing a check job."""
    models = services.embedding_model_status()
    return JsonResponse({"history": services.model_job_history(models)})


def service_job_status(request):
    active = []
    for job in service_jobs.active_service_jobs():
        maintenance = job.action in MAINTENANCE_ACTIONS
        entry = job.to_dict()
        entry.update(
            area="service" if maintenance else "data",
            detail_url=reverse("service:job_detail" if maintenance else "data_tools:service_job_detail",
                               kwargs={"job_id": job.job_id}),
        )
        active.append(entry)
    recent = [job.to_dict() for job in service_jobs.list_service_jobs(limit=5)]
    return JsonResponse({"active": active, "recent": recent})


def service_job_detail_status(request, job_id: str):
    job = service_jobs.get_service_job(job_id)
    if job is None:
        return HttpResponseNotFound()
    models = services.embedding_model_status()
    return JsonResponse({"job": job.to_dict(), "legacy_report": services.inspection_result(job),
                         "model_job_evidence": services.model_job_detail(job, models)})
