"""Read-only evidence for a one-time legacy Qdrant index migration."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from typing import Callable

from src.config.index_compatibility import IndexCompatibility, current_index_compatibility
from src.indexing.id_strategy import stable_document_id
from src.paths import LANDKREIS_DATA_DIR, LANDKREIS_PUBLICATIONS_DB, LOCAL_INDEX_DB
from src.qdrant_connection import QdrantConnection


SAMPLE_SIZE = 32
DENSE_ABS_TOLERANCE = 1e-4
DENSE_REL_TOLERANCE = 1e-4
SPARSE_ABS_TOLERANCE = 1e-4
SPARSE_REL_TOLERANCE = 1e-4

_COLLECTIONS = frozenset({"ratsi_passages", "ratsi_documents", "landkreis_publications"})


class LegacyInspectionError(ValueError):
    """A legacy collection lacks sufficient evidence for a safe migration."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class LegacyInspection:
    """Read-only evidence bound to one target, collection and point-ID set."""

    target: str
    target_sha256: str
    collection: str
    point_count: int
    point_ids_sha256: str
    sample_ids: tuple[int, ...]
    compatibility: IndexCompatibility


def select_sample_ids(collection: str, point_ids: list[int], compatibility: IndexCompatibility) -> tuple[int, ...]:
    """Choose up to 32 IDs by a stable hash of collection, contract and ID."""

    contract = json.dumps(compatibility.as_dict(), sort_keys=True, separators=(",", ":"))
    ranked = (
        (sha256(f"{collection}\0{contract}\0{point_id}".encode()).digest(), point_id)
        for point_id in point_ids
    )
    return tuple(point_id for _, point_id in sorted(ranked)[:SAMPLE_SIZE])


def _point_ids_sha256(point_ids: list[int]) -> str:
    return sha256(json.dumps(sorted(point_ids), separators=(",", ":")).encode()).hexdigest()


def target_sha256(connection: QdrantConnection) -> str:
    """Bind evidence to the full server URL or resolved local store path."""

    identity = "url\0" + connection.url if connection.url else "path\0" + str(connection.path.resolve())
    return sha256(identity.encode()).hexdigest()


def _check_hints(payload: dict, compatibility: IndexCompatibility) -> None:
    if "model" in payload and payload["model"] != compatibility.dense_model_id:
        raise LegacyInspectionError("model_mismatch", "Vorhandener Modellhinweis widerspricht dem aktiven Vertrag.")
    if "pipeline_version" in payload and payload["pipeline_version"] != compatibility.pipeline_version:
        raise LegacyInspectionError("pipeline_mismatch", "Vorhandener Pipelinehinweis widerspricht dem aktiven Vertrag.")
    if "index_compatibility" in payload:
        try:
            stored = IndexCompatibility.from_dict(payload["index_compatibility"])
        except (TypeError, ValueError) as error:
            raise LegacyInspectionError("contract_invalid", "Vorhandener Kompatibilitaetsdatensatz ist ungueltig.") from error
        if stored != compatibility:
            raise LegacyInspectionError("contract_mismatch", "Vorhandener Kompatibilitaetsdatensatz widerspricht dem aktiven Vertrag.")


def _check_marker(connection: QdrantConnection, collection: str, compatibility: IndexCompatibility) -> dict | None:
    path = connection.release_path(collection)
    if path.is_symlink():
        raise LegacyInspectionError("marker_invalid", "Freigabemarker ist kein regulaeres File.")
    if not path.exists():
        return None
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise LegacyInspectionError("marker_invalid", "Vorhandener Freigabemarker ist unlesbar.") from error
    if not isinstance(marker, dict):
        raise LegacyInspectionError("marker_invalid", "Vorhandener Freigabemarker ist ungueltig.")
    if connection.url and marker.get("url_sha256") != sha256(connection.url.encode()).hexdigest():
        raise LegacyInspectionError("marker_target_mismatch", "Freigabemarker gehoert zu einem anderen Qdrant-Ziel.")
    if "collection" in marker and marker["collection"] != collection:
        raise LegacyInspectionError("marker_collection_mismatch", "Freigabemarker gehoert zu einer anderen Collection.")
    _check_hints(marker, compatibility)
    return marker


