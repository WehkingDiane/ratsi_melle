"""Central runtime settings for indexing and Qdrant."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

from src import paths


# False = der Indexer verwendet ausschließlich bereits lokal vorhandene Modelle.
# True  = fehlende Modelle dürfen beim Indexieren heruntergeladen werden.
INDEXER_ALLOW_MODEL_DOWNLOADS = False
DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"


class QdrantSettingsError(ValueError):
    """A Qdrant environment setting is invalid."""


@dataclass(frozen=True)
class QdrantSettings:
    """Validated settings for one Qdrant operation."""

    mode: str
    url: str = field(repr=False)
    state_dir: Path


def load_qdrant_settings() -> QdrantSettings:
    """Read and validate Qdrant settings when an operation starts."""

    mode = os.environ.get("RATSI_QDRANT_MODE", "server").strip().lower()
    if mode not in {"server", "local"}:
        raise QdrantSettingsError("RATSI_QDRANT_MODE muss 'server' oder 'local' sein.")

    configured_url = os.environ.get("RATSI_QDRANT_URL", "").strip()
    url = (configured_url or (DEFAULT_QDRANT_URL if mode == "server" else "")).rstrip("/")
    if url:
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                     and parsed.port != 0 and not parsed.query and not parsed.fragment
                     and not any(char.isspace() for char in url))
        except ValueError:
            valid = False
        if not valid:
            raise QdrantSettingsError("RATSI_QDRANT_URL muss eine gültige HTTP(S)-Serveradresse sein.")

    configured_state_dir = os.environ.get("RATSI_QDRANT_STATE_DIR")
    if configured_state_dir is None:
        state_dir = paths.DB_DIR / "qdrant_server_state"
    else:
        if not configured_state_dir.strip() or "\x00" in configured_state_dir:
            raise QdrantSettingsError("RATSI_QDRANT_STATE_DIR muss ein gültiger Pfad sein.")
        try:
            state_dir = Path(configured_state_dir).expanduser()
        except RuntimeError:
            raise QdrantSettingsError("RATSI_QDRANT_STATE_DIR muss ein gültiger Pfad sein.") from None
    return QdrantSettings(mode=mode, url=url, state_dir=state_dir)
