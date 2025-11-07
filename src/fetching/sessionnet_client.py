"""HTTP client and parser for the SessionNet installation in Melle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
import json
import logging
import mimetypes
from itertools import count
import re
import shutil
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

from hashlib import sha1

from bs4 import BeautifulSoup
import requests

from .models import AgendaItem, DocumentReference, SessionDetail, SessionReference


LOGGER = logging.getLogger(__name__)


REPORTER_SPLIT_RE = re.compile(r"(?:[-–—]\s*)?\bBerichterstatt[-\w()/]*:?\s*", re.IGNORECASE)
ACCEPTED_DECISION_KEYWORDS = ("beschlossen", "angenommen", "zugestimmt")
REJECTED_DECISION_KEYWORDS = ("abgelehnt", "zurückgestellt", "vertagt", "ohne beschluss")


DEFAULT_HEADERS = {
    "User-Agent": "ratsi-melle-fetcher/0.1 (+https://github.com/openai)"
}


class FetchingError(RuntimeError):
    """Raised when fetching the external SessionNet pages fails."""


@dataclass(slots=True)
class SessionNetClient:
    """Client capable of crawling the SessionNet HTML pages."""

    base_url: str = "https://session.melle.info/bi"
    timeout: int = 30
    min_request_interval: float = 1.0  # seconds
    max_retries: int = 3
    retry_backoff: float = 1.5
    storage_root: Path = Path("data/raw")
    _last_request_ts: float = field(default=0.0, init=False, repr=False)
    _document_cache: Dict[str, Tuple[bytes, Dict[str, str]]] = field(default_factory=dict, init=False, repr=False)
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.base_url = self.base_url.rstrip("/") + "/"
        self.storage_root = Path(self.storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    def fetch_month(self, year: int, month: int) -> List[SessionReference]:
        """Fetch overview page for a given month and parse session references."""

        LOGGER.info("Fetching session overview for %04d-%02d", year, month)
        response = self._get("si0040.asp", params=self._build_month_params(year, month))
        content = response.text
        filename = self._build_month_filename(year, month)
        self._write_raw(filename, content)
        sessions = self._parse_overview(content, year, month)
        LOGGER.info("Parsed %d session references", len(sessions))
        return sessions

    def fetch_session(self, reference: SessionReference) -> SessionDetail:
        """Fetch the detailed view including agenda items for a session."""

        LOGGER.info("Fetching session detail for %s", reference.session_id)
        response = self._get(reference.detail_url)
        html = response.text
        session_detail = self._parse_session_detail(reference, html)
        self._write_raw(self._build_session_filename(reference), html)
        return session_detail

    def download_documents(self, detail: SessionDetail) -> None:
        """Download session-level and agenda documents into structured folders."""

        target_dir = self._build_session_directory(detail.reference)
        target_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ("session-documents", "agenda"):
            path = target_dir / subdir
            if path.exists():
                shutil.rmtree(path)
        manifest_entries = []
        sequence = count(1)

        def _store_document(document: DocumentReference, scope_dir: Path) -> None:
            scope_dir.mkdir(parents=True, exist_ok=True)
            try:
                content, headers = self._fetch_document_payload(document)
            except FetchingError:
                LOGGER.exception("Failed to download document %s", document.url)
                return

            file_extension = self._detect_extension(document, headers)
            index = next(sequence)
            filename = self._normalise_filename(document, index=index, extension=file_extension)
            path = scope_dir / filename
            path.write_bytes(content)
            digest = sha1(content).hexdigest()
            manifest_entries.append(
                {
                    "title": document.title,
                    "category": document.category,
                    "agenda_item": document.on_agenda_item,
                    "url": document.url,
                    "path": str(path.relative_to(target_dir)),
                    "sha1": digest,
                    "content_type": headers.get("Content-Type"),
                    "content_disposition": headers.get("Content-Disposition"),
                    "content_length": int(headers.get("Content-Length") or len(content)),
                }
            )

        session_docs_dir = target_dir / "session-documents"
        for document in detail.session_documents:
            _store_document(document, session_docs_dir)

        agenda_root = target_dir / "agenda"
        for agenda_item in detail.agenda_items:
            if not agenda_item.documents:
                continue
            agenda_dir = agenda_root / self._build_agenda_directory_name(agenda_item)
            for document in agenda_item.documents:
                _store_document(document, agenda_dir)

        self._write_manifest(target_dir, detail, manifest_entries)
        self._write_agenda_summary(target_dir, detail)

    # ------------------------------------------------------------------
    # Parsing helpers
    def _parse_overview(self, html: str, year: int, month: int) -> List[SessionReference]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table#smc_page_si0040_contenttable1")
        if table is None:
            LOGGER.warning("Overview page did not contain a table")
            return []

        sessions: List[SessionReference] = []
        for row in table.select("tr"):
            cell = row.select_one("td.silink")
            if cell is None:
                continue

            link_tag = cell.select_one("a.smc-link-normal")
            header_tag = cell.select_one("div.smc-el-h")

            title_tag = link_tag or header_tag
            title = title_tag.get_text(strip=True) if title_tag else None
            if not title:
                continue

            committee = header_tag.get_text(strip=True) if header_tag else title

            detail_href = link_tag.get("href") if link_tag and link_tag.has_attr("href") else None
            if not detail_href:
                LOGGER.debug("Skipping event %s without detail link", title)
                continue

            detail_url = self._absolute_url(detail_href)
            session_id = self._extract_session_id(detail_url)

            day_tag = row.select_one("span.weekday")
            session_date = self._parse_day_value(day_tag.get_text(strip=True) if day_tag else None, year, month)
            if session_date is None:
                LOGGER.warning("Could not parse date for meeting %s", title)
                continue

            details = [li.get_text(strip=True) for li in cell.select("ul li")]
            start_time = details[0] if details else None
            location = details[1] if len(details) > 1 else None

            sessions.append(
                SessionReference(
                    committee=committee,
                    meeting_name=title,
                    session_id=session_id,
                    date=session_date,
                    start_time=start_time,
                    detail_url=detail_url,
                    agenda_url=None,
                    documents_url=None,
                    location=location,
                )
            )

        return sessions

    def _parse_day_value(self, day_text: Optional[str], year: int, month: int) -> Optional[date]:
        if not day_text:
            return None

        cleaned = "".join(ch for ch in day_text if ch.isdigit())
        if not cleaned:
            return None

        try:
            day_number = int(cleaned)
            return date(year, month, day_number)
        except ValueError:
            return None

    def _parse_session_detail(self, reference: SessionReference, html: str) -> SessionDetail:
        soup = BeautifulSoup(html, "html.parser")
        agenda_items: List[AgendaItem] = []
        agenda_table = self._find_agenda_table(soup)

        if agenda_table:
            for row in agenda_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                number = cells[0].get_text(strip=True)
                title, reporter = self._extract_title_and_reporter(cells[1])
                status = cells[2].get_text(strip=True) if len(cells) > 2 else None
                documents = list(self._parse_documents(cells[-1], agenda_label=number or None))
                agenda_items.append(
                    AgendaItem(number=number, title=title, status=status, reporter=reporter, documents=documents)
                )

        session_documents = list(self._parse_session_documents(soup))

        retrieved_at = datetime.now(UTC)
        return SessionDetail(
            reference=reference,
            agenda_items=agenda_items,
            session_documents=session_documents,
            retrieved_at=retrieved_at,
            raw_html=html,
        )

    def _extract_title_and_reporter(self, cell) -> Tuple[str, Optional[str]]:
        raw_text = cell.get_text("\n", strip=True)
        title, reporter = self._split_title_and_reporter(raw_text)
        if title:
            return title, reporter

        fallback_text = cell.get_text(" ", strip=True)
        title, reporter = self._split_title_and_reporter(fallback_text)
        return title or fallback_text or "Tagesordnungspunkt", reporter

    def _find_agenda_table(self, soup: BeautifulSoup):
        agenda_table = soup.find("table", class_=lambda value: value and "Tagesordnung" in value)
        if not agenda_table:
            agenda_table = soup.find("table", id=lambda value: value and "Tagesordnung" in value)
        if not agenda_table:
            agenda_table = soup.find("table", attrs={"summary": "Tagesordnung"})
        if not agenda_table:
            agenda_table = soup.select_one("table.smctablesitzung")
        if not agenda_table:
            agenda_table = soup.select_one("table#smc_page_si0057_contenttable2")
        return agenda_table

    def _parse_session_documents(self, soup: BeautifulSoup) -> Iterable[DocumentReference]:
        for block in soup.select("div.smc-documents div.smc-dg-ds-1"):
            icon = block.select_one("div.smc-doc-icon i")
            category_text = icon.get_text(strip=True) if icon else None
            category = category_text or None
            content = block.select_one("div.smc-doc-content")
            if not content:
                continue
            yield from self._parse_documents(content, category=category)

    def _parse_documents(
        self,
        container,
        *,
        agenda_label: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Iterable[DocumentReference]:
        collected: Dict[str, Tuple[DocumentReference, bool]] = {}
        for link in container.find_all("a"):
            href = link.get("href")
            if not self._is_document_link(href):
                continue
            url = self._absolute_url(href)
            title_text = link.get_text(strip=True)
            title = title_text or link.get("title") or "Dokument"
            has_visible_title = bool(title_text)
            document = DocumentReference(title=title, url=url, category=category, on_agenda_item=agenda_label)
            existing = collected.get(url)
            if existing:
                _, existing_has_title = existing
                if existing_has_title:
                    continue
                if has_visible_title:
                    collected[url] = (document, True)
                continue
            collected[url] = (document, has_visible_title)

        for document, _ in collected.values():
            yield document

    # ------------------------------------------------------------------
    # Internal helpers
    def _fetch_document_payload(self, document: DocumentReference) -> Tuple[bytes, Dict[str, str]]:
        cached = self._document_cache.get(document.url)
        if cached:
            LOGGER.debug("Reusing cached document %s", document.url)
            return cached

        LOGGER.info("Downloading document %s", document.url)
        response = self._get(document.url)
        headers = {k: v for k, v in response.headers.items()}
        payload = (response.content, headers)
        self._document_cache[document.url] = payload
        return payload

    def _respect_rate_limit(self) -> None:
        if self.min_request_interval <= 0:
            return
        if self._last_request_ts <= 0:
            return
        elapsed = time.monotonic() - self._last_request_ts
        delay = self.min_request_interval - elapsed
        if delay > 0:
            time.sleep(delay)

    def _get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        url = path if path.startswith("http") else urljoin(self.base_url, path)
        last_error: Optional[requests.RequestException] = None
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            self._respect_rate_limit()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                self._last_request_ts = time.monotonic()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:  # pragma: no cover - thin wrapper
                self._last_request_ts = time.monotonic()
                last_error = exc
                if attempt >= self.max_retries:
                    raise FetchingError(str(exc)) from exc
                LOGGER.warning(
                    "Request failed (%d/%d) for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                time.sleep(backoff)
                backoff *= self.retry_backoff
        raise FetchingError(str(last_error)) from last_error

    def _absolute_url(self, href: str) -> str:
        if not href:
            return href
        return urljoin(self.base_url, href)

    @staticmethod
    def _is_document_link(href: Optional[str]) -> bool:
        if not href:
            return False
        lower = href.lower()
        return "type=do" in lower or "getfile.asp" in lower

    @staticmethod
    def _extract_session_id(detail_url: str) -> str:
        parsed = urlparse(detail_url)
        query = parse_qs(parsed.query)
        for key in ("SID", "SILFDNR", "__kvid", "__ksinr"):
            value = query.get(key)
            if value:
                return value[0]
        return detail_url

    def _build_month_filename(self, year: int, month: int) -> Path:
        directory = self.storage_root / str(year)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{year:04d}-{month:02d}_overview.html"

    def _build_session_directory(self, reference: SessionReference) -> Path:
        directory = self.storage_root / str(reference.date.year)
        directory.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(f"{reference.date.isoformat()}_{reference.committee}_{reference.session_id}")
        path = directory / slug
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _build_session_filename(self, reference: SessionReference) -> Path:
        directory = self._build_session_directory(reference)
        return directory / "session_detail.html"

    def _build_agenda_directory_name(self, agenda_item: AgendaItem) -> str:
        title = agenda_item.title or ""
        cleaned_title, _ = self._split_title_and_reporter(title)
        cleaned_title = cleaned_title or title or "TOP"
        parts = [part for part in (agenda_item.number, cleaned_title) if part]
        base = "_".join(parts) if parts else "TOP"
        return self._slugify(base, max_length=120)

    def _detect_extension(self, document: DocumentReference, headers: Dict[str, str]) -> str:
        content_type = headers.get("Content-Type")
        extension: Optional[str] = None
        if content_type:
            guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if guessed:
                extension = guessed

        if not extension or extension == ".bin":
            parsed = urlparse(document.url)
            suffix = Path(parsed.path).suffix
            if suffix and suffix.lower() not in {".asp"}:
                extension = suffix

        title = document.title or ""
        if (not extension or extension == ".bin") and "pdf" in title.lower():
            extension = ".pdf"

        return extension or ".bin"

    def _write_manifest(self, session_dir: Path, detail: SessionDetail, documents: List[dict]) -> None:
        manifest = {
            "session": {
                "id": detail.reference.session_id,
                "committee": detail.reference.committee,
                "meeting_name": detail.reference.meeting_name,
                "date": detail.reference.date.isoformat(),
                "detail_url": detail.reference.detail_url,
                "location": detail.reference.location,
            },
            "retrieved_at": self._format_timestamp(detail.retrieved_at),
            "documents": documents,
        }
        manifest_path = session_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_agenda_summary(self, session_dir: Path, detail: SessionDetail) -> None:
        agenda_entries = []
        for item in detail.agenda_items:
            title = self._normalise_whitespace(item.title or "") or "Tagesordnungspunkt"
            agenda_entries.append(
                {
                    "number": item.number,
                    "title": title,
                    "reporter": item.reporter,
                    "status": item.status,
                    "decision": self._derive_decision_outcome(item.status),
                    "documents_present": bool(item.documents),
                }
            )

        summary = {
            "session": {
                "id": detail.reference.session_id,
                "committee": detail.reference.committee,
                "meeting_name": detail.reference.meeting_name,
                "date": detail.reference.date.isoformat(),
            },
            "generated_at": self._format_timestamp(detail.retrieved_at),
            "agenda_items": agenda_entries,
        }

        summary_path = session_dir / "agenda_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_raw(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _build_month_params(year: int, month: int) -> dict:
        """Construct the parameter set required by the SessionNet overview page."""

        return {
            "month": f"{month:02d}",
            "year": str(year),
            "__cjahr": str(year),
            "__cmonat": f"{month:02d}",
            "__cmandant": "2",
            "__canz": "1",
            "__cselect": "0",
        }

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        if value.tzinfo is None:
            timestamp = value.replace(tzinfo=UTC)
        else:
            timestamp = value.astimezone(UTC)
        return timestamp.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _derive_decision_outcome(status: Optional[str]) -> Optional[str]:
        if not status:
            return None
        normalised = SessionNetClient._normalise_status_text(status)
        if any(keyword in normalised for keyword in ACCEPTED_DECISION_KEYWORDS):
            return "accepted"
        if any(keyword in normalised for keyword in REJECTED_DECISION_KEYWORDS):
            return "rejected"
        return None

    @classmethod
    def _split_title_and_reporter(cls, text: str) -> Tuple[str, Optional[str]]:
        if not text:
            return "", None
        match = REPORTER_SPLIT_RE.search(text)
        if not match:
            return cls._normalise_whitespace(text), None

        title = text[: match.start()].rstrip(" -–—,:;\n\r\t")
        reporter = text[match.end() :].lstrip(" :;-–—\n\r\t")
        return cls._normalise_whitespace(title), cls._normalise_whitespace(reporter) or None

    @staticmethod
    def _normalise_whitespace(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _normalise_status_text(value: str) -> str:
        normalised = value.lower()
        replacements = {
            "ß": "ss",
            "ä": "ae",
            "ö": "oe",
            "ü": "ue",
        }
        for original, replacement in replacements.items():
            normalised = normalised.replace(original, replacement)
        return normalised

    @staticmethod
    def _normalise_filename(
        document: DocumentReference,
        *,
        index: Optional[int] = None,
        extension: str = ".bin",
    ) -> str:
        slug = SessionNetClient._slugify(document.title or "document", max_length=100)
        url_hash = sha1(document.url.encode("utf-8")).hexdigest()[:8]
        unique_parts: List[str] = []
        if index is not None:
            unique_parts.append(f"{index:03d}")
        unique_parts.append(url_hash)
        unique_suffix = "-".join(unique_parts)
        suffix = extension if extension.startswith(".") else f".{extension}"
        return f"{slug}-{unique_suffix}{suffix}"

    @staticmethod
    def _slugify(value: str, max_length: Optional[int] = None) -> str:
        safe = [c if c.isalnum() else "-" for c in value]
        slug = "".join(safe)
        while "--" in slug:
            slug = slug.replace("--", "-")
        slug = slug.strip("-") or "document"
        if max_length and len(slug) > max_length:
            hash_suffix = sha1(slug.encode("utf-8")).hexdigest()[:6]
            cutoff = max_length - len(hash_suffix) - 1
            slug = f"{slug[:cutoff].rstrip('-')}-{hash_suffix}"
        return slug

