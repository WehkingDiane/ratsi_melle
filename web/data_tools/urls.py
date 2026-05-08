"""Routes for local data and service tools."""

from __future__ import annotations

from django.urls import path

from . import views


app_name = "data_tools"

urlpatterns = [
    path("", views.service_home, name="index"),
    path("fetch/", views.service_fetch, name="service_fetch"),
    path("build/", views.service_build, name="service_build"),
    path("vektor/", views.service_vector, name="service_vector"),
    path("jobs/status/", views.service_job_status, name="service_job_status"),
    path("jobs/<str:job_id>/status/", views.service_job_detail_status, name="service_job_detail_status"),
    path("jobs/<str:job_id>/", views.service_job_detail, name="service_job_detail"),
]
