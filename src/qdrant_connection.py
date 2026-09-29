"""Shared Qdrant connection configuration for CLI, search and status pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from src import paths
from src.config.index_compatibility import IndexCompatibility
from src.config.settings import load_qdrant_settings


class QdrantServerUnavailableError(RuntimeError):
    """Raised when the configured remote Qdrant server cannot be reached."""


_INDEX_COLLECTIONS = frozenset({"ratsi_passages", "ratsi_documents", "landkreis_publications"})


@dataclass(frozen=True)
class QdrantConnection:
    """Use validated settings for a Qdrant operation."""

    path: Path
    url: str = field(default="", repr=False)
    state_dir: Path = paths.DB_DIR / "qdrant_server_state"

    @classmethod
    def from_env(cls, path: Path = paths.QDRANT_DIR) -> QdrantConnection:
        """Use the configured server unless local mode is selected."""
        settings = load_qdrant_settings()
        return cls(Path(path), settings.url, settings.state_dir)

    @property
    def target(self) -> str:
        """Return a public destination without credentials or URL paths."""
        if not self.url:
            return str(self.path)
        parsed = urlsplit(self.url)
        return f"{parsed.scheme}://{parsed.netloc.rsplit('@', 1)[-1]}"

    @property
    def ready_path(self) -> Path:
        """Return the historical passage marker path."""
        return self.release_path("ratsi_passages")

    def release_path(self, collection: str) -> Path:
        """Keep each collection's local or URL-scoped release marker separate."""
        if collection not in _INDEX_COLLECTIONS:
            raise ValueError("Unknown index collection")
        directory = self.state_dir / sha256(self.url.encode()).hexdigest() if self.url else self.path
        return directory / f"{collection}.ready.json"

    def read_index_compatibility(self, collection: str) -> IndexCompatibility | None:
        """Read a marker's validated model contract without changing the store."""
        try:
            marker = json.loads(self.release_path(collection).read_text(encoding="utf-8"))
            if not isinstance(marker, dict) or marker.get("collection") != collection:
                return None
            if self.url and marker.get("url_sha256") != sha256(self.url.encode()).hexdigest():
                return None
            return IndexCompatibility.from_dict(marker.get("compatibility"))
        except (OSError, UnicodeError, ValueError, TypeError):
            return None

    def create_client(self):
        """Open only the selected backend; never fall back after server errors."""
        from qdrant_client import QdrantClient

        if self.url:
            client = None
            try:
                client = QdrantClient(url=self.url, timeout=10)
                client.get_collections()
            except Exception:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass
                raise QdrantServerUnavailableError("Qdrant-Server nicht erreichbar.") from None
            return client
        return QdrantClient(path=str(self.path))

    def passages_ready(self, client) -> bool:
        """Accept server markers only for this endpoint and committed point count."""
        try:
            marker = json.loads(self.ready_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(marker, dict):
            return False
        if not self.url:
            return True  # Preserve existing local marker format.
        if marker.get("url_sha256") != sha256(self.url.encode()).hexdigest() or not marker.get("points_count"):
            return False
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        total = client.count("ratsi_passages", exact=True).count
        committed = client.count("ratsi_passages", exact=True, count_filter=Filter(must=[
            FieldCondition(key="committed", match=MatchValue(value=True)),
        ])).count
        return total == committed == marker["points_count"]

    def clear_readiness(self, collection: str = "ratsi_passages") -> None:
        """Revoke activation before a build changes the collection."""
        self.release_path(collection).unlink(missing_ok=True)

    def write_readiness(self, client, metadata: dict, *,
                        collection: str = "ratsi_passages",
                        compatibility: IndexCompatibility | None = None) -> None:
        """Atomically record the completed build for the selected backend."""
        path = self.release_path(collection)
        marker = dict(metadata)
        if compatibility is not None:
            marker.update(collection=collection, compatibility=compatibility.as_dict())
        if self.url:
            marker.update(url_sha256=sha256(self.url.encode()).hexdigest(),
                          points_count=client.count(collection, exact=True).count)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(marker, stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def collection_state(connection: QdrantConnection, client, collection: str = "ratsi_documents", *, prefer_passages: bool = True) -> dict:
    """Resolve the searchable collection using the same readiness rule everywhere."""
    names = {item.name for item in client.get_collections().collections}
    incomplete = False
    if prefer_passages and collection == "ratsi_documents" and "ratsi_passages" in names:
        if connection.passages_ready(client) and client.get_collection("ratsi_passages").points_count:
            collection = "ratsi_passages"
        else:
            incomplete = True
    exists = collection in names
    searchable = exists and bool(client.get_collection(collection).points_count)
    if exists and not searchable:
        incomplete = True
    state = "incomplete" if incomplete else "ready" if exists else "missing_collection"
    return {"state": state, "collection_name": collection, "collection_exists": exists,
            "searchable": searchable,
            "message": {"incomplete": "Index unvollständig: Collection leer oder Abschnittsindex noch nicht freigegeben.",
                        "ready": "bereit", "missing_collection": f"Collection fehlt: {collection}"}[state]}


def probe_qdrant(connection: QdrantConnection) -> dict:
    """Return lightweight availability without creating a missing local database."""
    if not connection.url and not connection.path.exists():
        return {"state": "missing_qdrant", "message": "Vektorindex fehlt", "available": False}
    client = None
    try:
        client = connection.create_client()
        result = collection_state(connection, client)
        return {**result, "available": result["searchable"]}
    except Exception as exc:
        label = "Server nicht erreichbar" if connection.url else "Vektorindex nicht lesbar"
        return {"state": "server_unreachable" if connection.url else "warning",
                "message": label if connection.url else f"{label}: {exc}", "available": False}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass  # A cleanup error must not turn a status response into HTTP 500.
