"""Domain models for fetching data from the Melle SessionNet instance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass(slots=True)
class DocumentReference:
    """Reference to a downloadable document in the SessionNet system."""

    title: str
    url: str
    category: Optional[str] = None
    on_agenda_item: Optional[str] = None


@dataclass(slots=True)
class AgendaItem:
    """Structured representation of a single agenda item."""

    number: str
    title: str
    status: Optional[str] = None
    documents: List[DocumentReference] = field(default_factory=list)


@dataclass(slots=True)
class SessionReference:
    """Summary information for a council meeting (Sitzung)."""

    committee: str
    meeting_name: str
    session_id: str
    date: date
    start_time: Optional[str]
    detail_url: str
    agenda_url: Optional[str] = None
    documents_url: Optional[str] = None
    location: Optional[str] = None


@dataclass(slots=True)
class SessionDetail:
    """Detailed information parsed from the session detail view."""

    reference: SessionReference
    agenda_items: List[AgendaItem]
    retrieved_at: datetime
    raw_html: str