def _check_schema(info, compatibility: IndexCompatibility) -> None:
    from qdrant_client.models import Distance

    try:
        params = info.config.params
        dense = params.vectors
        sparse = params.sparse_vectors
        valid = (
            isinstance(dense, dict) and set(dense) == {"harrier"}
            and dense["harrier"].size == compatibility.vector_dimension
            and dense["harrier"].distance == Distance.COSINE
            and isinstance(sparse, dict) and set(sparse) == {"bm25"}
            and sparse["bm25"].modifier is None
            and (sparse["bm25"].index is None
                 or sparse["bm25"].index.datatype is None)
        )
    except (AttributeError, KeyError, TypeError):
        valid = False
    if not valid:
        raise LegacyInspectionError("schema_mismatch", "Qdrant-Vektorschema entspricht nicht dem aktiven Vertrag.")


def _scan_point_ids(client, collection: str, compatibility: IndexCompatibility) -> list[int]:
    ids: list[int] = []
    offset = None
    seen: set[int] = set()
    while True:
        records, next_offset = client.scroll(
            collection_name=collection, with_payload=True, with_vectors=False,
            limit=256, offset=offset,
        )
        for record in records:
            if type(record.id) is not int or record.id in seen:
                raise LegacyInspectionError("point_ids_invalid", "Punkt-IDs sind ungueltig oder doppelt vorhanden.")
            if not isinstance(record.payload, dict):
                raise LegacyInspectionError("payload_missing", "Ein Punkt besitzt kein pruefbares Payload.")
            _check_hints(record.payload, compatibility)
            if collection == "ratsi_passages" and record.payload.get("committed") is not True:
                raise LegacyInspectionError("text_unavailable", "Passage ist nicht bestaetigt.")
            seen.add(record.id)
            ids.append(record.id)
        if next_offset is None:
            return ids
        if next_offset == offset or not records:
            raise LegacyInspectionError("scroll_incomplete", "Qdrant-Punktliste ist unvollstaendig.")
        offset = next_offset


def _sparse_pairs(vector) -> list[tuple[int, float]]:
    if isinstance(vector, dict):
        indices, values = vector.get("indices"), vector.get("values")
    else:
        indices, values = getattr(vector, "indices", None), getattr(vector, "values", None)
    if not isinstance(indices, list) or not isinstance(values, list) or len(indices) != len(values):
        raise LegacyInspectionError("vector_invalid", "Sparse-Vektor ist unvollstaendig.")
    if any(type(index) is not int or index < 0 for index in indices):
        raise LegacyInspectionError("vector_invalid", "Sparse-Indizes sind ungueltig.")
    if len(set(indices)) != len(indices):
        raise LegacyInspectionError("vector_invalid", "Sparse-Indizes sind nicht eindeutig.")
    try:
        pairs = sorted((index, float(value)) for index, value in zip(indices, values, strict=True))
    except (TypeError, ValueError) as error:
        raise LegacyInspectionError("vector_invalid", "Sparse-Werte sind ungueltig.") from error
    if not all(math.isfinite(value) for _, value in pairs):
        raise LegacyInspectionError("vector_invalid", "Sparse-Werte sind nicht endlich.")
    return pairs


