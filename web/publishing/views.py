"""Placeholder views for publishing workflows."""

from __future__ import annotations

from django.shortcuts import render


def index(request):
    return render(request, "publishing/index.html", {"active_nav": "publishing"})
