"""Publishing area routes."""

from __future__ import annotations

from django.urls import path

from . import views


app_name = "publishing"

urlpatterns = [
    path("", views.index, name="index"),
]
