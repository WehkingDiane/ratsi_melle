"""Offline validation of the locally prepared embedding model inventory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

from src.config.embedding_model_manifest import (
    ArtifactManifest,
    EmbeddingModelManifest,
    ModelLibraryVersions,
    PreparedModelManifest,
    calculate_manifest_sha256,
    validate_absent_artifacts,
    validate_relative_posix_path,
)
from src.config.embedding_models import (
    BM25_MODEL,
    EMBEDDING_PIPELINE_VERSION,
    HARRIER_MODEL,
    HARRIER_TOKENIZER,
    MODEL_MANIFEST_FORMAT_VERSION,
)


MODEL_MANIFEST_FILENAME = "manifest.json"


class ModelInventoryError(ValueError):
    """Base error raised when the local model inventory cannot be used."""


class ModelInventoryMissingError(ModelInventoryError):
    """The local inventory manifest is absent."""


class ModelInventoryIncompleteError(ModelInventoryError):
    """The local inventory or one of its required files is incomplete."""


class ModelInventoryIncompatibleError(ModelInventoryError):
    """The local inventory does not match the configured model contract."""


class EmbeddingModelReadiness(StrEnum):
    """Stable shared readiness values for command-line and web consumers."""

    READY = "bereit"
    MISSING = "fehlt"
    INCOMPLETE = "unvollstaendig"
    INCOMPATIBLE = "inkompatibel"


@dataclass(frozen=True, slots=True)
class EmbeddingModelStatus:
    """Machine-readable readiness result for the local model inventory."""

    state: EmbeddingModelReadiness
    message: str
    manifest_sha256: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Return a JSON-compatible representation for CLI and web callers."""

        return {
            "status": self.state.value,
            "message": self.message,
            "manifest_sha256": self.manifest_sha256,
        }


def _component_from_payload(payload: object, name: str) -> PreparedModelManifest:
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be an object")
    expected_fields = {
        "model_id",
        "configured_revision",
        "resolved_revision",
        "relative_path",
        "artifacts",
    }
    if set(payload) != expected_fields:
        raise ValueError(f"{name} fields do not match the manifest schema")
    artifacts_payload = payload.get("artifacts")
    if not isinstance(artifacts_payload, list):
        raise ValueError(f"{name}.artifacts must be a list")
    artifacts = tuple(ArtifactManifest(**artifact) for artifact in artifacts_payload)
    fields = {key: value for key, value in payload.items() if key != "artifacts"}
    return PreparedModelManifest(**fields, artifacts=artifacts)


def _manifest_from_payload(payload: object) -> EmbeddingModelManifest:
    if not isinstance(payload, dict):
        raise ValueError("Manifest must be a JSON object")
    expected_fields = {
        "manifest_format_version",
        "pipeline_version",
        "dense_model",
        "tokenizer",
        "sparse_model",
        "library_versions",
        "created_at",
        "manifest_sha256",
    }
    if set(payload) != expected_fields:
        raise ValueError("Manifest fields do not match the schema")
    components = {
        name: _component_from_payload(payload[name], name)
        for name in ("dense_model", "tokenizer", "sparse_model")
    }
    return EmbeddingModelManifest(
        manifest_format_version=payload["manifest_format_version"],
        pipeline_version=payload["pipeline_version"],
        dense_model=components["dense_model"],
        tokenizer=components["tokenizer"],
        sparse_model=components["sparse_model"],
        library_versions=ModelLibraryVersions(**payload["library_versions"]),
        created_at=payload["created_at"],
        manifest_sha256=payload["manifest_sha256"],
    )


