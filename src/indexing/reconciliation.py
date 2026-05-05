"""Reconciliation helpers for Qdrant vector IDs."""

from __future__ import annotations


def find_orphaned_ids(indexed_ids: set[int], current_ids: set[int]) -> set[int]:
    """Return indexed vector IDs that no longer exist in the current source set."""
    return indexed_ids - current_ids
