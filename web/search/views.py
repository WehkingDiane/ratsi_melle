"""Views for document search."""

from __future__ import annotations

from django.shortcuts import render

from . import services


def index(request):
    query = request.GET.get("q", "")
    semantic_search = services.search_semantic_documents(query)
    return render(
        request,
        "search/index.html",
        {
            "active_nav": "search",
            "query": query,
            "results": semantic_search["results"],
            "search_error": semantic_search["error"],
            "search_warning": semantic_search["warning"],
            "has_query": bool(query.strip()),
            "max_results": services.MAX_SEMANTIC_SEARCH_RESULTS,
        },
    )
