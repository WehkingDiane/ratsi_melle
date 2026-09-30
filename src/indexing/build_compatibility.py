"""Read-only compatibility gate before any vector build changes Qdrant."""

from __future__ import annotations

import json

from src.config.index_compatibility import IndexCompatibility
from src.qdrant_connection import QdrantConnection


class IndexBuildCompatibilityError(ValueError):
    """An existing nonempty collection cannot be continued with this contract."""


def check_build_compatibility(
    connection: QdrantConnection, client, collection: str, compatibility: IndexCompatibility,
) -> str:
    """Return existing provenance, rejecting missing or different release contracts."""

    names = {item.name for item in client.get_collections().collections}
    if collection not in names or client.count(collection_name=collection, exact=True).count == 0:
        return "native"
    stored = connection.read_index_compatibility(collection)
    if stored is None:
        raise IndexBuildCompatibilityError(
            f"Bestehende Collection {collection} hat keinen gueltigen Kompatibilitaetsmarker."
        )
    if stored != compatibility:
        raise IndexBuildCompatibilityError(
            f"Bestehende Collection {collection} hat einen anderen Modell- oder Pipelinevertrag."
        )
    try:
        marker = json.loads(connection.release_path(collection).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise IndexBuildCompatibilityError("Freigabemarker ist nicht lesbar.") from error
    provenance = marker.get("provenance", "native")
    if provenance not in {"native", "legacy_verified"}:
        raise IndexBuildCompatibilityError("Freigabemarker hat eine ungueltige Herkunft.")
    return provenance
