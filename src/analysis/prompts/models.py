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


def scopes_from_json(*values: Any) -> list[str]:
    """Return normalized scope values from current or legacy JSON fields."""
    scopes: list[str] = []
    for value in values:
        if isinstance(value, list):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            scope = str(candidate or "").strip()
            if scope and scope not in scopes:
                scopes.append(scope)
    return scopes


@dataclass(frozen=True)
class PromptTemplate:
    """Prompt template metadata and text stored outside the public repository."""

    id: str
    label: str
    scope: str
    description: str
    prompt_text: str
    variables: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    is_active: bool = True
    owner_id: str = ""
    visibility: str = "private"
    revision: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptTemplate":
        """Build a template from persisted JSON data."""
        scopes = scopes_from_json(data.get("scope"), data.get("scopes"))
        variables = data.get("variables") or []
        if isinstance(variables, str):
            variables = [item.strip() for item in variables.split(",") if item.strip()]
        return cls(
            id=str(data.get("id") or ""),
            label=str(data.get("label") or ""),
            scope=scopes[0] if scopes else "",
            description=str(data.get("description") or ""),
            prompt_text=str(data.get("prompt_text") or data.get("text") or ""),
            variables=[str(item).strip() for item in variables if str(item).strip()],
            scopes=scopes,
            is_active=bool_from_json(data.get("is_active"), default=True),
            owner_id=str(data.get("owner_id") or ""),
            visibility=str(data.get("visibility") or "private"),
            revision=int(data.get("revision") or 1),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["scopes"] = self.all_scopes
        return data

    @property
    def all_scopes(self) -> list[str]:
        """Return every scope this template is valid for."""
        return scopes_from_json(self.scope, self.scopes)

    def matches_scope(self, scope: str) -> bool:
        """Return whether this template can be used for the given scope."""
        return scope in self.all_scopes

    def with_revision_update(self) -> "PromptTemplate":
        """Return a copy with an incremented revision and fresh timestamp."""
        return PromptTemplate(
            id=self.id,
            label=self.label,
            scope=self.scope,
            description=self.description,
            prompt_text=self.prompt_text,
            variables=list(self.variables),
            scopes=list(self.all_scopes),
            is_active=self.is_active,
            owner_id=self.owner_id,
            visibility=self.visibility,
            revision=max(1, self.revision) + 1,
            created_at=self.created_at,
            updated_at=utc_now(),
        )
