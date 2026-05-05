"""Typed prompt template models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    """Return a stable UTC timestamp for persisted prompt metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def bool_from_json(value: Any, default: bool = True) -> bool:
    """Return a bool for JSON values that may have been stored as strings."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "active", "aktiv"}:
            return True
        if normalized in {"0", "false", "no", "off", "inactive", "inaktiv"}:
            return False
    return bool(value)


@dataclass(frozen=True)
class PromptTemplate:
    """Prompt template metadata and text stored outside the public repository."""

    id: str
    label: str
    scope: str
    description: str
    prompt_text: str
    variables: list[str] = field(default_factory=list)
    is_active: bool = True
    owner_id: str = ""
    visibility: str = "private"
    revision: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptTemplate":
        """Build a template from persisted JSON data."""
        scope = data.get("scope")
        if isinstance(scope, list):
            scope = str(scope[0] if scope else "")
        variables = data.get("variables") or []
        if isinstance(variables, str):
            variables = [item.strip() for item in variables.split(",") if item.strip()]
        return cls(
            id=str(data.get("id") or ""),
            label=str(data.get("label") or ""),
            scope=str(scope or ""),
            description=str(data.get("description") or ""),
            prompt_text=str(data.get("prompt_text") or data.get("text") or ""),
            variables=[str(item).strip() for item in variables if str(item).strip()],
            is_active=bool_from_json(data.get("is_active"), default=True),
            owner_id=str(data.get("owner_id") or ""),
            visibility=str(data.get("visibility") or "private"),
            revision=int(data.get("revision") or 1),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)

    def with_revision_update(self) -> "PromptTemplate":
        """Return a copy with an incremented revision and fresh timestamp."""
        return PromptTemplate(
            id=self.id,
            label=self.label,
            scope=self.scope,
            description=self.description,
            prompt_text=self.prompt_text,
            variables=list(self.variables),
            is_active=self.is_active,
            owner_id=self.owner_id,
            visibility=self.visibility,
            revision=max(1, self.revision) + 1,
            created_at=self.created_at,
            updated_at=utc_now(),
        )
