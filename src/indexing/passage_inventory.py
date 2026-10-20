"""Compact passage inventory shared by builds, checks and status pages."""

from __future__ import annotations

from collections import defaultdict


INVENTORY_FIELDS = [
    "document_id", "generation", "fingerprint", "chunk_count", "chunk_index", "committed",
]


def indexed_document_ids(payloads: dict) -> set[int]:
    """Return all valid parent IDs, including incomplete/uncommitted documents."""
    return {p["document_id"] for p in payloads.values() if type(p.get("document_id")) is int}


def complete_document_ids(payloads: dict) -> set[int]:
    """Find documents with at least one fully committed passage generation."""
    groups = defaultdict(list)
    for payload in payloads.values():
        parent = payload.get("document_id")
        if type(parent) is int:
            generation = payload.get("generation", payload.get("fingerprint"))
            groups[parent, generation].append(payload)
    complete = set()
    for (parent, _), parts in groups.items():
        count = parts[0].get("chunk_count")
        if (type(count) is not int or count < 1 or len(parts) != count
                or not all(p.get("committed") is True and p.get("chunk_count") == count for p in parts)):
            continue
        # Older inventories did not request chunk_index. When supplied, verify
        # every distinct position rather than accepting duplicate/missing chunks.
        if any("chunk_index" in p for p in parts) and {
            p.get("chunk_index") for p in parts
        } != set(range(count)):
            continue
        complete.add(parent)
    return complete


def stale_partial_point_ids(payloads: dict) -> set[int]:
    """Find incomplete generations removable beside a complete document version."""
    complete = complete_document_ids(payloads)
    groups = defaultdict(dict)
    for point_id, payload in payloads.items():
        parent = payload.get("document_id")
        if type(parent) is int and parent in complete:
            generation = payload.get("generation", payload.get("fingerprint"))
            groups[parent, generation][point_id] = payload
    return {
        point_id
        for (parent, _), parts in groups.items()
        if parent not in complete_document_ids(parts)
        for point_id in parts
    }