def _compare_vectors(stored: dict, recalculated: dict, dimension: int) -> None:
    dense = stored.get("harrier")
    expected_dense = recalculated.get("dense_vector")
    if not isinstance(dense, list) or not isinstance(expected_dense, list) or len(dense) != dimension or len(expected_dense) != dimension:
        raise LegacyInspectionError("vector_invalid", "Dense-Vektor fehlt oder hat die falsche Dimension.")
    try:
        dense_equal = all(
            math.isfinite(float(old)) and math.isfinite(float(new))
            and math.isclose(float(old), float(new), rel_tol=DENSE_REL_TOLERANCE, abs_tol=DENSE_ABS_TOLERANCE)
            for old, new in zip(dense, expected_dense, strict=True)
        )
    except (TypeError, ValueError) as error:
        raise LegacyInspectionError("vector_invalid", "Dense-Vektor enthaelt ungueltige Werte.") from error
    if not dense_equal:
        raise LegacyInspectionError("dense_mismatch", "Dense-Vektor stimmt nicht mit der Neuberechnung ueberein.")
    old_sparse = _sparse_pairs(stored.get("bm25"))
    new_sparse = _sparse_pairs(recalculated.get("sparse_vector"))
    if [index for index, _ in old_sparse] != [index for index, _ in new_sparse]:
        raise LegacyInspectionError("sparse_indices_mismatch", "Sparse-Indizes stimmen nicht mit der Neuberechnung ueberein.")
    if not all(math.isclose(old, new, rel_tol=SPARSE_REL_TOLERANCE, abs_tol=SPARSE_ABS_TOLERANCE)
               for (_, old), (_, new) in zip(old_sparse, new_sparse, strict=True)):
        raise LegacyInspectionError("sparse_values_mismatch", "Sparse-Werte stimmen nicht mit der Neuberechnung ueberein.")


class _TextResolver:
    def __init__(self, ratsinfo_db: Path, landkreis_db: Path, landkreis_data_root: Path) -> None:
        self.ratsinfo_db = ratsinfo_db
        self.landkreis_db = landkreis_db
        self.landkreis_data_root = landkreis_data_root
        self._rows: dict[str, dict[int, dict]] = {}

    def _load_rows(self, collection: str) -> dict[int, dict]:
        if collection not in self._rows:
            if collection == "ratsi_documents":
                from scripts.build_vector_index import _load_documents
                try:
                    rows = _load_documents(self.ratsinfo_db, read_only=True)
                except (OSError, RuntimeError, sqlite3.Error) as error:
                    raise LegacyInspectionError("source_missing", "Ratsinfo-Quelldatenbank ist nicht lesbar.") from error
                identify = lambda row: stable_document_id(
                    str(row.get("session_id") or ""), str(row.get("url") or ""),
                    str(row.get("agenda_item") or ""),
                )
            else:
                from scripts.build_landkreis_vector_index import _load_documents, _stable_landkreis_qdrant_id
                try:
                    rows = _load_documents(self.landkreis_db, read_only=True)
                except (OSError, RuntimeError, sqlite3.Error) as error:
                    raise LegacyInspectionError("source_missing", "Landkreis-Quelldatenbank ist nicht lesbar.") from error
                identify = lambda row: _stable_landkreis_qdrant_id(
                    str(row.get("publication_id") or ""), str(row.get("url") or ""),
                )
            result: dict[int, dict] = {}
            for row in rows:
                point_id = identify(row)
                if point_id in result:
                    raise LegacyInspectionError("source_ambiguous", "Quellzeilen besitzen dieselbe Punkt-ID.")
                result[point_id] = row
            self._rows[collection] = result
        return self._rows[collection]

    def __call__(self, collection: str, point_id: int, payload: dict) -> str:
        if collection == "ratsi_passages":
            text = payload.get("text")
            if payload.get("committed") is not True or not isinstance(text, str) or not text:
                raise LegacyInspectionError("text_unavailable", "Passage besitzt keinen bestaetigten Originaltext.")
            if payload.get("snippet") != text[:500]:
                raise LegacyInspectionError("text_mismatch", "Passage-Snippet passt nicht zum Originaltext.")
            return text
        row = self._load_rows(collection).get(point_id)
        if row is None or str(payload.get("url") or "") != str(row.get("url") or ""):
            raise LegacyInspectionError("source_missing", "Urspruengliche Quellzeile ist nicht eindeutig rekonstruierbar.")
        if collection == "ratsi_documents":
            from scripts.build_vector_index import _get_document_text
            from src.indexing.payload_builder import build_document_payload
            text = _get_document_text(row)
            expected_snippet = build_document_payload(row, search_text=text)["snippet"]
        else:
            from scripts.build_landkreis_vector_index import _build_payload, _document_text
            text = _document_text(row)
            expected_snippet = _build_payload(row, data_root=self.landkreis_data_root, search_text=text)["snippet"]
        if not text or payload.get("snippet") != expected_snippet:
            raise LegacyInspectionError("text_mismatch", "Gespeicherter Textbeleg passt nicht zum rekonstruierten Embedding-Text.")
        return text


