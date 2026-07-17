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
    _remove_existing_database(db_path)
    store = LandkreisPublicationStore(db_path)
    store.initialize()

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
    extracted_publication_ids: set[str] = set()
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
        publication_id = store.upsert_extraction(
            int(row["id"]),
            result.to_dict(),
            refresh_fts=False,
        )
        if publication_id:
            extracted_publication_ids.add(publication_id)
        extracted_count += 1

    store.refresh_publication_fts(extracted_publication_ids)
    return publication_count, document_count, extracted_count


def _remove_existing_database(db_path: Path) -> None:
    """Remove an existing generated SQLite DB and sidecars before rebuilding."""

    for path in (db_path, db_path.with_name(f"{db_path.name}-wal"), db_path.with_name(f"{db_path.name}-shm")):
        if path.exists():
            path.unlink()
