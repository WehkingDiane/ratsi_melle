"""RI login tests never send network requests or use real account values."""

from types import SimpleNamespace
from pathlib import Path

import pytest
import requests

from src.config.ri_proton import RiAccessError, RiCredentials
from src.fetching import ri_login as ri

FORM = (Path(__file__).parent / 'fixtures' / 'ri_login_synthetic.html').read_bytes()
AUTH = b'<a href="ylogoff.asp">Abmelden</a><h1>Geschuetzter Einstieg</h1>'
CREDS = RiCredentials("synthetic-user", "synthetic-password")


class Response:
    def __init__(self, body=b"", *, status=200, location=None, content_type="text/html"):
        self.body = body
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.body


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.headers = {}
        self.cleared = False
        self.cookies = SimpleNamespace(clear=lambda: setattr(self, "cleared", True))

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, {**kwargs, "data": dict(kwargs["data"]) if kwargs.get("data") else None}))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture(autouse=True)
def no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(ri.time, "sleep", lambda delay: None)


def test_payload_keeps_csrf_but_never_changes_password_or_recovers_account():
    action, data = ri.login_payload(FORM, ri.LOGIN, CREDS)
    assert action == ri.ORIGIN + "/ri/ylogon2.asp"
    assert data["control1"] == "synthetic-csrf"
    assert data["pepwd"] == CREDS.password
    assert "pwdch_confirm" not in data
    assert "pwforgotten" not in data
    assert data["logongopn"] == "info.asp"


@pytest.mark.parametrize("target", [
    "http://session.melle.info/ri/ylogon2.asp", "https://foreign.invalid/ri/ylogon2.asp",
    "https://session.melle.info.evil.invalid/ri/ylogon2.asp", "https://user:pw@session.melle.info/ri/ylogon2.asp",
    "https://session.melle.info/bi/ylogon2.asp", "https://session.melle.info/ri/getfile.asp",
    "https://session.melle.info/ri/../bi/ylogon2.asp", "https://session.melle.info/ri/%2e%2e/ylogon2.asp",
])
def test_unapproved_targets_rejected(target):
    with pytest.raises(RiAccessError):
        ri.allowed_url(target)


def test_foreign_form_action_never_submits_password():
    html = FORM.replace(b'action="ylogon2.asp"', b'action="https://foreign.invalid/ri/ylogon2.asp"')
    session = Session([Response(html)])
    with pytest.raises(RiAccessError):
        ri.RiLoginProbe(session).verify(CREDS)
    assert [method for method, _, _ in session.calls] == ["GET"]


def test_success_requires_protected_marker_and_checks_logout(monkeypatch):
    session = Session([
        Response(FORM), Response(status=302, location="info.asp"), Response(AUTH),
        Response(status=302, location="default.asp"), Response(b"public landing"),
        Response(status=302, location="ylogon.asp"), Response(FORM),
    ])
    monkeypatch.setattr(ri.requests, "Session", lambda: session)
    ri.verify_ri_login(CREDS)
    posts = [call for call in session.calls if call[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2]["data"]["pesch"] == CREDS.username
    assert session.trust_env is False
    assert session.cleared
    for method, url, kwargs in session.calls:
        assert kwargs["allow_redirects"] is False
        assert kwargs["verify"] is True
        assert CREDS.password not in url
        assert "getfile" not in url


def test_failed_login_never_retries_password_and_clears_cookies(monkeypatch):
    session = Session([Response(FORM), Response(FORM), Response(status=302, location="ylogon.asp"), Response(FORM)])
    monkeypatch.setattr(ri.requests, "Session", lambda: session)
    with pytest.raises(RiAccessError):
        ri.verify_ri_login(CREDS)
    assert sum(method == "POST" for method, _, _ in session.calls) == 1
    assert session.cleared


@pytest.mark.parametrize("status", [307, 308])
def test_password_is_never_replayed_on_redirect(status):
    session = Session([Response(FORM), Response(status=status, location="ylogon2.asp")])
    with pytest.raises(RiAccessError, match="nicht automatisch wiederholt"):
        ri.RiLoginProbe(session).verify(CREDS)
    assert sum(method == "POST" for method, _, _ in session.calls) == 1


def test_cross_host_redirect_stops_before_following():
    session = Session([Response(FORM), Response(status=302, location="https://foreign.invalid/ri/info.asp")])
    with pytest.raises(RiAccessError):
        ri.RiLoginProbe(session).verify(CREDS)
    assert len(session.calls) == 2


def test_http_200_alone_is_not_proof_of_login():
    session = Session([Response(FORM), Response(b"ok"), Response(b"a public page")])
    with pytest.raises(RiAccessError, match="nicht eindeutig"):
        ri.RiLoginProbe(session).verify(CREDS)


@pytest.mark.parametrize("response", [Response(b"x" * (ri.MAX_HTML + 1)), Response(b"pdf", content_type="application/pdf")])
def test_oversized_or_non_html_response_is_rejected(response):
    with pytest.raises(RiAccessError):
        ri.RiLoginProbe(Session([response])).get(ri.LOGIN)


def test_network_error_never_exposes_native_details(capsys):
    error = requests.ConnectionError("synthetic-password private-cookie private-url")
    with pytest.raises(RiAccessError) as result:
        ri.RiLoginProbe(Session([error])).get(ri.LOGIN)
    assert "synthetic-password" not in str(result.value)
    assert "private" not in str(result.value) + repr(capsys.readouterr())
