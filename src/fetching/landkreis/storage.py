"""Storage helpers for Landkreis publication raw data."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.fetching.landkreis.models import LandkreisPublication


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
        return self.data_root / publication.source / year / f"{date_part}_{slug}"

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

        target = self.publication_dir(publication) / "manifest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(publication)
        if publication.date is not None:
            payload["date"] = publication.date.isoformat()
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target


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
