"""Views for document search."""

from __future__ import annotations

from django.shortcuts import render

from . import services


def index(request):
    query = request.GET.get("q", "").strip()
    source = request.GET.get("source", "ratsinfo")
    semantic_search = services.search_semantic_documents(query, source=source)
    all_results = semantic_search["results"]
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    committee = request.GET.get("committee", "").strip()
    document_type = request.GET.get("document_type", "").strip()
    results = services.filter_semantic_results(
        all_results,
        date_from=date_from,
        date_to=date_to,
        committee=committee,
        document_type=document_type,
    )
    return render(
        request,
        "search/index.html",
        {
            "active_nav": "search",
            "query": query,
            "selected_source": source if source == "landkreis" else "ratsinfo",
            "results": results,
            "unfiltered_result_count": len(all_results),
            "search_error": semantic_search["error"],
            "search_warning": semantic_search["warning"],
            "has_query": bool(query.strip()),
            "max_results": services.MAX_SEMANTIC_SEARCH_RESULTS,
            "date_from": date_from,
            "date_to": date_to,
            "selected_committee": committee,
            "selected_document_type": document_type,
            "committees": services.result_filter_options(all_results, "committee"),
            "document_types": services.result_filter_options(all_results, "document_type"),
        },
    )
