"""Reproducible retrieval measurements against curated source references."""

from __future__ import annotations

import re
import time
from statistics import mean


def normalize_evidence(text: str) -> str:
    """Ignore whitespace and PDF line-break hyphenation for evidence checks."""
    return re.sub(r"\s+", "", re.sub(r"-\s*\n\s*", "", text)).casefold()


def score_query(hits: list[dict], relevant: list[dict], k: int = 10) -> dict:
    """Measure known-source retrieval and passage evidence independently."""
    urls = list(dict.fromkeys(hit.get("url", "") for hit in hits))[:k]
    expected = {item["url"] for item in relevant}
    rank = next((i for i, url in enumerate(urls, 1) if url in expected), None)
    passage_found = any(
        hit.get("url") == item["url"]
        and hit.get("page_start") == item.get("page")
        and normalize_evidence(item["evidence"]) in normalize_evidence(hit.get("text", ""))
        for hit in hits[:k] for item in relevant
    )
    return {"hit_at_k": int(rank is not None), "reciprocal_rank": 1 / rank if rank else 0,
            "known_source_recall_at_k": len(expected.intersection(urls)) / len(expected),
            "evidence_hit_at_k": int(passage_found)}


def evaluate(queries, search, *, k=10):
    """Evaluate a fixed query set; errors remain explicit instead of disappearing."""
    rows = []
    for query in queries:
        start = time.perf_counter()
        hits = search(query["query"], k)
        elapsed = time.perf_counter() - start
        rows.append({"id": query["id"], "query": query["query"],
                     **score_query(hits, query["relevant"], k), "seconds": elapsed,
                     "hits": [{key: hit.get(key) for key in ("url", "page_start", "score", "doc_id")} for hit in hits]})
    if not rows:
        raise ValueError("Benchmark has no queries")
    return {"k": k, "query_count": len(rows),
            "metrics": {key: mean(row[key] for row in rows) for key in
                        ("hit_at_k", "reciprocal_rank", "known_source_recall_at_k", "evidence_hit_at_k", "seconds")},
            "queries": rows}
