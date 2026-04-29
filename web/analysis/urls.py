"""Analysis area routes."""

from __future__ import annotations

from django.urls import path
from django.views.generic import RedirectView

from . import views


app_name = "analysis"

urlpatterns = [
    path("", views.analysis_home, name="index"),
    path("starten/", views.analysis_start, name="analysis_start"),
    path("sitzungen/", views.session_list, name="session_list"),
    path("sitzungen/<str:session_id>/", views.session_detail, name="session_detail"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<str:job_id>/", views.job_detail, name="job_detail"),
    path("service/", RedirectView.as_view(pattern_name="data_tools:index", permanent=False)),
    path("service/fetch/", RedirectView.as_view(pattern_name="data_tools:service_fetch", permanent=False)),
    path("service/build/", RedirectView.as_view(pattern_name="data_tools:service_build", permanent=False)),
    path("service/jobs/status/", views.legacy_service_job_status, name="service_job_status"),
    path(
        "service/jobs/<str:job_id>/",
        RedirectView.as_view(pattern_name="data_tools:service_job_detail", permanent=False),
        name="service_job_detail",
    ),
]
