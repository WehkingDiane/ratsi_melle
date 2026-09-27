"""Canonical identities for models used by the hybrid search pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from src.config.embedding_model_manifest import (
    select_checksum_artifacts,
    validate_commit_sha,
    validate_model_id,
)


# Changes to embedding, query instructions, tokenization, chunking, or sparse
# processing that alter index contents require a new value.
EMBEDDING_PIPELINE_VERSION: Final[str] = "passages-1"

# Changes to the serialized manifest contract require a new integer version.
MODEL_MANIFEST_FORMAT_VERSION: Final[int] = 1


@dataclass(frozen=True, slots=True)
class DenseModelDefinition:
    """Identity and output contract of the dense embedding model."""

    model_id: str
    revision: str
    vector_dimension: int
    required_artifacts: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_model_id(self.model_id)
        validate_commit_sha(self.revision)
        if type(self.vector_dimension) is not int or self.vector_dimension < 1:
            raise ValueError("Dense vector dimension must be a positive integer")
        if not isinstance(self.required_artifacts, tuple):
            raise ValueError("Required artifacts must be an immutable tuple")
        if select_checksum_artifacts(self.required_artifacts) != self.required_artifacts:
            raise ValueError("Required artifacts must be unique and sorted")


@dataclass(frozen=True, slots=True)
class TokenizerDefinition:
    """Identity of the tokenizer used to split documents into passages."""

    model_id: str
    revision: str
    required_artifacts: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_model_id(self.model_id)
        validate_commit_sha(self.revision)
        if not isinstance(self.required_artifacts, tuple):
            raise ValueError("Required artifacts must be an immutable tuple")
        if select_checksum_artifacts(self.required_artifacts) != self.required_artifacts:
            raise ValueError("Required artifacts must be unique and sorted")


@dataclass(frozen=True, slots=True)
class SparseModelDefinition:
    """Identity of the sparse embedding model."""

    model_id: str
    revision: str
    required_artifacts: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_model_id(self.model_id)
        validate_commit_sha(self.revision)
        if not isinstance(self.required_artifacts, tuple):
            raise ValueError("Required artifacts must be an immutable tuple")
        if select_checksum_artifacts(self.required_artifacts) != self.required_artifacts:
            raise ValueError("Required artifacts must be unique and sorted")


HARRIER_MODEL = DenseModelDefinition(
    model_id="microsoft/harrier-oss-v1-0.6b",
    revision="f9b9dc8d367d443f2479d27aa5d8d2850c0774ee",
    vector_dimension=1024,
    required_artifacts=(
        "1_Pooling/config.json",
        "config.json",
        "config_sentence_transformers.json",
        "model.safetensors",
        "modules.json",
    ),
)

HARRIER_TOKENIZER = TokenizerDefinition(
    model_id="microsoft/harrier-oss-v1-0.6b",
    revision="f9b9dc8d367d443f2479d27aa5d8d2850c0774ee",
    required_artifacts=(
        "added_tokens.json",
        "merges.txt",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    ),
)

BM25_MODEL = SparseModelDefinition(
    model_id="Qdrant/bm25",
    revision="22b8d2af71a76161e18dd432d2cee0eefa66e412",
    required_artifacts=(
        "config.json",
        "english.txt",
    ),
)
