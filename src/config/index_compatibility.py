"""Shared model contract recorded with a Qdrant index generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from src.config.embedding_model_manifest import validate_commit_sha, validate_model_id
from src.config.embedding_model_status import (
    EmbeddingModelReadiness,
    PreparedModelUnavailableError,
    check_embedding_model_status,
)
from src.config.embedding_models import (
    BM25_MODEL,
    EMBEDDING_PIPELINE_VERSION,
    HARRIER_MODEL,
    HARRIER_TOKENIZER,
)
from src.config.settings import load_embedding_model_settings


INDEX_COMPATIBILITY_PAYLOAD_KEY: Final[str] = "index_compatibility"


@dataclass(frozen=True, slots=True)
class IndexCompatibility:
    """Identity of the models and pipeline that produced Qdrant vectors."""

    dense_model_id: str
    dense_revision: str
    sparse_model_id: str
    sparse_revision: str
    tokenizer_model_id: str
    tokenizer_revision: str
    manifest_sha256: str
    vector_dimension: int
    pipeline_version: str

    def __post_init__(self) -> None:
        for model_id in (self.dense_model_id, self.sparse_model_id, self.tokenizer_model_id):
            validate_model_id(model_id)
        for revision in (self.dense_revision, self.sparse_revision, self.tokenizer_revision):
            validate_commit_sha(revision)
        if (not isinstance(self.manifest_sha256, str)
                or len(self.manifest_sha256) != 64
                or any(c not in "0123456789abcdef" for c in self.manifest_sha256)):
            raise ValueError("Manifest hash must be a lowercase SHA-256 digest")
        if type(self.vector_dimension) is not int or self.vector_dimension < 1:
            raise ValueError("Vector dimension must be a positive integer")
        if not isinstance(self.pipeline_version, str) or not self.pipeline_version.strip():
            raise ValueError("Pipeline version must be a nonempty string")

    def as_dict(self) -> dict[str, str | int]:
        """Return the exact JSON-compatible compatibility fields."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: object) -> IndexCompatibility:
        """Parse a stored record, rejecting missing or unknown fields."""

        if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
            raise ValueError("Index compatibility fields do not match the schema")
        return cls(**payload)


def with_index_compatibility(payload: dict, compatibility: IndexCompatibility) -> dict:
    """Add the shared model contract to a newly vectorized point payload."""

    return {**payload, INDEX_COMPATIBILITY_PAYLOAD_KEY: compatibility.as_dict()}


# Explicit operating decision, 2026-11-03: retain the existing passage index
# after the Windows/XPU comparison (128 passages). This is not a blanket waiver
# for library upgrades. Keep complete contracts so future model changes cannot
# accidentally inherit this exception through updated model constants.
_ACCEPTED_PASSAGE_CONTRACTS = frozenset(
    IndexCompatibility(
        dense_model_id="microsoft/harrier-oss-v1-0.6b",
        dense_revision="f9b9dc8d367d443f2479d27aa5d8d2850c0774ee",
        sparse_model_id="Qdrant/bm25",
        sparse_revision="22b8d2af71a76161e18dd432d2cee0eefa66e412",
        tokenizer_model_id="microsoft/harrier-oss-v1-0.6b",
        tokenizer_revision="f9b9dc8d367d443f2479d27aa5d8d2850c0774ee",
        manifest_sha256=manifest_hash, vector_dimension=1024, pipeline_version="passages-1",
    ) for manifest_hash in (
        "478077ff73fbf75e6e4e1660de2c9c6d8cbbbab6d9864c7ffe06ee87d34314c9",
        "b126904ecc150d7c7a72490a8cb0fcee969ad925db0d21f75d8b6bd67261176d",
    )
)


def index_contracts_compatible(stored: IndexCompatibility | None, active: IndexCompatibility,
                               collection: str) -> bool:
    """Accept exact contracts or the explicitly approved Ratsinfo library pair."""
    if stored == active:
        return True
    return (collection == "ratsi_passages" and stored in _ACCEPTED_PASSAGE_CONTRACTS
            and active in _ACCEPTED_PASSAGE_CONTRACTS)


def current_index_compatibility(models_dir: Path | None = None, *, deep: bool = False) -> IndexCompatibility:
    """Build the active contract only after offline inventory validation."""

    if models_dir is None:
        models_dir = load_embedding_model_settings().models_dir
    status = check_embedding_model_status(models_dir, deep=deep)
    if status.state is not EmbeddingModelReadiness.READY or status.manifest_sha256 is None:
        raise PreparedModelUnavailableError(
            "Lokales Embedding-Modell fehlt, ist unvollstaendig oder inkompatibel. "
            "Vorbereitung: python scripts/prepare_embedding_models.py --download"
        )
    return IndexCompatibility(
        dense_model_id=HARRIER_MODEL.model_id,
        dense_revision=HARRIER_MODEL.revision,
        sparse_model_id=BM25_MODEL.model_id,
        sparse_revision=BM25_MODEL.revision,
        tokenizer_model_id=HARRIER_TOKENIZER.model_id,
        tokenizer_revision=HARRIER_TOKENIZER.revision,
        manifest_sha256=status.manifest_sha256,
        vector_dimension=HARRIER_MODEL.vector_dimension,
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
    )
