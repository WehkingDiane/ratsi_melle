"""Views for document search."""

from __future__ import annotations

from django.shortcuts import render

from . import services


def index(request):
    query = request.GET.get("q", "").strip()
    source = "landkreis" if request.GET.get("source") == "landkreis" else "ratsinfo"
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    committee = request.GET.get("committee", "").strip()
    document_type = request.GET.get("document_type", "").strip()
    if source == "landkreis":
        committee = ""
        document_type = ""
    semantic_search = services.search_semantic_documents(
        query,
        source=source,
        date_from=date_from,
        date_to=date_to,
        committee=committee,
        document_type=document_type,
    )
    results = semantic_search["results"]
    filter_options = semantic_search.get("filter_options", {})
    return render(
        request,
        "search/index.html",
        {
            "active_nav": "search",
            "query": query,
            "selected_source": source,
            "results": results,
            "unfiltered_result_count": semantic_search.get("candidate_count", len(results)),
            "search_error": semantic_search["error"],
            "search_warning": semantic_search["warning"],
            "has_query": bool(query.strip()),
            "max_results": services.MAX_SEMANTIC_SEARCH_RESULTS,
            "date_from": date_from,
            "date_to": date_to,
            "selected_committee": committee,
            "selected_document_type": document_type,
            "committees": filter_options.get("committees", []),
            "document_types": filter_options.get("document_types", []),
        },
    )
