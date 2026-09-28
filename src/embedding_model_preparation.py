"""Explicit downloads of pinned model artifacts, separate from the active inventory."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
from tempfile import mkdtemp, mkstemp

from src.config.embedding_model_manifest import (
    EmbeddingModelManifest,
    ModelLibraryVersions,
    PreparedModelManifest,
    build_artifact_manifests,
    canonical_manifest_bytes,
    with_manifest_sha256,
)
from src.config.embedding_models import (
    BM25_MODEL, EMBEDDING_PIPELINE_VERSION, HARRIER_MODEL, HARRIER_TOKENIZER,
    MODEL_MANIFEST_FORMAT_VERSION,
)
from src.config.embedding_model_status import (
    MODEL_MANIFEST_FILENAME,
    load_and_validate_model_inventory,
)


class EmbeddingModelDownloadError(RuntimeError):
    """A configured snapshot could not be downloaded into the preparation area."""


@dataclass(frozen=True, slots=True)
class PreparedEmbeddingModels:
    """Validated inventory activated by atomically replacing its manifest."""

    inventory_dir: Path
    manifest: EmbeddingModelManifest

    def as_dict(self) -> dict[str, object]:
        """Return the successful preparation result without credentials."""

        return {
            "operation": "download",
            "status": "bereit",
            "message": "Lokale Embedding-Modelle sind geprueft und freigegeben.",
            "inventory_dir": str(self.inventory_dir),
            "manifest_sha256": self.manifest.manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class DownloadedModelSnapshot:
    """Pinned identity and selected artifacts of one downloaded repository."""

    model_id: str
    revision: str
    relative_path: str
    required_artifacts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingModelDownload:
    """Downloaded candidates; this result does not imply inventory readiness."""

    staging_dir: Path
    snapshots: tuple[DownloadedModelSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        """Return download metadata without credentials or a readiness claim."""

        return {
            "operation": "download",
            "status": "heruntergeladen",
            "message": "Gepinnte Modellartefakte heruntergeladen; noch nicht geprueft oder freigegeben.",
            "staging_dir": str(self.staging_dir),
            "snapshots": [asdict(snapshot) for snapshot in self.snapshots],
        }


def download_embedding_models(models_dir: Path) -> EmbeddingModelDownload:
    """Download only configured revisions to a new, retained preparation directory.

    Dense model and tokenizer share a download when their pinned identities match.
    No manifest is written and no active model file is replaced. Failed downloads
    leave their preparation directory in place for diagnosis; safe reuse and
    publication belong to later preparation steps.
    """

    # Keep the Hub dependency and credential lookup out of all offline checks.
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise EmbeddingModelDownloadError(
            "Die Download-Abhaengigkeit huggingface-hub fehlt; requirements.txt installieren."
        ) from None
    from src.config.secrets import get_api_key

    token = get_api_key("huggingface") or False
    artifacts_by_snapshot: dict[tuple[str, str], set[str]] = {}
    for definition in (HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL):
        identity = (definition.model_id, definition.revision)
        artifacts_by_snapshot.setdefault(identity, set()).update(definition.required_artifacts)

    try:
        preparation_root = models_dir.resolve() / ".preparation"
        if preparation_root.is_symlink():
            raise OSError("Preparation directory must not be a symlink")
        preparation_root.mkdir(parents=True, exist_ok=True)
        staging_dir = Path(mkdtemp(prefix="download-", dir=preparation_root))
    except OSError:
        raise EmbeddingModelDownloadError(
            "Der lokale Vorbereitungsordner kann nicht angelegt werden."
        ) from None

    snapshots = []
    for (model_id, revision), artifacts in artifacts_by_snapshot.items():
        relative_path = f"{model_id}/{revision}"
        required_artifacts = tuple(sorted(artifacts))
        try:
            snapshot_download(
                repo_id=model_id,
                repo_type="model",
                revision=revision,
                local_dir=staging_dir / relative_path,
                allow_patterns=list(required_artifacts),
                token=token,
                local_files_only=False,
            )
        except Exception:
            # Provider exceptions can contain authenticated URLs. Detailed error
            # categorization and redacted logging are separate preparation steps.
            raise EmbeddingModelDownloadError(
                f"Download fuer {model_id} fehlgeschlagen; der aktive Bestand bleibt unveraendert."
            ) from None
        snapshots.append(DownloadedModelSnapshot(
            model_id=model_id,
            revision=revision,
            relative_path=relative_path,
            required_artifacts=required_artifacts,
        ))
    return EmbeddingModelDownload(staging_dir, tuple(snapshots))


def _build_candidate_manifest(download: EmbeddingModelDownload) -> EmbeddingModelManifest:
    components = {}
    staging_root = download.staging_dir.resolve(strict=True)
    for name, definition in (
        ("dense_model", HARRIER_MODEL),
        ("tokenizer", HARRIER_TOKENIZER),
        ("sparse_model", BM25_MODEL),
    ):
        relative_path = f"{definition.model_id}/{definition.revision}"
        model_root = staging_root / relative_path
        resolved_model_root = model_root.resolve(strict=True)
        resolved_model_root.relative_to(staging_root)
        for relative_artifact in definition.required_artifacts:
            artifact = model_root / relative_artifact
            resolved = artifact.resolve(strict=True)
            resolved.relative_to(resolved_model_root)
            if artifact.is_symlink() or not resolved.is_file() or resolved.stat().st_size == 0:
                raise ValueError("Required artifacts must be nonempty regular local files")
        components[name] = PreparedModelManifest(
            model_id=definition.model_id,
            configured_revision=definition.revision,
            resolved_revision=definition.revision,
            relative_path=relative_path,
            artifacts=build_artifact_manifests(
                model_root,
                definition.required_artifacts,
                expected_absent_paths=getattr(definition, "expected_absent_artifacts", ()),
            ),
        )
    return with_manifest_sha256(EmbeddingModelManifest(
        manifest_format_version=MODEL_MANIFEST_FORMAT_VERSION,
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        **components,
        library_versions=ModelLibraryVersions(
            transformers=version("transformers"),
            sentence_transformers=version("sentence-transformers"),
            fastembed=version("fastembed"),
            huggingface_hub=version("huggingface-hub"),
        ),
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    ))


def prepare_embedding_models(models_dir: Path) -> PreparedEmbeddingModels:
    """Download, deeply validate, then atomically activate a complete inventory.

    Artifacts are stored in content-addressed inventory directories and never
    overwrite active files. The root manifest is the sole activation point.
    Failed or interrupted preparation leaves the previous root manifest intact;
    candidates and old inventories are retained rather than deleted.
    """

    download = download_embedding_models(models_dir)
    root = models_dir.resolve()
    try:
        candidate = _build_candidate_manifest(download)
        candidate_path = download.staging_dir / MODEL_MANIFEST_FILENAME
        candidate_path.write_bytes(canonical_manifest_bytes(candidate))
        load_and_validate_model_inventory(download.staging_dir, deep=True)

        inventories_root = root / "inventories"
        if inventories_root.is_symlink():
            raise ValueError("Inventory directory must not be a symlink")
        inventories_root.mkdir(exist_ok=True)
        inventory_dir = inventories_root / candidate.manifest_sha256
        if inventory_dir.exists() or inventory_dir.is_symlink():
            # Deterministic paths keep identical preparations hash-compatible.
            # Verify a pre-existing generation instead of overwriting its files.
            if inventory_dir.is_symlink():
                raise ValueError("Inventory must not be a symlink")
            existing = load_and_validate_model_inventory(inventory_dir, deep=True)
            if canonical_manifest_bytes(existing, include_created_at=False) != canonical_manifest_bytes(
                candidate, include_created_at=False,
            ):
                raise ValueError("Existing inventory does not match its content address")
        else:
            download.staging_dir.rename(inventory_dir)

        prefix = inventory_dir.relative_to(root).as_posix()
        active_components = {}
        for name in ("dense_model", "tokenizer", "sparse_model"):
            component = getattr(candidate, name)
            active_components[name] = replace(
                component, relative_path=f"{prefix}/{component.relative_path}",
            )
        active = with_manifest_sha256(replace(candidate, **active_components))
        # Create and flush on the same filesystem before the atomic switch.
        descriptor, temporary_name = mkstemp(prefix=".manifest-", suffix=".tmp", dir=root)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_manifest_bytes(active))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, root / MODEL_MANIFEST_FILENAME)
    except (OSError, ValueError, PackageNotFoundError):
        raise EmbeddingModelDownloadError(
            "Modellpruefung oder Freigabe fehlgeschlagen; der aktive Bestand bleibt unveraendert."
        ) from None
    return PreparedEmbeddingModels(inventory_dir, active)
