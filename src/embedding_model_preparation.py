"""Explicit downloads of pinned model artifacts, separate from the active inventory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import mkdtemp

from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER


class EmbeddingModelDownloadError(RuntimeError):
    """A configured snapshot could not be downloaded into the preparation area."""


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
