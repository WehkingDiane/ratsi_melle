"""Schema and deterministic hashing for prepared embedding model manifests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable


_MODEL_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*")
_COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def validate_model_id(value: str) -> str:
    """Return a valid Hub-style model ID or raise ``ValueError``."""

    if not isinstance(value, str) or not _MODEL_ID_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid model ID: {value!r}")
    return value


def validate_commit_sha(value: str) -> str:
    """Return a full lowercase commit SHA or reject moving/short revisions."""

    if not isinstance(value, str) or not _COMMIT_SHA_PATTERN.fullmatch(value):
        raise ValueError(f"Revision must be a full lowercase commit SHA: {value!r}")
    return value


def validate_relative_posix_path(value: str, *, label: str = "Path") -> str:
    """Return one canonical relative POSIX path without traversal components."""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a relative POSIX path: {value!r}")
    path = PurePosixPath(value)
    if (
        not value
        or "\x00" in value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.as_posix() != value
    ):
        raise ValueError(f"{label} must be a relative POSIX path: {value!r}")
    return value


def _validate_sha256(value: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return value
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"SHA-256 must contain 64 lowercase hexadecimal characters: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Size and checksum of one centrally selected model artifact."""

    relative_path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        validate_relative_posix_path(self.relative_path, label="Artifact path")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("Artifact size must be a nonnegative integer")
        _validate_sha256(self.sha256)


@dataclass(frozen=True, slots=True)
class PreparedModelManifest:
    """Configured and resolved identity of one prepared local model component."""

    model_id: str
    configured_revision: str
    resolved_revision: str
    relative_path: str
    artifacts: tuple[ArtifactManifest, ...]

    def __post_init__(self) -> None:
        validate_model_id(self.model_id)
        validate_commit_sha(self.configured_revision)
        validate_commit_sha(self.resolved_revision)
        validate_relative_posix_path(self.relative_path, label="Local model path")
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ValueError("Prepared model artifacts must be a nonempty tuple")
        if not all(isinstance(artifact, ArtifactManifest) for artifact in self.artifacts):
            raise ValueError("Prepared model artifacts contain an invalid entry")
        paths = [artifact.relative_path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("Prepared model artifacts contain duplicate paths")


@dataclass(frozen=True, slots=True)
class ModelLibraryVersions:
    """Library versions that participated in model preparation."""

    transformers: str
    sentence_transformers: str
    fastembed: str
    huggingface_hub: str

    def __post_init__(self) -> None:
        for name in (
            "transformers",
            "sentence_transformers",
            "fastembed",
            "huggingface_hub",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"Library version {name} must be a nonempty trimmed string")


@dataclass(frozen=True, slots=True)
class EmbeddingModelManifest:
    """Complete reproducibility contract for one prepared model inventory."""

    manifest_format_version: int
    pipeline_version: str
    dense_model: PreparedModelManifest
    tokenizer: PreparedModelManifest
    sparse_model: PreparedModelManifest
    library_versions: ModelLibraryVersions
    created_at: str
    manifest_sha256: str = ""

    def __post_init__(self) -> None:
        if type(self.manifest_format_version) is not int or self.manifest_format_version < 1:
            raise ValueError("Manifest format version must be a positive integer")
        if (
            not isinstance(self.pipeline_version, str)
            or not self.pipeline_version.strip()
            or self.pipeline_version != self.pipeline_version.strip()
        ):
            raise ValueError("Pipeline version must be a nonempty trimmed string")
        for name in ("dense_model", "tokenizer", "sparse_model"):
            if not isinstance(getattr(self, name), PreparedModelManifest):
                raise ValueError(f"Manifest component {name} is invalid")
        if not isinstance(self.library_versions, ModelLibraryVersions):
            raise ValueError("Manifest library versions are invalid")
        if not isinstance(self.created_at, str) or not self.created_at.endswith("Z"):
            raise ValueError("Creation time must be an ISO-8601 UTC timestamp ending in Z")
        try:
            created_at = datetime.fromisoformat(self.created_at[:-1] + "+00:00")
        except ValueError:
            raise ValueError("Creation time must be an ISO-8601 UTC timestamp ending in Z") from None
        if created_at.tzinfo is None or created_at.utcoffset() != timezone.utc.utcoffset(created_at):
            raise ValueError("Creation time must be an ISO-8601 UTC timestamp ending in Z")
        _validate_sha256(self.manifest_sha256, allow_empty=True)


def select_checksum_artifacts(relative_paths: Iterable[str]) -> tuple[str, ...]:
    """Validate and deterministically order the configured artifact allowlist."""

    selected: set[str] = set()
    for value in relative_paths:
        normalized = validate_relative_posix_path(value, label="Artifact path")
        if normalized in selected:
            raise ValueError(f"Duplicate artifact path: {normalized}")
        selected.add(normalized)
    if not selected:
        raise ValueError("At least one artifact path is required")
    return tuple(sorted(selected))


def build_artifact_manifests(
    model_root: Path,
    relative_paths: Iterable[str],
) -> tuple[ArtifactManifest, ...]:
    """Hash exactly the selected core artifacts below one prepared model root."""

    records = []
    for relative_path in select_checksum_artifacts(relative_paths):
        path = model_root.joinpath(*PurePosixPath(relative_path).parts)
        digest = sha256()
        size_bytes = 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size_bytes += len(block)
                digest.update(block)
        records.append(
            ArtifactManifest(
                relative_path=relative_path,
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
            )
        )
    return tuple(records)


def manifest_payload(
    manifest: EmbeddingModelManifest,
    *,
    include_manifest_sha256: bool = True,
    include_created_at: bool = True,
) -> dict[str, Any]:
    """Return the JSON-compatible manifest payload in deterministic list order."""

    payload = asdict(manifest)
    for component in ("dense_model", "tokenizer", "sparse_model"):
        payload[component]["artifacts"] = sorted(
            payload[component]["artifacts"],
            key=lambda artifact: artifact["relative_path"],
        )
    if not include_manifest_sha256:
        payload.pop("manifest_sha256", None)
    if not include_created_at:
        payload.pop("created_at", None)
    return payload


def canonical_manifest_bytes(
    manifest: EmbeddingModelManifest,
    *,
    include_manifest_sha256: bool = True,
    include_created_at: bool = True,
) -> bytes:
    """Serialize a manifest as canonical UTF-8 JSON without insignificant space."""

    return json.dumps(
        manifest_payload(
            manifest,
            include_manifest_sha256=include_manifest_sha256,
            include_created_at=include_created_at,
        ),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def calculate_manifest_sha256(manifest: EmbeddingModelManifest) -> str:
    """Hash the stable compatibility contract without volatile metadata."""

    return sha256(
        canonical_manifest_bytes(
            manifest,
            include_manifest_sha256=False,
            include_created_at=False,
        )
    ).hexdigest()


def with_manifest_sha256(manifest: EmbeddingModelManifest) -> EmbeddingModelManifest:
    """Return an immutable manifest copy containing its canonical content hash."""

    return replace(manifest, manifest_sha256=calculate_manifest_sha256(manifest))
