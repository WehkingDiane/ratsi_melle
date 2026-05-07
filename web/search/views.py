"""Views for document search."""

from __future__ import annotations

from django.shortcuts import render

from . import services


def index(request):
    query = request.GET.get("q", "")
    results = services.search_documents(query)
    return render(
        request,
        "search/index.html",
        {
            "active_nav": "search",
            "query": query,
            "results": results,
            "has_query": bool(query.strip()),
            "max_results": services.MAX_SEARCH_RESULTS,
        },
    )
