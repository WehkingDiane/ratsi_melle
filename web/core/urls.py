"""Analysis area routes."""

from __future__ import annotations

from django.urls import path

from . import views


app_name = "analysis"

urlpatterns = [
    path("", views.analysis_home, name="index"),
    path("sitzungen/", views.session_list, name="session_list"),
    path("sitzungen/<str:session_id>/", views.session_detail, name="session_detail"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<str:job_id>/", views.job_detail, name="job_detail"),
]
