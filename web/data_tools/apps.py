"""Django app configuration for local data tools."""

from __future__ import annotations

from django.apps import AppConfig


class DataToolsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "data_tools"
