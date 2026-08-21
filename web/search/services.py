"""Document search services for the Django web UI."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from core.services import paths
from core.services.db import rows


REPO_ROOT = paths.REPO_ROOT
LOCAL_INDEX_DB = paths.LOCAL_INDEX_DB
QDRANT_DIR = paths.QDRANT_DIR

MAX_SEARCH_RESULTS = 100
MAX_SEMANTIC_SEARCH_RESULTS = 20
LANDKREIS_COLLECTION_NAME = "landkreis_publications"
RATSINFO_COLLECTION_NAME = "ratsi_documents"

_SEMANTIC_SEARCH_DEPENDENCIES = (
    ("qdrant-client", "qdrant_client"),
    ("sentence-transformers", "sentence_transformers"),
    ("fastembed", "fastembed"),
)


def _sync_paths() -> None:
    paths.REPO_ROOT = Path(REPO_ROOT)
    paths.LOCAL_INDEX_DB = Path(LOCAL_INDEX_DB)
    paths.QDRANT_DIR = Path(QDRANT_DIR)


def search_documents(query: str, *, limit: int = MAX_SEARCH_RESULTS) -> list[dict[str, Any]]:
    """Search indexed document metadata in the local SQLite database."""

    normalized_query = " ".join(query.split())
    if not normalized_query:
        return []

    _sync_paths()
    terms = normalized_query.split()
    conditions: list[str] = []
    params: list[str | int] = []
    for term in terms:
        conditions.append(
            """
            (
                LOWER(COALESCE(d.title, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.document_type, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.category, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.agenda_item, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.local_path, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.committee, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.meeting_name, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.session_id, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.date, '')) LIKE ? ESCAPE '\\'
            )
            """
        )
        pattern = f"%{_escape_like(term.lower())}%"
        params.extend([pattern] * 9)

    params.append(max(1, min(int(limit), MAX_SEARCH_RESULTS)))
    results = rows(
        paths.LOCAL_INDEX_DB,
        f"""
        SELECT
            d.id,
            d.session_id,
            d.title,
            d.category,
            d.document_type,
            d.agenda_item,
            d.local_path,
            d.content_type,
            s.date,
            s.committee,
            s.meeting_name,
            s.detail_url
        FROM documents d
        LEFT JOIN sessions s ON s.session_id = d.session_id
        WHERE {' AND '.join(conditions)}
        ORDER BY s.date DESC, s.committee ASC, d.agenda_item ASC, d.title ASC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_with_display_fields(result) for result in results]


def search_semantic_documents(
    query: str,
    *,
    limit: int = MAX_SEMANTIC_SEARCH_RESULTS,
    source: str = "ratsinfo",
) -> dict[str, Any]:
    """Search indexed document contents via the local Qdrant vector index."""

    normalized_query = " ".join(query.split())
    if not normalized_query:
        return {"results": [], "error": "", "warning": ""}
    source_config = _semantic_source_config(source)

    _sync_paths()
    dependency_error = _semantic_search_dependency_error()
    if dependency_error:
        return {"results": [], "error": dependency_error, "warning": ""}

    qdrant_dir = Path(paths.QDRANT_DIR)
    if not qdrant_dir.exists():
        return {
            "results": [],
            "error": (
                f"Der {source_config['label']}-Vektorindex fehlt. Bitte "
                f"`{source_config['build_command']}` ausfuehren."
            ),
            "warning": "",
        }

    store = None
    try:
        embedder, bm25 = _get_semantic_resources()
        store = _create_vector_store(qdrant_dir, source_config["collection_name"])
        results = store.search(
            query_dense=embedder.embed_query(normalized_query),
            query_sparse=bm25.encode_query(normalized_query),
            limit=max(1, min(int(limit), MAX_SEMANTIC_SEARCH_RESULTS)),
        )
    except Exception as exc:  # noqa: BLE001
        missing_collection_text = source_config["missing_collection_text"]
        if "doesn't exist" in str(exc) or "not found" in str(exc).lower():
            return {"results": [], "error": missing_collection_text, "warning": ""}
        return {
            "results": [],
            "error": f"Fehler bei der Vektorsuche: {exc}",
            "warning": "",
        }
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:  # noqa: BLE001 - Search results should survive cleanup errors.
                pass

    return {
        "results": [
            _with_semantic_display_fields(rank, result, source_config["source"])
            for rank, result in enumerate(results, start=1)
        ],
        "error": "",
        "warning": (
            f"Ergebnisse stammen aus der hybriden {source_config['label']}-Vektorsuche "
            "(Harrier + BM25, RRF-Rangfusion)."
        ),
    }


@lru_cache(maxsize=1)
def _get_semantic_resources():
    """Load the reusable semantic encoders once per Django process."""

    from src.analysis.bm25_sparse import BM25Encoder
    from src.analysis.embeddings import HarrierEmbedder

    return HarrierEmbedder(), BM25Encoder()


def _create_vector_store(qdrant_dir: Path, collection_name: str = RATSINFO_COLLECTION_NAME):
    """Create a request-local vector store so Qdrant locks are not cached."""

    from src.analysis.vector_store import DocumentVectorStore

    return DocumentVectorStore(qdrant_dir, collection_name=collection_name)


def _semantic_source_config(source: str) -> dict[str, str]:
    normalized = (source or "ratsinfo").strip().lower()
    if normalized == "landkreis":
        return {
            "source": "landkreis",
            "label": "Landkreis",
            "collection_name": LANDKREIS_COLLECTION_NAME,
            "build_command": "python scripts/build_landkreis_vector_index.py",
            "missing_collection_text": (
                "Der Landkreis-Vektorindex fehlt. Bitte "
                "`python scripts/build_landkreis_vector_index.py` ausfuehren."
            ),
        }
    return {
        "source": "ratsinfo",
        "label": "Ratsinfo",
        "collection_name": RATSINFO_COLLECTION_NAME,
        "build_command": "python scripts/build_vector_index.py",
        "missing_collection_text": (
            "Der Ratsinfo-Vektorindex fehlt. Bitte unter /daten/vektor/ den "
            "Vektorindex bauen oder `python scripts/build_vector_index.py` ausfuehren."
        ),
    }


def _semantic_search_dependency_error() -> str:
    missing = [package for package, module in _SEMANTIC_SEARCH_DEPENDENCIES if find_spec(module) is None]
    if not missing:
        return ""
    return (
        "Die Vektorsuche ist nicht verfügbar, weil Abhängigkeiten fehlen: "
        f"{', '.join(missing)}. Installieren mit: "
        "pip install qdrant-client sentence-transformers fastembed"
    )


def _with_display_fields(result: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(result)
    enriched["display_date"] = _format_german_date(str(enriched.get("date") or ""))
    enriched["display_type"] = (
        enriched.get("document_type")
        or enriched.get("category")
        or enriched.get("content_type")
        or "-"
    )
    return enriched


def _with_semantic_display_fields(rank: int, result: dict[str, Any], source: str = "ratsinfo") -> dict[str, Any]:
    enriched = _with_display_fields(result)
    enriched["rank"] = rank
    enriched["display_score"] = _format_rrf_score(enriched.get("score"))
    enriched["search_source"] = source
    return enriched


def _format_rrf_score(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "-"


def _format_german_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
