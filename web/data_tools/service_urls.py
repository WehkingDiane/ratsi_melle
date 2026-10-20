"""Service navigation, maintenance and its existing job records."""

from django.urls import path

from . import views


app_name = "service"

urlpatterns = [
    path("", views.service_overview, name="index"),
    path("wartung/", views.service_maintenance, name="maintenance"),
    path("model-jobs/status/", views.service_model_history_status, name="model_history_status"),
    path("jobs/<str:job_id>/status/", views.service_job_detail_status, name="job_detail_status"),
    path("jobs/<str:job_id>/", views.service_job_detail, name="job_detail"),
]
