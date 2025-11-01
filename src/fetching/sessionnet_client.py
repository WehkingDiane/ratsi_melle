"""HTTP client and parser for the SessionNet installation in Melle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

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

    base_url: str = "https://sessionnet.krz.de/melle/bi/"
    timeout: int = 30
    storage_root: Path = Path("data/raw")

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.storage_root = Path(self.storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    def fetch_month(self, year: int, month: int) -> List[SessionReference]:
        """Fetch overview page for a given month and parse session references."""

        LOGGER.info("Fetching session overview for %04d-%02d", year, month)
        response = self._get("si010.asp", params={"MM": f"{month:02d}", "YY": str(year)})
        content = response.text
        filename = self._build_month_filename(year, month)
        self._write_raw(filename, content)
        sessions = self._parse_overview(content)
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
        for document in documents:
            try:
                LOGGER.info("Downloading document %s", document.url)
                response = self._get(document.url)
            except FetchingError:
                LOGGER.exception("Failed to download document %s", document.url)
                continue
            filename = self._normalise_filename(document)
            path = target_dir / filename
            path.write_bytes(response.content)

    # ------------------------------------------------------------------
    # Parsing helpers
    def _parse_overview(self, html: str) -> List[SessionReference]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            LOGGER.warning("Overview page did not contain a table")
            return []

        sessions: List[SessionReference] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            detail_link = row.find("a", href=lambda value: value and "si005" in value)
            if not detail_link:
                continue

            committee = cells[0].get_text(strip=True)
            meeting_name = detail_link.get_text(strip=True)
            date_cell = cells[2].get_text(strip=True)
            time_cell = cells[3].get_text(strip=True)

            try:
                session_date = datetime.strptime(date_cell, "%d.%m.%Y").date()
            except ValueError:
                LOGGER.warning("Could not parse date %s for meeting %s", date_cell, meeting_name)
                continue

            detail_href = detail_link.get("href")
            if detail_href is None:
                continue

            detail_url = self._absolute_url(detail_href)
            session_id = self._extract_session_id(detail_url)

            agenda_link = row.find("a", href=lambda value: value and "to010" in value)
            agenda_url = self._absolute_url(agenda_link.get("href")) if agenda_link and agenda_link.get("href") else None

            docs_link = row.find("a", href=lambda value: value and "do010" in value)
            documents_url = self._absolute_url(docs_link.get("href")) if docs_link and docs_link.get("href") else None

            sessions.append(
                SessionReference(
                    committee=committee,
                    meeting_name=meeting_name,
                    session_id=session_id,
                    date=session_date,
                    start_time=time_cell or None,
                    detail_url=detail_url,
                    agenda_url=agenda_url,
                    documents_url=documents_url,
                )
            )

        return sessions

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
    def _normalise_filename(document: DocumentReference) -> str:
        slug = SessionNetClient._slugify(document.title or "document")
        return f"{slug}.bin"

    @staticmethod
    def _slugify(value: str) -> str:
        safe = [c if c.isalnum() else "-" for c in value]
        slug = "".join(safe)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-") or "document"

