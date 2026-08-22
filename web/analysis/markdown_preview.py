"""Safe server-side Markdown rendering for analysis previews."""

from __future__ import annotations

import bleach
import markdown
from django.utils.safestring import SafeString
from django.utils.safestring import mark_safe


ALLOWED_TAGS = {
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4",
    "h5", "h6", "hr", "li", "ol", "p", "pre", "strong", "table", "tbody",
    "td", "th", "thead", "tr", "ul",
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}


def render_markdown_preview(value: str) -> SafeString:
    """Render Markdown and remove unsafe HTML, attributes, and URL schemes."""

    rendered = markdown.markdown(
        value or "",
        extensions=["extra", "sane_lists"],
        output_format="html",
    )
    cleaned = bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )
    return mark_safe(cleaned)
