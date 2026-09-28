"""Explicit downloads of pinned model artifacts, separate from the active inventory."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
from tempfile import mkdtemp, mkstemp

from src.config.embedding_model_manifest import (
    ArtifactManifest,
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
    reused: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return the successful preparation result without credentials."""

        return {
            "operation": "download",
            "status": "bereit",
            "message": "Lokale Embedding-Modelle sind geprueft und freigegeben.",
            "inventory_dir": str(self.inventory_dir),
            "manifest_sha256": self.manifest.manifest_sha256,
            "reused": self.reused,
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
    """Download pinned revisions or resume an exactly matching preparation plan.

    Dense model and tokenizer share a download when their pinned identities match.
    No manifest is written and no active model file is replaced. Failed downloads
    leave their preparation directory in place. Completed snapshots are reused
    only after checking their receipt and all artifact checksums; unconfirmed
    snapshots are downloaded again without trusting the Hub's local cache.
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
    plan = {
        "format_version": 1,
        "pipeline_version": EMBEDDING_PIPELINE_VERSION,
        "manifest_format_version": MODEL_MANIFEST_FORMAT_VERSION,
        "snapshots": [
            {"model_id": model_id, "revision": revision, "artifacts": sorted(artifacts)}
            for (model_id, revision), artifacts in artifacts_by_snapshot.items()
        ],
    }

    try:
        preparation_root = models_dir.resolve() / ".preparation"
        if preparation_root.is_symlink():
            raise OSError("Preparation directory must not be a symlink")
        preparation_root.mkdir(parents=True, exist_ok=True)
        staging_dir = None
        for path in sorted(preparation_root.glob("download-*")):
            if not path.is_dir() or path.is_symlink():
                continue
            try:
                if any(entry.is_symlink() for entry in path.rglob("*")):
                    continue
                if json.loads((path / "download-plan.json").read_text(encoding="utf-8")) == plan:
                    staging_dir = path
                    break
            except (OSError, ValueError, UnicodeError):
                continue
        if staging_dir is None:
            staging_dir = Path(mkdtemp(prefix="download-", dir=preparation_root))
            (staging_dir / "download-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    except OSError:
        raise EmbeddingModelDownloadError(
            "Der lokale Vorbereitungsordner kann nicht angelegt werden."
        ) from None

    snapshots = []
    for index, ((model_id, revision), artifacts) in enumerate(artifacts_by_snapshot.items()):
        relative_path = f"{model_id}/{revision}"
        required_artifacts = tuple(sorted(artifacts))
        receipt_path = staging_dir / f"snapshot-{index}.json"
        model_root = staging_dir / relative_path
        confirmed = False
        try:
            confirmed = json.loads(receipt_path.read_text(encoding="utf-8")) == _snapshot_receipt(
                model_root, model_id, revision, required_artifacts,
            )
        except (OSError, ValueError, UnicodeError):
            pass
        try:
            if not confirmed:
                snapshot_download(
                    repo_id=model_id,
                    repo_type="model",
                    revision=revision,
                    local_dir=model_root,
                    allow_patterns=list(required_artifacts),
                    token=token,
                    local_files_only=False,
                    force_download=True,
                )
                receipt_path.write_text(json.dumps(_snapshot_receipt(
                    model_root, model_id, revision, required_artifacts,
                )), encoding="utf-8")
        except Exception:
            # Provider exceptions can contain authenticated URLs. Detailed error
            # categorization and redacted logging are separate preparation steps.
            raise EmbeddingModelDownloadError(
                f"Download oder Modellpruefung fuer {model_id} fehlgeschlagen; der aktive Bestand bleibt unveraendert."
            ) from None
        snapshots.append(DownloadedModelSnapshot(
            model_id=model_id,
            revision=revision,
            relative_path=relative_path,
            required_artifacts=required_artifacts,
        ))
    return EmbeddingModelDownload(staging_dir, tuple(snapshots))


def _checked_artifacts(
    model_root: Path, artifacts: tuple[str, ...], absent: tuple[str, ...] = (),
) -> tuple[ArtifactManifest, ...]:
    resolved_root = model_root.resolve(strict=True)
    for relative_path in artifacts:
        path = model_root / relative_path
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
        if path.is_symlink() or not resolved.is_file() or resolved.stat().st_size == 0:
            raise ValueError("Required artifacts must be nonempty regular local files")
    return build_artifact_manifests(model_root, artifacts, expected_absent_paths=absent)


def _snapshot_receipt(
    model_root: Path, model_id: str, revision: str, artifacts: tuple[str, ...],
) -> dict[str, object]:
    absent = (
        HARRIER_MODEL.expected_absent_artifacts
        if (model_id, revision) == (HARRIER_MODEL.model_id, HARRIER_MODEL.revision) else ()
    )
    return {
        "model_id": model_id,
        "revision": revision,
        "artifacts": [asdict(artifact) for artifact in _checked_artifacts(model_root, artifacts, absent)],
    }


def _library_versions() -> ModelLibraryVersions:
    return ModelLibraryVersions(
        transformers=version("transformers"),
        sentence_transformers=version("sentence-transformers"),
        fastembed=version("fastembed"),
        huggingface_hub=version("huggingface-hub"),
    )


def _reusable_manifest(path: Path, libraries: ModelLibraryVersions) -> EmbeddingModelManifest | None:
    try:
        if path.is_symlink():
            return None
        manifest = load_and_validate_model_inventory(path, deep=True)
        if manifest.library_versions != libraries:
            return None
        if any(
            artifact.size_bytes == 0
            for name in ("dense_model", "tokenizer", "sparse_model")
            for artifact in getattr(manifest, name).artifacts
        ):
            return None
        return manifest
    except (OSError, ValueError):
        return None


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
        components[name] = PreparedModelManifest(
            model_id=definition.model_id,
            configured_revision=definition.revision,
            resolved_revision=definition.revision,
            relative_path=relative_path,
            artifacts=_checked_artifacts(
                model_root,
                definition.required_artifacts,
                getattr(definition, "expected_absent_artifacts", ()),
            ),
        )
    return with_manifest_sha256(EmbeddingModelManifest(
        manifest_format_version=MODEL_MANIFEST_FORMAT_VERSION,
        pipeline_version=EMBEDDING_PIPELINE_VERSION,
        **components,
        library_versions=_library_versions(),
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    ))


def prepare_embedding_models(models_dir: Path) -> PreparedEmbeddingModels:
    """Download, deeply validate, then atomically activate a complete inventory.

    Artifacts are stored in content-addressed inventory directories and never
    overwrite active files. The root manifest is the sole activation point.
    Failed or interrupted preparation leaves the previous root manifest intact;
    candidates and old inventories are retained rather than deleted.
    """

    root = models_dir.resolve()
    try:
        libraries = _library_versions()
        current = _reusable_manifest(root, libraries)
        if current is not None:
            parts = Path(current.dense_model.relative_path).parts
            inventory_dir = root.joinpath(*parts[:2]) if parts[0] == "inventories" else root
            return PreparedEmbeddingModels(inventory_dir, current, reused=True)

        inventories_root = root / "inventories"
        if inventories_root.is_symlink():
            raise ValueError("Inventory directory must not be a symlink")
        for path in sorted(inventories_root.glob("*")):
            existing = _reusable_manifest(path, libraries)
            if existing is not None and existing.manifest_sha256 == path.name:
                return _activate_inventory(root, path, existing, reused=True)

        preparation_root = root / ".preparation"
        if preparation_root.is_symlink():
            raise ValueError("Preparation directory must not be a symlink")
        download = None
        for path in sorted(preparation_root.glob("download-*")):
            existing = _reusable_manifest(path, libraries)
            if existing is not None:
                download = EmbeddingModelDownload(path, ())
                break
        reused_candidate = download is not None
        if download is None:
            download = download_embedding_models(models_dir)
        candidate = _build_candidate_manifest(download)
        candidate_path = download.staging_dir / MODEL_MANIFEST_FILENAME
        candidate_path.write_bytes(canonical_manifest_bytes(candidate))
        load_and_validate_model_inventory(download.staging_dir, deep=True)

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

        return _activate_inventory(root, inventory_dir, candidate, reused=reused_candidate)
    except (OSError, ValueError, PackageNotFoundError):
        raise EmbeddingModelDownloadError(
            "Modellpruefung oder Freigabe fehlgeschlagen; der aktive Bestand bleibt unveraendert."
        ) from None


def _activate_inventory(
    root: Path, inventory_dir: Path, candidate: EmbeddingModelManifest, *, reused: bool = False,
) -> PreparedEmbeddingModels:
    prefix = inventory_dir.relative_to(root).as_posix()
    components = {
        name: replace(getattr(candidate, name), relative_path=f"{prefix}/{getattr(candidate, name).relative_path}")
        for name in ("dense_model", "tokenizer", "sparse_model")
    }
    active = with_manifest_sha256(replace(candidate, **components))
    descriptor, temporary_name = mkstemp(prefix=".manifest-", suffix=".tmp", dir=root)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical_manifest_bytes(active))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_name, root / MODEL_MANIFEST_FILENAME)
    return PreparedEmbeddingModels(inventory_dir, active, reused=reused)
