"""Domain models for Landkreis Osnabrueck publications."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class LandkreisDocument:
    """A downloadable document linked from a Landkreis publication."""

    title: str
    url: str
    local_path: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    sha1: str | None = None
    retrieved_at: str | None = None


@dataclass(frozen=True, slots=True)
class LandkreisPublication:
    """One entry from a Landkreis publication list."""

    source: str
    publication_id: str
    date: date | None
    title: str
    detail_url: str
    list_url: str
    local_dir: str | None = None
    page_text: str = ""
    retrieved_at: str | None = None
    documents: list[LandkreisDocument] = field(default_factory=list)

    @property
    def year(self) -> int | None:
        """Return the publication year when a date is available."""

        return self.date.year if self.date is not None else None
