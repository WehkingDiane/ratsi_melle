"""Bounded RI login verification; no document fetching or persistent HTTP session."""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from src.config.ri_proton import RiAccessError, RiCredentials

ORIGIN = "https://session.melle.info"
LOGIN = ORIGIN + "/ri/ylogon.asp"
PROTECTED = ORIGIN + "/ri/info.asp"
MAX_HTML = 1024 * 1024
_LOGOUT = re.compile(r"/ri/y(?:logoff|logout)\d*\.asp\Z", re.IGNORECASE)


def allowed_url(value: str) -> str:
    """Accept only the known HTTPS origin and login/status/logout endpoints."""
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https" or parts.hostname != "session.melle.info"
            or parts.port not in (None, 443) or parts.username or parts.password
            or parts.fragment or any(c in value for c in "\r\n\\")
            or (parts.path not in {"/ri/", "/ri/default.asp", "/ri/ylogon.asp", "/ri/ylogon2.asp", "/ri/info.asp"}
                and not _LOGOUT.fullmatch(parts.path))
        ):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise RiAccessError("RI-Seite verweist auf ein nicht freigegebenes Ziel; Zugriff abgebrochen.") from None


def login_payload(html: bytes, page_url: str, credentials: RiCredentials) -> tuple[str, dict[str, str]]:
    """Submit only the observed login fields, never password-change or recovery controls."""
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.select("form#smclogon")
    if len(forms) != 1:
        raise RiAccessError("Das erwartete RI-Anmeldeformular wurde nicht gefunden.")
    form = forms[0]
    action = allowed_url(urljoin(page_url, form.get("action", "")))
    if form.get("method", "get").casefold() != "post" or urlsplit(action).path != "/ri/ylogon2.asp":
        raise RiAccessError("RI-Anmeldeverfahren hat sich geändert; kein Passwort gesendet.")
    if len(form.select('input[name="pesch"]')) != 1 or len(form.select('input[name="pepwd"][type="password"]')) != 1:
        raise RiAccessError("RI-Anmeldefelder entsprechen nicht dem geprüften Verfahren.")
    data = {}
    for name in ("control1", "logongopn", "logongoqs", "smcsdasessionnettype"):
        fields = form.select(f'input[type="hidden"][name="{name}"]')
        if len(fields) != 1 or fields[0].has_attr("disabled"):
            raise RiAccessError("RI-Anmeldeformular ist unvollständig; kein Passwort gesendet.")
        data[name] = fields[0].get("value", "")
    submit = form.select('input[type="submit"][name="submit"]')
    if len(submit) != 1:
        raise RiAccessError("RI-Anmeldeschaltfläche ist nicht eindeutig.")
    data.update(pesch=credentials.username, pepwd=credentials.password,
                logongopn="info.asp", logongoqs="", submit=submit[0].get("value", ""))
    return action, data


