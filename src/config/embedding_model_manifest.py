"""Schema and deterministic hashing for prepared embedding model manifests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Size and checksum of one centrally selected model artifact."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PreparedModelManifest:
    """Configured and resolved identity of one prepared local model component."""

    model_id: str
    configured_revision: str
    resolved_revision: str
    relative_path: str
    artifacts: tuple[ArtifactManifest, ...]


@dataclass(frozen=True, slots=True)
class ModelLibraryVersions:
    """Library versions that participated in model preparation."""

    transformers: str
    sentence_transformers: str
    fastembed: str
    huggingface_hub: str


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


def select_checksum_artifacts(relative_paths: Iterable[str]) -> tuple[str, ...]:
    """Validate and deterministically order the configured artifact allowlist."""

    selected: set[str] = set()
    for value in relative_paths:
        path = PurePosixPath(value)
        if (
            not value
            or "\x00" in value
            or "\\" in value
            or path.is_absolute()
            or ".." in path.parts
            or not path.parts
        ):
            raise ValueError(f"Artifact path must be relative POSIX path: {value!r}")
        normalized = path.as_posix()
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
    return payload


def canonical_manifest_bytes(
    manifest: EmbeddingModelManifest,
    *,
    include_manifest_sha256: bool = True,
) -> bytes:
    """Serialize a manifest as canonical UTF-8 JSON without insignificant space."""

    return json.dumps(
        manifest_payload(manifest, include_manifest_sha256=include_manifest_sha256),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def calculate_manifest_sha256(manifest: EmbeddingModelManifest) -> str:
    """Hash canonical manifest content while excluding the self-referential hash."""

    return sha256(
        canonical_manifest_bytes(manifest, include_manifest_sha256=False)
    ).hexdigest()


def with_manifest_sha256(manifest: EmbeddingModelManifest) -> EmbeddingModelManifest:
    """Return an immutable manifest copy containing its canonical content hash."""

    return replace(manifest, manifest_sha256=calculate_manifest_sha256(manifest))
