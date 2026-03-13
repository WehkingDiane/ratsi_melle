"""Typed and versioned schemas for analysis inputs and outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


ANALYSIS_OUTPUT_SCHEMA_VERSION = "1.2"


@dataclass(frozen=True)
class AnalysisOutputRecord:
    """Versioned analysis output payload persisted for downstream consumers."""

    schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION
    job_id: int = 0
    created_at: str = ""
    session_id: str = ""
    scope: str = "session"
    top_numbers: list[str] = field(default_factory=list)
    model_name: str = ""
    prompt_version: str = ""
    prompt_text: str = ""
    markdown: str = ""
    document_count: int = 0
    source_db: str = ""
    mode: str = "journalistic_brief"
    parameters: dict[str, object] = field(default_factory=dict)
    document_hashes: list[dict[str, str]] = field(default_factory=list)
    uncertainty_flags: list[str] = field(default_factory=list)
    plausibility_flags: list[str] = field(default_factory=list)
    bias_metrics: dict[str, object] = field(default_factory=dict)
    hallucination_risk: str = "unknown"
    sources: list[dict[str, str]] = field(default_factory=list)
    sensitive_data_masked: bool = False
    draft_status: str = "draft"
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_notes: str = ""
    audit_trail: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