def load_and_validate_model_inventory(
    models_dir: Path,
    *,
    deep: bool = False,
) -> EmbeddingModelManifest:
    """Validate manifest metadata and file sizes without hashing model contents.

    The default check reads only the small manifest and filesystem metadata. With
    ``deep=True``, it also hashes the configured core artifacts. Neither mode
    initializes model libraries or accesses the network.
    """

    models_dir = Path(models_dir).expanduser()
    manifest_path = models_dir / MODEL_MANIFEST_FILENAME
    if manifest_path.is_symlink():
        raise ModelInventoryIncompatibleError("Das lokale Modellmanifest ist kein regulaeres File.")
    if not manifest_path.exists():
        raise ModelInventoryMissingError("Lokales Embedding-Modellmanifest fehlt.")
    if not manifest_path.is_file():
        raise ModelInventoryIncompatibleError("Das lokale Modellmanifest ist kein regulaeres File.")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ModelInventoryIncompleteError("Das lokale Modellmanifest ist unvollstaendig oder ungueltig.") from error

    if not isinstance(payload, dict):
        raise ModelInventoryIncompleteError("Das lokale Modellmanifest ist unvollstaendig oder ungueltig.")
    format_version = payload.get("manifest_format_version")
    if type(format_version) is not int or format_version < 1:
        raise ModelInventoryIncompleteError("Das lokale Modellmanifest ist unvollstaendig oder ungueltig.")
    if format_version != MODEL_MANIFEST_FORMAT_VERSION:
        raise ModelInventoryIncompatibleError(
            "Das lokale Modellmanifest verwendet eine nicht unterstuetzte Formatversion."
        )

    try:
        manifest = _manifest_from_payload(payload)
    except (KeyError, TypeError, ValueError) as error:
        raise ModelInventoryIncompleteError("Das lokale Modellmanifest ist unvollstaendig oder ungueltig.") from error

    if manifest.manifest_sha256 != calculate_manifest_sha256(manifest):
        raise ModelInventoryIncompatibleError("Der Hash des lokalen Modellmanifests stimmt nicht.")
    if manifest.pipeline_version != EMBEDDING_PIPELINE_VERSION:
        raise ModelInventoryIncompatibleError("Das lokale Modellmanifest verwendet einen inkompatiblen Vertrag.")

    try:
        root = models_dir.resolve()
    except (OSError, RuntimeError) as error:
        raise ModelInventoryIncompleteError("Der lokale Modellpfad fehlt oder ist ungueltig.") from error
    expected = (
        ("dense_model", HARRIER_MODEL.model_id, HARRIER_MODEL.revision,
         HARRIER_MODEL.required_artifacts, HARRIER_MODEL.expected_absent_artifacts),
        ("tokenizer", HARRIER_TOKENIZER.model_id, HARRIER_TOKENIZER.revision,
         HARRIER_TOKENIZER.required_artifacts, ()),
        ("sparse_model", BM25_MODEL.model_id, BM25_MODEL.revision,
         BM25_MODEL.required_artifacts, ()),
    )
    for name, model_id, revision, required_artifacts, expected_absent_artifacts in expected:
        component = getattr(manifest, name)
        if (
            component.model_id != model_id
            or component.configured_revision != revision
            or component.resolved_revision != revision
            or tuple(sorted(artifact.relative_path for artifact in component.artifacts))
            != required_artifacts
        ):
            raise ModelInventoryIncompatibleError(
                f"Der lokale Modellvertrag fuer {name} ist inkompatibel."
            )
        try:
            relative_model_path = validate_relative_posix_path(
                component.relative_path,
                label="Local model path",
            )
            model_root = (root / Path(*PurePosixPath(relative_model_path).parts)).resolve(strict=True)
            model_root.relative_to(root)
        except (OSError, ValueError, RuntimeError) as error:
            raise ModelInventoryIncompleteError(
                f"Der lokale Modellpfad fuer {name} fehlt oder ist ungueltig."
            ) from error
        if expected_absent_artifacts:
            try:
                validate_absent_artifacts(model_root, expected_absent_artifacts)
            except ValueError as error:
                raise ModelInventoryIncompatibleError(
                    f"Der lokale Modellbestand fuer {name} enthaelt ein unzulaessiges Artefakt."
                ) from error
        for artifact in component.artifacts:
            artifact_path = model_root.joinpath(*PurePosixPath(artifact.relative_path).parts)
            try:
                resolved_artifact = artifact_path.resolve(strict=True)
                resolved_artifact.relative_to(model_root)
                if artifact_path.is_symlink() or not resolved_artifact.is_file():
                    raise OSError("not a regular local file")
                actual_size = resolved_artifact.stat().st_size
            except (OSError, ValueError, RuntimeError) as error:
                raise ModelInventoryIncompleteError(
                    f"Ein Pflichtartefakt fuer {name} fehlt oder liegt ausserhalb des Modellpfads."
                ) from error
            if actual_size != artifact.size_bytes:
                raise ModelInventoryIncompleteError(
                    f"Die Dateigroesse eines Pflichtartefakts fuer {name} stimmt nicht."
                )
            if deep:
                digest = sha256()
                try:
                    with resolved_artifact.open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(block)
                except OSError as error:
                    raise ModelInventoryIncompleteError(
                        f"Ein Pflichtartefakt fuer {name} kann nicht gelesen werden."
                    ) from error
                if digest.hexdigest() != artifact.sha256:
                    raise ModelInventoryIncompleteError(
                        f"Die SHA-256-Pruefsumme eines Pflichtartefakts fuer {name} stimmt nicht."
                    )
            else:
                try:
                    with resolved_artifact.open("rb"):
                        pass
                except OSError as error:
                    raise ModelInventoryIncompleteError(
                        f"Ein Pflichtartefakt fuer {name} kann nicht gelesen werden."
                    ) from error
    return manifest


def check_embedding_model_status(
    models_dir: Path,
    *,
    deep: bool = False,
) -> EmbeddingModelStatus:
    """Return one shared readiness result without propagating inventory errors."""

    try:
        manifest = load_and_validate_model_inventory(models_dir, deep=deep)
    except ModelInventoryMissingError as error:
        return EmbeddingModelStatus(EmbeddingModelReadiness.MISSING, str(error))
    except ModelInventoryIncompleteError as error:
        return EmbeddingModelStatus(EmbeddingModelReadiness.INCOMPLETE, str(error))
    except ModelInventoryIncompatibleError as error:
        return EmbeddingModelStatus(EmbeddingModelReadiness.INCOMPATIBLE, str(error))
    return EmbeddingModelStatus(
        EmbeddingModelReadiness.READY,
        "Lokale Embedding-Modelle sind bereit.",
        manifest.manifest_sha256,
    )
