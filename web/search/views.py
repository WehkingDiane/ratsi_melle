"""Placeholder views for search."""

from __future__ import annotations

from django.shortcuts import render


def index(request):
    return render(request, "search/index.html", {"active_nav": "search"})
