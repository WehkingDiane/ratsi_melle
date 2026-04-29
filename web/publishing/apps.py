"""Django app configuration for publishing workflows."""

from __future__ import annotations

from django.apps import AppConfig


class PublishingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "publishing"
