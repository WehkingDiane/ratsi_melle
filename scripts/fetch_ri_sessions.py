"""Sitzungen und Dokumente des Ratsbereichs in den lokalen RI-Bestand laden."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, urljoin, urlsplit

from requests import RequestException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fetching.ri_session import BASE_URL, RI_ROOT, RiOnlineClient, RiPageUnavailable, login
from src.config.ri import configure_file_logging
from src.config.ri_proton import RiAccessError
from src.fetching import FetchingError, SessionNetClient

from src.config.ri import select_months


def document_id(url):
    """Extract an unambiguous SessionNet document ID, independent of BI/RI path."""
    parsed = urlsplit(url)
    values = parse_qs(parsed.query, keep_blank_values=True).get('id', [])
    if (parsed.scheme != 'https' or parsed.netloc != 'session.melle.info'
            or parsed.path.lower() not in {'/bi/getfile.asp', '/ri/getfile.asp'}
            or len(values) != 1 or not values[0].isascii() or not values[0].isdigit()):
        return None
    return str(int(values[0]))


def fetch_public_document_ids(reference):
    """Read only public session HTML using a separate session without RI cookies."""
    if not reference.session_id.isascii() or not reference.session_id.isdigit():
        raise ValueError('Ungültige Sitzungs-ID')
    url = 'https://session.melle.info/bi/si0057.asp?__ksinr=' + reference.session_id
    public = SessionNetClient(persist_raw=False)
    public.session.trust_env = False
    try:
        with public.session.get(url, timeout=(10, 20), stream=True,
                                allow_redirects=False, verify=True) as response:
            if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('BI-Sitzungsseite nicht verfügbar')
            body = bytearray()
            deadline = time.monotonic() + 45
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > 1024 * 1024 or time.monotonic() >= deadline:
                    raise ValueError('BI-Seite überschreitet Größen-/Zeitgrenze')
            html = bytes(body).decode(response.encoding or 'utf-8', errors='replace')
        if not public.contains_agenda_table(html):
            raise ValueError('Keine erkannte BI-Sitzungsansicht')
        detail = public.parse_session_detail(replace(reference, detail_url=url), html)
        documents = list(detail.session_documents)
        for item in detail.agenda_items:
            documents.extend(item.documents)
        return {identifier for doc in documents if (identifier := document_id(doc.url)) is not None}
    finally:
        public.session.close()


class RiFetchClient(RiOnlineClient):
    """Keep the checked HTML transport and allow RI document downloads."""

    def download_documents(self, detail, *, force_download=False):
        """Classify document IDs against BI before downloading or reusing files."""
        self._public_document_ids = set()
        self._bi_comparison_status = 'fehlgeschlagen'
        try:
            self._public_document_ids = fetch_public_document_ids(detail.reference)
            self._bi_comparison_status = 'erfolgreich'
            logging.info('BI-Abgleich Sitzung %s: %d öffentliche Dokument-IDs',
                         detail.reference.session_id, len(self._public_document_ids))
        except Exception:
            logging.warning('BI-Abgleich Sitzung %s fehlgeschlagen; alle Dokumente als nicht öffentlich kennzeichnen.',
                            detail.reference.session_id)
        self._visibility_checked_at = datetime.now(timezone.utc).isoformat()
        return super().download_documents(detail, force_download=force_download)

    def _write_manifest(self, session_dir, detail, documents, *, completion_detected_at=None):
        """Persist IDs and visibility also for reused files and retained error entries."""
        enriched = []
        for entry in documents:
            identifier = document_id(entry['url'])
            enriched.append({
                **entry,
                'document_id': identifier,
                'visibility': 'öffentlich' if identifier is not None and identifier in self._public_document_ids else 'nicht öffentlich',
                'visibility_checked_at': self._visibility_checked_at,
                'bi_comparison_status': self._bi_comparison_status,
            })
        super()._write_manifest(session_dir, detail, enriched,
                                completion_detected_at=completion_detected_at)

    def _request(self, method, path, params=None, *, stream=False):
        if method.upper() == 'GET' and not stream:
            return super()._request(method, path, params=params)
        if method.upper() not in {'GET', 'HEAD'} or params:
            raise RiAccessError('Nicht unterstützter RI-Dokumentaufruf.')
        url = urljoin(self.base_url, path)
        for _ in range(6):
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or parsed.netloc != 'session.melle.info'
                    or parsed.path.lower() != '/ri/getfile.asp' or parsed.fragment
                    or any(c in url for c in '\r\n\\')):
                raise RiAccessError('Nicht freigegebenes RI-Dokumentziel oder abgelaufene Anmeldung.')
            self._respect_rate_limit()
            try:
                response = self.session.request(method, url, timeout=(10, 30),
                                                allow_redirects=False, stream=True, verify=True)
            except RequestException:
                raise FetchingError('RI-Dokumentanfrage wegen eines Verbindungsfehlers fehlgeschlagen.') from None
            finally:
                self._last_request_ts = time.monotonic()
            if response.status_code in {301, 302, 303, 307, 308}:
                target = response.headers.get('Location')
                response.close()
                if not target:
                    raise RiAccessError('RI-Dokumentweiterleitung ohne Ziel.')
                url = urljoin(url, target)
                continue
            if response.status_code in {401, 403}:
                response.close()
                raise RiAccessError('RI-Dokument nicht verfügbar; Anmeldung/Berechtigung prüfen.')
            if response.status_code != 200:
                status = response.status_code
                response.close()
                raise FetchingError(f'RI-Dokumentdownload fehlgeschlagen (HTTP {status}).')
            if 'text/html' in response.headers.get('Content-Type', '').lower():
                response.close()
                raise RiAccessError('RI-Dokument nicht verfügbar; Anmeldung/Berechtigung prüfen.')
            return response
        raise RiAccessError('Zu viele RI-Dokumentweiterleitungen.')


@dataclass
class FetchResult:
    """Incomplete session views and document downloads encountered during a run."""

    skipped_sessions: list[str] = field(default_factory=list)
    failed_documents: list[tuple[str, str]] = field(default_factory=list)


def fetch_months(client, year, months, *, force_download=False):
    """Download available details and report unsupported views without losing progress."""
    months = tuple(months)
    result = FetchResult()
    completed = 0
    for month_index, month in enumerate(months, start=1):
        logging.info('Fetching %04d month %02d (%d/%d)', year, month, month_index, len(months))
        references = client.fetch_month(year=year, month=month)
        logging.info('Found %d sessions for %04d-%02d', len(references), year, month)
        for session_index, reference in enumerate(references, start=1):
            logging.info('Fetching session %s (%d/%d in month)',
                         reference.session_id, session_index, len(references))
            try:
                detail = client.fetch_session(reference)
            except RiPageUnavailable:
                result.skipped_sessions.append(reference.session_id)
                logging.warning('Sitzung %s: Detailansicht ungeprüft; übersprungen, keine Dokumente geladen.',
                                reference.session_id)
                continue
            failures = client.download_documents(detail, force_download=force_download) or []
            if failures:
                identifiers = dict.fromkeys(document_id(doc.url) or 'unbekannt' for doc in failures)
                for identifier in identifiers:
                    result.failed_documents.append((reference.session_id, identifier))
                    logging.warning('Sitzung %s: Dokument %s nicht vollständig heruntergeladen.',
                                    reference.session_id, identifier)
            else:
                completed += 1
    logging.info('RI-Abruf beendet: vollständige_sitzungen=%d Monate=%d übersprungen=%d dokumentfehler=%d',
                 completed, len(months), len(result.skipped_sessions), len(result.failed_documents))
    if result.skipped_sessions:
        logging.warning('Ungeprüfte Sitzungen: %s', ', '.join(result.skipped_sessions))
    return result


def main(argv=None):
    """Download selected accessible months with automatic login and cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('year', type=int)
    parser.add_argument('--months', type=int, nargs='+', default=tuple(range(1, 13)))
    parser.add_argument('--force-download', action='store_true')
    parser.add_argument('--log-level', default=None)
    args = parser.parse_args(argv)
    try:
        months = select_months(args.year, args.months)
        configure_file_logging(Path(__file__).stem, args.log_level)
        if tuple(args.months) != months:
            logging.info('Monatsauswahl auf zugängliche Monate begrenzt: %s', months)
        with login(client_class=RiFetchClient) as client:
            client.persist_raw = True
            result = fetch_months(client, args.year, months, force_download=args.force_download)
        if result.skipped_sessions:
            print(f'Hinweis: {len(result.skipped_sessions)} Sitzungen übersprungen; IDs siehe Abrufprotokoll.')
        if result.failed_documents:
            identifiers = ', '.join(f'{session_id}/{identifier}' for session_id, identifier in result.failed_documents)
            print(f'Hinweis: Dokumentdownloads unvollständig (Sitzung/Dokument): {identifiers}')
        return 2 if (result.skipped_sessions or result.failed_documents
                     or client.ri_cleanup_warning or client.proton_cleanup_warning) else 0
    except RiAccessError as error:
        print(f'Abbruch: {error}', file=sys.stderr)
        return 1
    except (Exception, KeyboardInterrupt):
        print('RI-Abruf abgebrochen; keine vertraulichen Fehlerdetails ausgegeben.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
