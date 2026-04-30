"""Placeholder views for local UI settings."""

from __future__ import annotations

from django.shortcuts import render


def index(request):
    return render(request, "settings_ui/index.html", {"active_nav": "settings"})
