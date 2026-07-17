"""Storage helpers for Landkreis publication raw data."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.fetching.landkreis.models import LandkreisPublication
from src.fetching.landkreis.models import LandkreisDocument


class LandkreisStorage:
    """Store Landkreis raw files under one configurable data root."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root).expanduser()
        self.data_root.mkdir(parents=True, exist_ok=True)

    def publication_dir(self, publication: LandkreisPublication) -> Path:
        """Return the stable directory for one publication."""

        year = str(publication.year or "unknown")
        date_part = publication.date.isoformat() if publication.date else "unknown-date"
        slug = _slugify(publication.title)[:80] or publication.publication_id[:12]
        id_part = _slugify(publication.publication_id)[:12] or "unknown-id"
        return self.data_root / publication.source / year / f"{date_part}_{slug}_{id_part}"

    def relative_path(self, path: Path) -> str:
        """Return a POSIX path relative to the configured data root."""

        return path.resolve().relative_to(self.data_root.resolve()).as_posix()

    def resolve_relative_path(self, value: str | None) -> Path | None:
        """Resolve a stored relative path inside the configured data root."""

        if not value:
            return None
        candidate = (self.data_root / value).resolve()
        root = self.data_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate

    def write_publication_html(self, publication: LandkreisPublication, html: str) -> Path:
        """Write the original detail HTML for one publication."""

        target = self.publication_dir(publication) / "detail.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return target

    def write_list_html(self, source: str, page_key: str, html: str) -> Path:
        """Store raw list-page HTML for diagnostics and reproducibility."""

        target = self.data_root / source / "_lists" / f"{_slugify(page_key) or 'page'}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return target

    def document_path(self, publication: LandkreisPublication, document_url: str, index: int) -> Path:
        """Build a stable local file path for a downloaded document."""

        parsed = urlparse(document_url)
        filename = Path(unquote(parsed.path)).name
        if not filename:
            query_name = re.search(r"(?:^|[?&])file=([^&]+)", parsed.query)
            filename = Path(unquote(query_name.group(1))).name if query_name else ""
        filename = _slugify(filename, keep_dot=True) or f"document-{index:03d}.pdf"
        if "." not in filename:
            filename = f"{filename}.pdf"
        return self.publication_dir(publication) / "documents" / f"{index:03d}_{filename}"

    def write_manifest(self, publication: LandkreisPublication) -> Path:
        """Write a manifest next to the publication files."""

        target = self.manifest_path(publication)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(publication)
        if publication.date is not None:
            payload["date"] = publication.date.isoformat()
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def manifest_path(self, publication: LandkreisPublication) -> Path:
        """Return the manifest path for one publication."""

        return self.publication_dir(publication) / "manifest.json"

    def has_manifest(self, publication: LandkreisPublication) -> bool:
        """Return whether this publication was already fetched locally."""

        return self.manifest_path(publication).is_file()

    def iter_manifests(self) -> list[Path]:
        """Return all stored publication manifests under this storage root."""

        if not self.data_root.exists():
            return []
        return sorted(
            path
            for path in self.data_root.rglob("manifest.json")
            if "_lists" not in path.parts
        )

    def load_manifest(self, path: Path) -> LandkreisPublication | None:
        """Load one stored publication manifest."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None

        raw_documents = payload.get("documents")
        documents = [
            LandkreisDocument(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                local_path=_optional_text(item.get("local_path")),
                content_type=_optional_text(item.get("content_type")),
                content_length=_optional_int(item.get("content_length")),
                sha1=_optional_text(item.get("sha1")),
                retrieved_at=_optional_text(item.get("retrieved_at")),
            )
            for item in raw_documents
            if isinstance(item, dict) and item.get("url")
        ] if isinstance(raw_documents, list) else []

        return LandkreisPublication(
            source=str(payload.get("source") or ""),
            publication_id=str(payload.get("publication_id") or ""),
            date=_parse_date(_optional_text(payload.get("date"))),
            title=str(payload.get("title") or ""),
            detail_url=str(payload.get("detail_url") or ""),
            list_url=str(payload.get("list_url") or ""),
            local_dir=_optional_text(payload.get("local_dir")),
            page_text=str(payload.get("page_text") or ""),
            retrieved_at=_optional_text(payload.get("retrieved_at")),
            documents=documents,
        )


def _slugify(value: str, *, keep_dot: bool = False) -> str:
    normalized = value.strip().lower()
    normalized = (
        normalized.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    pattern = r"[^a-z0-9.]+" if keep_dot else r"[^a-z0-9]+"
    normalized = re.sub(pattern, "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-.")
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
