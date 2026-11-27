"""Authenticated RI metadata transport with temporary credentials and automatic logout."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import re
import sys
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from src.config.ri_proton import ProtonRiSession, RiAccessError, read_token
from src.fetching import SessionNetClient
from src.fetching.ri_login import RiLoginProbe, LOGIN, PROTECTED, login_payload

from src.config.ri import BASE_URL, RI_ROOT


class RiPageUnavailable(RiAccessError):
    """A detail view is unavailable; it must not be indexed as an empty detail."""


def checked_metadata_url(url):
    """Accept only RI calendar/detail HTML, never download or modification endpoints."""
    p = urlsplit(url)
    if (p.scheme != 'https' or p.hostname != 'session.melle.info' or p.port not in (None, 443)
            or p.username or p.password or p.fragment or any(c in url for c in '\r\n\\')):
        raise RiAccessError('Nicht freigegebenes RI-Ziel abgewiesen.')
    if p.path in {'/ri/ylogon.asp', '/ri/ylogon2.asp'}:
        raise RiAccessError('RI-Anmeldung abgelaufen. Bitte den Build erneut mit gültigem Token starten.')
    values = parse_qsl(p.query, keep_blank_values=True)
    keys = [k for k, _ in values]
    if len(keys) != len(set(keys)):
        raise RiAccessError('Mehrdeutige RI-URL abgewiesen.')
    if p.path == '/ri/si0057.asp' and set(keys) == {'__ksinr'} and dict(values)['__ksinr'].isdecimal():
        return url
    calendar_keys = {'month', 'year', '__cjahr', '__cmonat', '__cmandant', '__canz', '__cselect'}
    if p.path == '/ri/si0040.asp' and set(keys) == calendar_keys and all(v.isdecimal() for _, v in values):
        return url
    raise RiPageUnavailable('RI-Detailansicht verweist auf eine andere, nicht untersuchte Ansicht.')


class RiOnlineClient(SessionNetClient):
    """Use the unchanged SessionNet parser with a logged-in, bounded HTML transport."""

    def _request(self, method, path, params=None, *, stream=False):
        if method.upper() != 'GET' or stream:
            raise RiAccessError('Dieser Online-Build erlaubt nur HTML-Metadaten, keine Dokumentdownloads.')
        url = urljoin(self.base_url, path)
        if params:
            url += ('&' if urlsplit(url).query else '?') + urlencode(params)
        expected_id = dict(parse_qsl(urlsplit(url).query)).get('__ksinr')
        for _ in range(6):
            checked_metadata_url(url)
            if expected_id and dict(parse_qsl(urlsplit(url).query)).get('__ksinr') != expected_id:
                raise RiPageUnavailable('Weiterleitung auf eine andere Sitzung/Ansicht; Detail bleibt ungeprüft.')
            self._respect_rate_limit()
            try:
                with self.session.get(url, timeout=(10, 20), allow_redirects=False, stream=True, verify=True) as response:
                    self._last_request_ts = time.monotonic()
                    if response.status_code in {301, 302, 303, 307, 308}:
                        target = response.headers.get('Location')
                        if not target:
                            raise RiPageUnavailable('RI-Weiterleitung ohne Ziel.')
                        url = checked_metadata_url(urljoin(url, target))
                        continue
                    if response.status_code in {401, 403}:
                        raise RiAccessError('RI-Zugriff abgelehnt; Anmeldung/Berechtigung prüfen.')
                    if response.status_code != 200:
                        raise RiPageUnavailable(f'RI-HTML-Ansicht nicht verfügbar (HTTP {response.status_code}).')
                    if 'text/html' not in response.headers.get('Content-Type', '').lower():
                        raise RiAccessError('Keine HTML-Antwort; Dokumentinhalt wird nicht gelesen.')
                    body = bytearray()
                    deadline = time.monotonic() + 45
                    for part in response.iter_content(8192):
                        body.extend(part)
                        if len(body) > 1024 * 1024 or time.monotonic() >= deadline:
                            raise RiAccessError('RI-HTML überschreitet Größen-/Zeitgrenze.')
            except requests.RequestException:
                raise RiAccessError('RI-Netzwerk-/TLS-Fehler; keine vertraulichen Fehlerdetails ausgegeben.') from None
            soup = BeautifulSoup(bytes(body), 'html.parser')
            if soup.select('form#smclogon input[type="password"]'):
                raise RiAccessError('RI-Anmeldung abgelaufen; Loginseite wird nicht als Sitzung gespeichert.')
            refresh = soup.find('meta', attrs={'http-equiv': re.compile('^refresh$', re.I)})
            match = re.search(r';\s*url\s*=\s*(.+)$', str(refresh.get('content', '')), re.I) if refresh else None
            if match:
                url = checked_metadata_url(urljoin(url, match.group(1).strip().strip('\"\'')))
                continue
            if expected_id:
                if not any(re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', h.get_text()) for h in soup.select('h1,h2,h3')):
                    raise RiPageUnavailable('Keine erkannte RI-Sitzungsansicht; nicht als leere Sitzung speichern.')
            elif soup.select_one('table#smc_page_si0040_contenttable1') is None:
                raise RiAccessError('RI-Kalendertabelle fehlt; kein leerer Kalender angenommen.')
            response._content = bytes(body)
            response._content_consumed = True
            response.encoding = soup.original_encoding or response.encoding or 'utf-8'
            return response
        raise RiPageUnavailable('Zu viele RI-Weiterleitungen.')


@contextmanager
def login(*, client_class=RiOnlineClient):
    """Log in once, yield a normal SessionNet client, then log out in all cases."""
    if sys.platform == 'linux':
        import os
        if os.geteuid() == 0:
            raise RiAccessError('Als normaler Benutzer starten, nicht mit sudo.')
    client = client_class(base_url=BASE_URL, storage_root=RI_ROOT / 'raw', persist_raw=False)
    client.session.trust_env = False
    client.session.headers['User-Agent'] = 'ratsi-melle-ri-online-build/0.1'
    client.ri_cleanup_warning = False
    client.proton_cleanup_warning = False
    logout_url = None
    submitted = False
    proton = None
    try:
        with ProtonRiSession(read_token()) as proton:
            credentials = proton.credentials()
            try:
                probe = RiLoginProbe(client.session)
                url, body = probe.get(LOGIN)
                action, data = login_payload(body, url, credentials)
            finally:
                credentials = None
            try:
                submitted = True
                _, target, body = probe._request('POST', action, data=data)
            finally:
                data.clear()
            url = action
            if target:
                url, body = probe.get(target)
            if urlsplit(url).path != '/ri/info.asp':
                url, body = probe.get(PROTECTED)
            logout_url = probe.logout_link(body, url)
            print('RI-Anmeldung erfolgreich.', flush=True)
            try:
                yield client
            finally:
                probe.deadline = time.monotonic() + 60
                try:
                    probe._request('GET', logout_url)
                    final, body = probe.get(PROTECTED)
                    denied = urlsplit(final).path == '/ri/ylogon.asp' and BeautifulSoup(body, 'html.parser').select('form#smclogon input[type="password"]')
                    client.ri_cleanup_warning = not bool(denied)
                except Exception:
                    client.ri_cleanup_warning = True
                print('RI-Abmeldung bestätigt.' if not client.ri_cleanup_warning else 'Hinweis: RI-Abmeldung nicht bestätigt.', flush=True)
    finally:
        # Also clean up if credential POST succeeded but subsequent validation failed.
        if submitted and logout_url is None:
            try:
                probe.deadline = time.monotonic() + 30
                probe._request('GET', BASE_URL + '/ylogoff.asp')
            except Exception:
                pass
        client.session.cookies.clear()
        client.session.close()
        client.proton_cleanup_warning = bool(proton and proton.cleanup_warning)
        if client.proton_cleanup_warning:
            print('Hinweis: Entfernte Proton-Abmeldung nicht bestätigt.', flush=True)
        elif proton is not None:
            print('Proton-Abmeldung bestätigt.', flush=True)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        with login() as client:
            print('Login-Test erfolgreich. Die Sitzung wird anschließend wieder abgemeldet.')
        return 2 if client.ri_cleanup_warning or client.proton_cleanup_warning else 0
    except RiAccessError as error:
        print(f'Abbruch: {error}', file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('Login abgebrochen.', file=sys.stderr)
        return 1
    except Exception:
        print('Abbruch: RI-Login fehlgeschlagen; keine vertraulichen Fehlerdetails ausgegeben.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
