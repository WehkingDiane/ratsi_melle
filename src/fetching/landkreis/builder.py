"""Build the Landkreis publications database from local raw manifests."""

from __future__ import annotations

from pathlib import Path

from src.analysis.extraction_pipeline import extract_text_for_analysis
from src.fetching.landkreis.database import LandkreisPublicationStore
from src.fetching.landkreis.storage import LandkreisStorage


def build_landkreis_publications_db(
    *,
    data_root: Path,
    db_path: Path,
    max_text_chars: int = 200_000,
) -> tuple[int, int, int]:
    """Rebuild the separated Landkreis DB from stored raw manifests."""

    storage = LandkreisStorage(data_root)
    store = LandkreisPublicationStore(db_path)
    store.reset()

    publication_count = 0
    document_count = 0
    extracted_count = 0
    for manifest_path in storage.iter_manifests():
        publication = storage.load_manifest(manifest_path)
        if publication is None or not publication.publication_id:
            continue
        store.upsert_publication(publication)
        publication_count += 1
        document_count += len(publication.documents)

    rows = store.document_rows()
    for row in rows:
        local_path = row.get("local_path")
        if not local_path:
            continue
        document_path = storage.resolve_relative_path(str(local_path))
        if document_path is None or not document_path.is_file():
            continue
        result = extract_text_for_analysis(
            document_path,
            content_type=str(row.get("content_type") or ""),
            max_text_chars=max_text_chars,
        )
        store.upsert_extraction(int(row["id"]), result.to_dict())
        extracted_count += 1

    return publication_count, document_count, extracted_count
