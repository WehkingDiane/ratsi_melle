"""Typed and versioned schemas for analysis inputs and outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


ANALYSIS_OUTPUT_SCHEMA_VERSION = "1.0"


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
    ki_response: str = ""
    document_count: int = 0
    source_db: str = ""
    session_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
