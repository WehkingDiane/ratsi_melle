"""Views for local data and service tools."""

from __future__ import annotations

from django.http import HttpResponseNotFound
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from core import service_jobs
from core import services


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


def service_job_detail_status(request, job_id: str):
    job = service_jobs.get_service_job(job_id)
    if job is None:
        return HttpResponseNotFound()
    return JsonResponse({"job": job.to_dict()})