def inspect_legacy_collection(
    connection: QdrantConnection,
    client,
    collection: str,
    *,
    ratsinfo_db: Path = LOCAL_INDEX_DB,
    landkreis_db: Path = LANDKREIS_PUBLICATIONS_DB,
    landkreis_data_root: Path = LANDKREIS_DATA_DIR,
    vectorizer_factory: Callable | None = None,
) -> LegacyInspection:
    """Deep-check local models and verify a deterministic Qdrant sample without writes."""

    if collection not in _COLLECTIONS:
        raise ValueError("Unknown legacy collection")
    from src.config.embedding_model_status import PreparedModelUnavailableError

    try:
        compatibility = current_index_compatibility(deep=True)
    except PreparedModelUnavailableError as error:
        raise LegacyInspectionError("model_unavailable", "Aktiver lokaler Modellbestand ist nicht vollstaendig geprueft.") from error
    marker = _check_marker(connection, collection, compatibility)
    if collection not in {item.name for item in client.get_collections().collections}:
        raise LegacyInspectionError("collection_missing", "Collection ist nicht vorhanden.")
    info = client.get_collection(collection_name=collection)
    _check_schema(info, compatibility)
    point_count = client.count(collection_name=collection, exact=True).count
    if type(point_count) is not int or point_count < 1:
        raise LegacyInspectionError("collection_empty", "Collection ist leer oder nicht lesbar.")
    if marker is not None:
        marked_count = marker.get("points_count")
        if (connection.url and type(marked_count) is not int) or (
            marked_count is not None and (type(marked_count) is not int or marked_count != point_count)
        ):
            raise LegacyInspectionError("marker_count_mismatch", "Freigabemarker und Qdrant-Punktzahl stimmen nicht ueberein.")
    ids = _scan_point_ids(client, collection, compatibility)
    if len(ids) != point_count:
        raise LegacyInspectionError("point_count_mismatch", "Qdrant-Punktzahl und Punktliste stimmen nicht ueberein.")
    sample_ids = select_sample_ids(collection, ids, compatibility)
    records = client.retrieve(collection_name=collection, ids=list(sample_ids),
                              with_payload=True, with_vectors=True)
    selected = {record.id: record for record in records}
    if len(selected) != len(sample_ids) or set(selected) != set(sample_ids):
        raise LegacyInspectionError("sample_incomplete", "Deterministische Stichprobe ist unvollstaendig.")
    resolver = _TextResolver(ratsinfo_db, landkreis_db, landkreis_data_root)
    texts = []
    for point_id in sample_ids:
        record = selected[point_id]
        if not isinstance(record.payload, dict) or not isinstance(record.vector, dict):
            raise LegacyInspectionError("sample_incomplete", "Stichprobenpunkt ist unvollstaendig.")
        _check_hints(record.payload, compatibility)
        texts.append(resolver(collection, point_id, record.payload))
    if vectorizer_factory is None:
        from src.analysis.bm25_sparse import BM25Encoder
        from src.analysis.embeddings import HarrierEmbedder
        from src.indexing.vectorizer import HybridVectorizer
        vectorizer_factory = lambda: HybridVectorizer(HarrierEmbedder(), BM25Encoder())
    recalculated = vectorizer_factory().encode_documents(texts)
    if len(recalculated) != len(sample_ids):
        raise LegacyInspectionError("sample_incomplete", "Neuberechnung der Stichprobe ist unvollstaendig.")
    for point_id, vectors in zip(sample_ids, recalculated, strict=True):
        _compare_vectors(selected[point_id].vector, vectors, compatibility.vector_dimension)
    current_ids = _scan_point_ids(client, collection, compatibility)
    if _point_ids_sha256(current_ids) != _point_ids_sha256(ids) or len(current_ids) != point_count:
        raise LegacyInspectionError("collection_changed", "Collection wurde waehrend der Pruefung veraendert.")
    return LegacyInspection(
        target=connection.target, target_sha256=target_sha256(connection),
        collection=collection, point_count=point_count,
        point_ids_sha256=_point_ids_sha256(ids), sample_ids=sample_ids,
        compatibility=compatibility,
    )
