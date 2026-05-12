"""Analysis area routes."""

from __future__ import annotations

from django.urls import path
from django.views.generic import RedirectView

from data_tools import views as data_tool_views

from . import views


app_name = "analysis"

urlpatterns = [
    path("", views.analysis_home, name="index"),
    path("prompts/", views.prompt_template_list, name="prompt_template_list"),
    path("prompts/neu/", views.prompt_template_form, name="prompt_template_new"),
    path("prompts/<str:template_id>/", views.prompt_template_form, name="prompt_template_edit"),
    path("prompts/<str:template_id>/duplizieren/", views.prompt_template_duplicate, name="prompt_template_duplicate"),
    path("prompts/<str:template_id>/deaktivieren/", views.prompt_template_deactivate, name="prompt_template_deactivate"),
    path("starten/", views.analysis_start, name="analysis_start"),
    path("sitzungen/", views.session_list, name="session_list"),
    path("sitzungen/<str:session_id>/", views.session_detail, name="session_detail"),
    path(
        "sitzungen/<str:session_id>/dokumente/<int:document_id>/pdf/",
        views.document_pdf,
        name="document_pdf",
    ),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<str:job_id>/", views.job_detail, name="job_detail"),
    path("service/", RedirectView.as_view(pattern_name="data_tools:index", permanent=False)),
    path("service/fetch/", RedirectView.as_view(pattern_name="data_tools:service_fetch", permanent=False)),
    path("service/build/", RedirectView.as_view(pattern_name="data_tools:service_build", permanent=False)),
    path("service/jobs/status/", data_tool_views.service_job_status, name="service_job_status"),
    path(
        "service/jobs/<str:job_id>/",
        RedirectView.as_view(pattern_name="data_tools:service_job_detail", permanent=False),
        name="service_job_detail",
    ),
]