class RiLoginProbe:
    """Use an in-memory cookie jar and a single password submission."""

    def __init__(self, session: requests.Session):
        self.session = session
        self.deadline = time.monotonic() + 90
        self.last_request = 0.0

    def _request(self, method: str, url: str, data=None):
        allowed_url(url)
        if method == "POST" and urlsplit(url).path != "/ri/ylogon2.asp":
            raise RiAccessError("Nicht erlaubte RI-Schreiboperation abgewiesen.")
        if method not in {"GET", "POST"}:
            raise RiAccessError("Nicht erlaubte RI-Operation abgewiesen.")
        wait = max(0, 1.0 - (time.monotonic() - self.last_request))
        if time.monotonic() + wait >= self.deadline:
            raise RiAccessError("Zeitlimit für die RI-Anmeldeprüfung erreicht.")
        if wait:
            time.sleep(wait)
        self.last_request = time.monotonic()
        try:
            with self.session.request(
                method, url, data=data, timeout=(10, 20), allow_redirects=False,
                stream=True, verify=True,
            ) as response:
                status = response.status_code
                location = response.headers.get("Location")
                if status in {301, 302, 303, 307, 308}:
                    if not location:
                        raise RiAccessError("RI-Weiterleitung ohne Ziel.")
                    target = allowed_url(urljoin(url, location))
                    if method == "POST" and status in {307, 308}:
                        raise RiAccessError("RI fordert erneute Passwortübermittlung; nicht automatisch wiederholt.")
                    return status, target, b""
                if status != 200:
                    raise RiAccessError("RI-Server hat den Zugriff nicht bestätigt.")
                if "text/html" not in response.headers.get("Content-Type", "").casefold():
                    raise RiAccessError("Unerwartete RI-Antwort; keine Datei wird heruntergeladen.")
                body = bytearray()
                for chunk in response.iter_content(8192):
                    body.extend(chunk)
                    if len(body) > MAX_HTML or time.monotonic() >= self.deadline:
                        raise RiAccessError("RI-Antwort überschreitet Größen- oder Zeitgrenze.")
                return status, None, bytes(body)
        except requests.RequestException:
            raise RiAccessError("RI-Server nicht erreichbar oder TLS-/Netzwerkfehler.") from None

    def get(self, url: str) -> tuple[str, bytes]:
        """Follow a bounded number of same-origin GET redirects."""
        for _ in range(6):
            status, target, body = self._request("GET", url)
            if target is None:
                return url, body
            url = target
        raise RiAccessError("Zu viele RI-Weiterleitungen.")

    @staticmethod
    def logout_link(html: bytes, page_url: str) -> str:
        """Require an explicit known logout link as evidence of an authenticated page."""
        soup = BeautifulSoup(html, "html.parser")
        if soup.select('input[type="password"]'):
            raise RiAccessError("RI-Anmeldung nicht bestätigt; Zugang oder zusätzliche Bestätigung prüfen. Kein weiterer Versuch.")
        candidates = []
        for anchor in soup.select("a[href]"):
            label = " ".join((anchor.get_text(" ", strip=True), anchor.get("title", ""), anchor.get("aria-label", "")))
            target = urljoin(page_url, anchor["href"])
            if re.search(r"\b(abmelden|logout)\b", label, re.IGNORECASE) and _LOGOUT.fullmatch(urlsplit(target).path):
                candidates.append(allowed_url(target))
        if len(set(candidates)) != 1:
            raise RiAccessError("Geschützte RI-Seite nicht eindeutig bestätigt; kein Dokumentabruf.")
        return candidates[0]

    def verify(self, credentials: RiCredentials) -> None:
        """Check login and logout without reading meetings or downloading documents."""
        page_url, html = self.get(LOGIN)
        action, data = login_payload(html, page_url, credentials)
        try:
            # Exactly one POST. Its redirect body is never resent.
            self._request("POST", action, data=data)
        finally:
            data.clear()
        page_url, html = self.get(PROTECTED)
        if urlsplit(page_url).path != "/ri/info.asp":
            raise RiAccessError("RI-Anmeldung nicht bestätigt; kein weiterer Anmeldeversuch.")
        logout = self.logout_link(html, page_url)
        self.get(logout)
        page_url, html = self.get(PROTECTED)
        if urlsplit(page_url).path != "/ri/ylogon.asp" or not BeautifulSoup(html, "html.parser").select('form#smclogon input[type="password"]'):
            raise RiAccessError("RI-Abmeldung nicht bestätigt; lokale Cookies werden verworfen.")


def verify_ri_login(credentials: RiCredentials) -> None:
    """Create a short-lived HTTPS session; never persist cookies, HTML or passwords."""
    with requests.Session() as session:
        session.trust_env = False
        session.headers.update({"User-Agent": "ratsi-melle-ri-login-check/0.1"})
        try:
            RiLoginProbe(session).verify(credentials)
        finally:
            session.cookies.clear()
