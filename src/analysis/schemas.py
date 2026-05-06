"""Typed and versioned schemas for analysis inputs and outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


ANALYSIS_OUTPUT_SCHEMA_VERSION = "1.0"
ANALYSIS_OUTPUT_SCHEMA_VERSION_V2 = "2.0"
DEFAULT_ANALYSIS_PURPOSE = "content_analysis"

AnalysisPurpose = Literal[
    "journalistic_publication",
    "session_preparation",
    "content_analysis",
    "fact_extraction",
]

AnalysisOutputType = Literal[
    "raw_analysis",
    "structured_analysis",
    "journalistic_article",
    "publication_draft",
    "meeting_briefing",
]


@dataclass(frozen=True)
class AnalysisOutputRecord:
    """Versioned analysis output payload persisted for downstream consumers."""

    schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION
    job_id: int = 0
    created_at: str = ""
    session_id: str = ""
    scope: str = "session"
    top_numbers: list[str] = field(default_factory=list)
    purpose: str = DEFAULT_ANALYSIS_PURPOSE
    model_name: str = ""
    prompt_version: str = ""
    prompt_template_id: str = ""
    prompt_template_revision: int | None = None
    prompt_template_label: str = ""
    rendered_prompt_snapshot_path: str = ""
    prompt_text: str = ""
    markdown: str = ""
    ki_response: str = ""
    document_count: int = 0
    source_db: str = ""
    session_path: str = ""
    session_date: str = ""
    status: str = "done"
    error_message: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RawAnalysisDocument:
    """Source document metadata used by raw analysis outputs."""

    title: str = ""
    document_type: str = ""
    agenda_item: str = ""
    url: str = ""
    local_path: str = ""
    source_available: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RawAnalysisOutput:
    """Raw source-oriented analysis payload."""

    schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION_V2
    output_type: str = "raw_analysis"
    job_id: int = 0
    session_id: str = ""
    scope: str = "session"
    top_numbers: list[str] = field(default_factory=list)
    documents: list[RawAnalysisDocument] = field(default_factory=list)
    source_db: str = ""
    session_path: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["documents"] = [doc.to_dict() for doc in self.documents]
        return payload


@dataclass(frozen=True)
class Topic:
    title: str = ""
    category: list[str] = field(default_factory=list)
    location: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Fact:
    claim: str = ""
    source_title: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class Decision:
    text: str = ""
    status: str = ""
    vote_result: str = ""


@dataclass(frozen=True)
class FinancialEffect:
    description: str = ""
    amount: float | None = None
    percentage: float | None = None
    affected_group: str = ""


@dataclass(frozen=True)
class CitizenRelevance:
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredAnalysisOutput:
    """Machine-readable analysis payload for downstream workflows."""

    schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION_V2
    output_type: str = "structured_analysis"
    job_id: int = 0
    session_id: str = ""
    purpose: str = DEFAULT_ANALYSIS_PURPOSE
    topic: Topic = field(default_factory=Topic)
    facts: list[Fact] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    financial_effects: list[FinancialEffect] = field(default_factory=list)
    affected_groups: list[str] = field(default_factory=list)
    citizen_relevance: CitizenRelevance = field(default_factory=CitizenRelevance)
    open_questions: list[str] = field(default_factory=list)
    risks_or_uncertainties: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewStatus:
    required: bool = True
    status: str = "pending"
    notes: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""


@dataclass(frozen=True)
class PublicationStatus:
    target: str = "local_static_site"
    status: str = "not_published"
    published_url: str = ""
    published_at: str = ""


@dataclass(frozen=True)
class PublicationDraftOutput:
    """Journalistic publication draft with review/publication status."""

    schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION_V2
    output_type: str = "publication_draft"
    job_id: int = 0
    session_id: str = ""
    purpose: str = "journalistic_publication"
    title: str = ""
    summary_short: str = ""
    summary_long: str = ""
    body_markdown: str = ""
    hashtags: list[str] = field(default_factory=list)
    seo_keywords: list[str] = field(default_factory=list)
    slug: str = ""
    status: str = "draft"
    review: ReviewStatus = field(default_factory=ReviewStatus)
    publication: PublicationStatus = field(default_factory=PublicationStatus)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_analysis_output(data: dict) -> dict[str, object]:
    """Normalize v1/v2 analysis payloads for read compatibility.

    v1 files did not separate purpose and output type. They are exposed as
    legacy outputs with the default content-analysis purpose.
    """

    schema_version = str(data.get("schema_version") or ANALYSIS_OUTPUT_SCHEMA_VERSION)
    if schema_version.startswith("2"):
        normalized = dict(data)
        normalized.setdefault("purpose", DEFAULT_ANALYSIS_PURPOSE)
        return normalized

    return {
        "schema_version": ANALYSIS_OUTPUT_SCHEMA_VERSION,
        "output_type": "legacy_analysis_output",
        "purpose": DEFAULT_ANALYSIS_PURPOSE,
        "job_id": data.get("job_id", 0),
        "session_id": str(data.get("session_id") or ""),
        "scope": str(data.get("scope") or "session"),
        "top_numbers": list(data.get("top_numbers") or []),
        "prompt_template_id": str(data.get("prompt_template_id") or ""),
        "prompt_template_revision": data.get("prompt_template_revision"),
        "prompt_template_label": str(data.get("prompt_template_label") or ""),
        "rendered_prompt_snapshot_path": str(data.get("rendered_prompt_snapshot_path") or ""),
        "ki_response": str(data.get("ki_response") or ""),
        "markdown": str(data.get("markdown") or ""),
        "status": str(data.get("status") or ""),
        "session_date": str(data.get("session_date") or ""),
        "session_path": str(data.get("session_path") or ""),
    }
