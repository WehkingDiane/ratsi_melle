"""HTTP client and parser for the SessionNet installation in Melle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import logging
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from hashlib import sha1

from bs4 import BeautifulSoup
import requests

from .models import AgendaItem, DocumentReference, SessionDetail, SessionReference


LOGGER = logging.getLogger(__name__)


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
    storage_root: Path = Path("data/raw")
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
        response = self._get("si0040.asp", params={"month": f"{month:02d}", "year": str(year)})
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

    def download_documents(self, documents: Iterable[DocumentReference], reference: SessionReference) -> None:
        """Download all referenced documents to the raw data directory."""

        target_dir = self._build_session_directory(reference)
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, document in enumerate(documents, start=1):
            try:
                LOGGER.info("Downloading document %s", document.url)
                response = self._get(document.url)
            except FetchingError:
                LOGGER.exception("Failed to download document %s", document.url)
                continue
            filename = self._normalise_filename(document, index=index)
            path = target_dir / filename
            path.write_bytes(response.content)

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

        agenda_table = soup.find("table", class_=lambda value: value and "Tagesordnung" in value)
        if not agenda_table:
            agenda_table = soup.find("table", id=lambda value: value and "Tagesordnung" in value)
        if not agenda_table:
            agenda_table = soup.find("table", attrs={"summary": "Tagesordnung"})

        if agenda_table:
            for row in agenda_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                number = cells[0].get_text(strip=True)
                title = cells[1].get_text(" ", strip=True)
                status = cells[2].get_text(strip=True) if len(cells) > 2 else None
                documents = list(self._parse_documents(cells[-1]))
                agenda_items.append(AgendaItem(number=number, title=title, status=status, documents=documents))

        retrieved_at = datetime.utcnow()
        return SessionDetail(reference=reference, agenda_items=agenda_items, retrieved_at=retrieved_at, raw_html=html)

    def _parse_documents(self, container) -> Iterable[DocumentReference]:
        for link in container.find_all("a"):
            href = link.get("href")
            if not href or "do" not in href:
                continue
            title = link.get_text(strip=True)
            yield DocumentReference(title=title, url=self._absolute_url(href))

    # ------------------------------------------------------------------
    # Internal helpers
    def _get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        url = path if path.startswith("http") else urljoin(self.base_url, path)
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:  # pragma: no cover - thin wrapper
            raise FetchingError(str(exc)) from exc

    def _absolute_url(self, href: str) -> str:
        if not href:
            return href
        return urljoin(self.base_url, href)

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

    def _write_raw(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _normalise_filename(document: DocumentReference, *, index: Optional[int] = None) -> str:
        slug = SessionNetClient._slugify(document.title or "document")
        url_hash = sha1(document.url.encode("utf-8")).hexdigest()[:8]
        unique_parts: List[str] = []
        if index is not None:
            unique_parts.append(f"{index:03d}")
        unique_parts.append(url_hash)
        unique_suffix = "-".join(unique_parts)
        return f"{slug}-{unique_suffix}.bin"

    @staticmethod
    def _slugify(value: str) -> str:
        safe = [c if c.isalnum() else "-" for c in value]
        slug = "".join(safe)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-") or "document"

