"""Shared model contract recorded with a Qdrant index generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

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
        if len(self.manifest_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.manifest_sha256):
            raise ValueError("Manifest hash must be a lowercase SHA-256 digest")
        if type(self.vector_dimension) is not int or self.vector_dimension < 1:
            raise ValueError("Vector dimension must be a positive integer")
        if not isinstance(self.pipeline_version, str) or not self.pipeline_version.strip():
            raise ValueError("Pipeline version must be a nonempty string")

    def as_dict(self) -> dict[str, str | int]:
        """Return the exact JSON-compatible compatibility fields."""

        return asdict(self)


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
