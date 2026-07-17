"""HTTP client and parsers for Landkreis Osnabrueck publication pages."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha1
import logging
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
import requests

from src.analysis.extraction_pipeline import extract_text_for_analysis
from src.fetching.landkreis.database import LandkreisPublicationStore
from src.fetching.landkreis.models import LandkreisDocument, LandkreisPublication
from src.fetching.landkreis.storage import LandkreisStorage


LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.landkreis-osnabrueck.de"
BEKANNTMACHUNGEN_PATH = "/verwaltung/veroeffentlichungen/bekanntmachungen"
AMTSBLAETTER_PATH = "/verwaltung/veroeffentlichungen/amtsblaetter"
DEFAULT_HEADERS = {"User-Agent": "ratsi-melle-landkreis-fetcher/0.1 (+https://github.com/openai)"}
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")


class LandkreisFetchingError(RuntimeError):
    """Raised when Landkreis fetching fails."""


class LandkreisClient:
    """Fetch Landkreis publication lists, detail pages and linked documents."""

    def __init__(
        self,
        *,
        storage: LandkreisStorage,
        store: LandkreisPublicationStore | None = None,
        base_url: str = BASE_URL,
        timeout: int = 30,
        min_request_interval: float = 1.0,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        max_document_bytes: int = MAX_DOCUMENT_BYTES,
    ) -> None:
        self.storage = storage
        self.store = store
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.max_document_bytes = max_document_bytes
        self._last_request_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def crawl(
        self,
        *,
        source: str,
        from_date: date | None = None,
        to_date: date | None = None,
        query: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        refresh_existing: bool = False,
    ) -> list[LandkreisPublication]:
        """Crawl one or all supported Landkreis publication sources."""

        sources = ("bekanntmachungen", "amtsblaetter") if source == "all" else (source,)
        publications: list[LandkreisPublication] = []
        for source_name in sources:
            for reference in self.iter_publication_references(source_name):
                if not _matches_filters(reference, from_date=from_date, to_date=to_date, query=query):
                    continue
                if limit is not None and len(publications) >= limit:
                    return publications
                if self.storage.has_manifest(reference) and not refresh_existing:
                    LOGGER.info("Skipping already fetched Landkreis publication %s", reference.title)
                    continue
                if dry_run:
                    publications.append(reference)
                    continue
                detail = self.fetch_publication(reference, refresh_existing=refresh_existing)
                publications.append(detail)
        return publications

    def iter_publication_references(self, source: str) -> Iterable[LandkreisPublication]:
        """Yield publication references from a list page."""

        if source == "bekanntmachungen":
            yield from self._iter_bekanntmachungen()
            return
        if source == "amtsblaetter":
            yield from self._iter_amtsblaetter()
            return
        raise ValueError(f"Unsupported Landkreis source: {source}")

    def fetch_publication(
        self,
        publication: LandkreisPublication,
        *,
        refresh_existing: bool = False,
    ) -> LandkreisPublication:
        """Fetch detail HTML and store raw publication data.

        Existing publications are skipped at crawl level unless
        ``refresh_existing`` is set. Bekanntmachungen keep only online metadata
        and detail HTML. Amtsblaetter additionally download linked documents,
        but existing local files are reused.
        """

        response = self._get(publication.detail_url)
        html = response.text
        page_text = _extract_page_text(html)
        html_path = self.storage.write_publication_html(publication, html)
        documents = self._parse_document_links(html, publication.detail_url)
        stored_documents = (
            self._download_documents(publication, documents, refresh_existing=refresh_existing)
            if publication.source == "amtsblaetter"
            else documents
        )
        now = _utc_now()
        stored = replace(
            publication,
            local_dir=self.storage.relative_path(html_path.parent),
            page_text=page_text,
            retrieved_at=now,
            documents=stored_documents,
        )
        self.storage.write_manifest(stored)
        if self.store is not None:
            self.store.upsert_publication(stored)
            self._extract_document_texts(stored_documents)
        return stored

    def parse_list(self, source: str, html: str, list_url: str) -> list[LandkreisPublication]:
        """Parse a raw list page for tests and crawlers."""

        soup = BeautifulSoup(html, "html.parser")
        if source == "amtsblaetter":
            return self._parse_amtsblaetter_list(soup, list_url)
        if source == "bekanntmachungen":
            return self._parse_bekanntmachungen_list(soup, list_url)
        raise ValueError(f"Unsupported Landkreis source: {source}")

    def _iter_bekanntmachungen(self) -> Iterable[LandkreisPublication]:
        page = 0
        seen_ids: set[str] = set()
        while True:
            path = BEKANNTMACHUNGEN_PATH if page == 0 else f"{BEKANNTMACHUNGEN_PATH}?page={page}"
            url = urljoin(self.base_url, path)
            response = self._get(url)
            self.storage.write_list_html("bekanntmachungen", f"page-{page}", response.text)
            entries = self.parse_list("bekanntmachungen", response.text, url)
            new_entries = [entry for entry in entries if entry.publication_id not in seen_ids]
            if not new_entries:
                break
            for entry in new_entries:
                seen_ids.add(entry.publication_id)
                yield entry
            if not _has_next_page(response.text):
                break
            page += 1

    def _iter_amtsblaetter(self) -> Iterable[LandkreisPublication]:
        url = urljoin(self.base_url, AMTSBLAETTER_PATH)
        response = self._get(url)
        self.storage.write_list_html("amtsblaetter", "index", response.text)
        yield from self.parse_list("amtsblaetter", response.text, url)

    def _parse_bekanntmachungen_list(self, soup: BeautifulSoup, list_url: str) -> list[LandkreisPublication]:
        candidates = _content_links(soup)
        entries: list[LandkreisPublication] = []
        for link in candidates:
            title = _clean_text(link.get_text(" ", strip=True))
            if not title or _is_navigation_link(title):
                continue
            href = link.get("href")
            if not href:
                continue
            detail_url = urljoin(self.base_url, href)
            if not _is_landkreis_content_url(detail_url):
                continue
            if "bekanntmachungen?page=" in detail_url:
                continue
            publication_date = _nearest_date(link)
            if publication_date is None:
                continue
            entries.append(
                LandkreisPublication(
                    source="bekanntmachungen",
                    publication_id=_publication_id("bekanntmachungen", detail_url, title, publication_date),
                    date=publication_date,
                    title=title,
                    detail_url=detail_url,
                    list_url=list_url,
                )
            )
        return _dedupe_publications(entries)

    def _parse_amtsblaetter_list(self, soup: BeautifulSoup, list_url: str) -> list[LandkreisPublication]:
        entries: list[LandkreisPublication] = []
        for link in _content_links(soup):
            title = _clean_text(link.get_text(" ", strip=True))
            if not re.match(r"^Amtsblatt\s+.+/\s*\d{4}$", title, re.IGNORECASE):
                continue
            href = link.get("href")
            if not href:
                continue
            detail_url = urljoin(self.base_url, href)
            publication_date = _nearest_date(link)
            entries.append(
                LandkreisPublication(
                    source="amtsblaetter",
                    publication_id=_publication_id("amtsblaetter", detail_url, title, publication_date),
                    date=publication_date,
                    title=title,
                    detail_url=detail_url,
                    list_url=list_url,
                )
            )
        return _dedupe_publications(entries)

    def _parse_document_links(self, html: str, detail_url: str) -> list[LandkreisDocument]:
        soup = BeautifulSoup(html, "html.parser")
        documents: list[LandkreisDocument] = []
        for link in soup.find_all("a", href=True):
            href = str(link.get("href") or "")
            text = _clean_text(link.get_text(" ", strip=True))
            absolute = urljoin(detail_url, href)
            if not _looks_like_document_link(absolute, text):
                continue
            documents.append(LandkreisDocument(title=text or Path(urlparse(absolute).path).name or "Dokument", url=absolute))
        return _dedupe_documents(documents)

    def _download_documents(
        self,
        publication: LandkreisPublication,
        documents: list[LandkreisDocument],
        *,
        refresh_existing: bool,
    ) -> list[LandkreisDocument]:
        stored: list[LandkreisDocument] = []
        for index, document in enumerate(documents, start=1):
            target = self.storage.document_path(publication, document.url, index)
            if target.exists():
                stored.append(
                    replace(
                        document,
                        local_path=self.storage.relative_path(target),
                        content_length=target.stat().st_size,
                    )
                )
                continue
            try:
                content, headers = self._download_document(document.url)
            except LandkreisFetchingError:
                LOGGER.exception("Failed to download Landkreis document %s", document.url)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            stored.append(
                replace(
                    document,
                    local_path=self.storage.relative_path(target),
                    content_type=headers.get("Content-Type"),
                    content_length=len(content),
                    sha1=sha1(content).hexdigest(),
                    retrieved_at=_utc_now(),
                )
            )
        return stored

    def _extract_document_texts(self, documents: list[LandkreisDocument]) -> None:
        if self.store is None:
            return
        rows_by_path = {row.get("local_path"): row for row in self.store.document_rows()}
        for document in documents:
            row = rows_by_path.get(document.local_path)
            if not row or not document.local_path:
                continue
            path = self.storage.resolve_relative_path(document.local_path)
            if path is None:
                continue
            result = extract_text_for_analysis(
                path,
                content_type=document.content_type,
                max_text_chars=200_000,
            )
            self.store.upsert_extraction(int(row["id"]), result.to_dict())

    def _get(self, url: str) -> requests.Response:
        return self._request("GET", url)

    def _download_document(self, url: str) -> tuple[bytes, dict[str, str]]:
        response = self._request("GET", url, stream=True)
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > self.max_document_bytes:
                raise LandkreisFetchingError(f"Document exceeds limit: {url}")
            chunks.append(chunk)
        return b"".join(chunks), dict(response.headers)

    def _request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            elapsed = time.monotonic() - self._last_request_ts
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                self._last_request_ts = time.monotonic()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff ** attempt)
        raise LandkreisFetchingError(f"Failed to fetch {url}: {last_error}") from last_error


def _content_links(soup: BeautifulSoup) -> list[Tag]:
    content = soup.find("main") or soup.find(id="main-content") or soup.find("article") or soup.body or soup
    return [link for link in content.find_all("a", href=True) if isinstance(link, Tag)]


def _nearest_date(link: Tag) -> date | None:
    for ancestor in [link.parent, link.parent.parent if link.parent else None, link.parent.parent.parent if link.parent and link.parent.parent else None]:
        if ancestor is None:
            continue
        parsed = _parse_first_date(ancestor.get_text(" ", strip=True))
        if parsed is not None:
            return parsed
    previous = link.find_previous(string=DATE_RE)
    if previous:
        return _parse_first_date(str(previous))
    return None


def _parse_first_date(value: str) -> date | None:
    match = DATE_RE.search(value)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _publication_id(source: str, detail_url: str, title: str, publication_date: date | None) -> str:
    key = f"{source}|{detail_url}|{title}|{publication_date.isoformat() if publication_date else ''}"
    return sha1(key.encode("utf-8")).hexdigest()


def _dedupe_publications(publications: list[LandkreisPublication]) -> list[LandkreisPublication]:
    seen: set[str] = set()
    result: list[LandkreisPublication] = []
    for publication in publications:
        if publication.publication_id in seen:
            continue
        seen.add(publication.publication_id)
        result.append(publication)
    return result


def _dedupe_documents(documents: list[LandkreisDocument]) -> list[LandkreisDocument]:
    seen: set[str] = set()
    result: list[LandkreisDocument] = []
    for document in documents:
        if document.url in seen:
            continue
        seen.add(document.url)
        result.append(document)
    return result


def _is_navigation_link(title: str) -> bool:
    normalized = title.strip().lower()
    return normalized in {
        "aktuelle seite 1",
        "nächste seite",
        "naechste seite",
        "letzte seite",
        "kontakt a-z",
        "dienstleistungen a-z",
        "druckversion",
    } or normalized.startswith("page ")


def _is_landkreis_content_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in {"www.landkreis-osnabrueck.de", "landkreis-osnabrueck.de"} and (
        parsed.path.startswith("/node/")
        or parsed.path.startswith("/verwaltung/veroeffentlichungen/")
        or parsed.path.startswith("/system/files")
    )


def _looks_like_document_link(url: str, text: str) -> bool:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    lower_url = url.lower()
    lower_text = text.lower()
    return (
        parsed.path.lower().endswith(".pdf")
        or "file" in query
        or "/system/files" in parsed.path.lower()
        or ".pdf" in lower_text
        or "anhang" in lower_text
    )


def _has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        text = _clean_text(link.get_text(" ", strip=True)).lower()
        if text in {"nächste seite", "naechste seite"}:
            return True
    return False


def _extract_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    content = soup.find("main") or soup.find("article") or soup.body or soup
    return _clean_text(content.get_text(" ", strip=True))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _matches_filters(
    publication: LandkreisPublication,
    *,
    from_date: date | None,
    to_date: date | None,
    query: str | None,
) -> bool:
    if from_date is not None and publication.date is not None and publication.date < from_date:
        return False
    if to_date is not None and publication.date is not None and publication.date > to_date:
        return False
    if query and query.lower() not in publication.title.lower():
        return False
    return True
