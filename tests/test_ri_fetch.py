"""Offline checks for the isolated RI downloader."""
from pathlib import Path

import pytest

from scripts import fetch_ri_sessions as fetch

@pytest.fixture
def config(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{"earliest_month": "2026-11"}')
    return path


@pytest.mark.integration
def test_year_is_clipped(config):
    assert fetch.select_months(2026, range(1, 13), config) == (11, 12)
    assert fetch.select_months(2027, range(1, 13), config) == tuple(range(1, 13))


@pytest.mark.parametrize('year,months', [(2025, [12]), (2026, [10]), (2026, [0]), (2026, [])])
@pytest.mark.integration
def test_unavailable_selection_rejected(config, year, months):
    with pytest.raises(fetch.RiAccessError):
        fetch.select_months(year, months, config)


@pytest.mark.integration
def test_invalid_config_fails_closed(config):
    config.write_text('{"earliest_month": "2026-13"}')
    with pytest.raises(fetch.RiAccessError):
        fetch.select_months(2026, [11], config)


@pytest.mark.parametrize('url', ['https://example.org/ri/getfile.asp?id=1',
                               'https://session.melle.info/ri/ylogon.asp',
                               'https://session.melle.info/bi/getfile.asp?id=1'])
@pytest.mark.integration
def test_document_target_checked_before_request(url, tmp_path):
    client = fetch.RiFetchClient(base_url=fetch.BASE_URL, storage_root=tmp_path, persist_raw=False)
    with pytest.raises(fetch.RiAccessError):
        client._request('GET', url, stream=True)


@pytest.mark.integration
def test_main_uses_login_and_download_flow(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.ri.RI_ROOT", tmp_path)
    from contextlib import contextmanager
    from types import SimpleNamespace
    events = []
    client = SimpleNamespace(persist_raw=False, ri_cleanup_warning=False, proton_cleanup_warning=False)

    @contextmanager
    def fake_login(*, client_class):
        assert client_class is fetch.RiFetchClient
        events.append('login')
        try:
            yield client
        finally:
            events.append('logout')

    def fake_fetch(actual, year, months, *, force_download):
        assert actual is client and actual.persist_raw
        assert (year, months, force_download) == (2026, (11, 12), True)
        events.append('download')
        return fetch.FetchResult()

    monkeypatch.setattr(fetch, 'login', fake_login)
    monkeypatch.setattr(fetch, 'fetch_months', fake_fetch)
    monkeypatch.setattr(fetch, 'configure_file_logging', lambda *args: None)
    assert fetch.main(['2026', '--force-download']) == 0
    assert events == ['login', 'download', 'logout']


@pytest.mark.integration
def test_redirect_to_login_is_rejected(monkeypatch, tmp_path):
    from types import SimpleNamespace
    client = fetch.RiFetchClient(base_url=fetch.BASE_URL, storage_root=tmp_path, persist_raw=False)
    calls = []
    response = SimpleNamespace(status_code=302, headers={'Location': 'ylogon.asp'},
                               close=lambda: calls.append('closed'))

    def request(*args, **kwargs):
        assert kwargs['allow_redirects'] is False
        calls.append('request')
        return response

    monkeypatch.setattr(client.session, 'request', request)
    with pytest.raises(fetch.RiAccessError):
        client._request('GET', fetch.BASE_URL + '/getfile.asp?id=1', stream=True)
    assert calls == ['request', 'closed']


def test_unavailable_detail_does_not_stop_following_sessions(caplog):
    from types import SimpleNamespace
    references = [SimpleNamespace(session_id='9489'), SimpleNamespace(session_id='7167'),
                  SimpleNamespace(session_id='9509')]
    downloaded = []

    def detail(reference):
        if reference.session_id == '7167':
            raise fetch.RiPageUnavailable('Andere Ansicht')
        return reference

    def download(reference, *, force_download):
        assert force_download
        downloaded.append(reference.session_id)

    client = SimpleNamespace(fetch_month=lambda **kw: references, fetch_session=detail,
                             download_documents=download)
    result = fetch.fetch_months(client, 2026, [11], force_download=True)
    assert downloaded == ['9489', '9509']
    assert result.skipped_sessions == ['7167']
    assert result.failed_documents == []
    assert '7167' in caplog.text and 'übersprungen' in caplog.text


def test_access_failure_still_aborts():
    from types import SimpleNamespace

    def denied(reference):
        raise fetch.RiAccessError('Anmeldung abgelaufen')

    client = SimpleNamespace(fetch_month=lambda **kw: [SimpleNamespace(session_id='1')],
                             fetch_session=denied)
    with pytest.raises(fetch.RiAccessError, match='abgelaufen'):
        fetch.fetch_months(client, 2026, [11])


@pytest.mark.integration
def test_main_reports_incomplete_run_after_logout(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("src.config.ri.RI_ROOT", tmp_path)
    from contextlib import contextmanager
    from types import SimpleNamespace
    events = []

    @contextmanager
    def fake_login(**kwargs):
        try:
            yield SimpleNamespace(persist_raw=False, ri_cleanup_warning=False,
                                  proton_cleanup_warning=False)
        finally:
            events.append('logout')

    monkeypatch.setattr(fetch, 'login', fake_login)
    monkeypatch.setattr(fetch, 'fetch_months', lambda *args, **kwargs: fetch.FetchResult(skipped_sessions=['7167']))
    monkeypatch.setattr(fetch, 'configure_file_logging', lambda *args: None)
    assert fetch.main(['2026', '--months', '11']) == 2
    assert events == ['logout']
    assert '1 Sitzungen übersprungen' in capsys.readouterr().out


@pytest.mark.parametrize('url,expected', [
    ('https://session.melle.info/ri/getfile.asp?id=145460&type=do', '145460'),
    ('https://session.melle.info/bi/getfile.asp?type=do&id=145460', '145460'),
    ('https://session.melle.info/ri/getfile.asp?id=1&id=2', None),
    ('https://example.org/ri/getfile.asp?id=145460', None),
    ('https://session.melle.info/ri/getfile.asp?id=abc', None),
])
def test_document_id(url, expected):
    assert fetch.document_id(url) == expected


@pytest.fixture
def visibility_client(tmp_path, monkeypatch):
    from datetime import date, datetime, timezone
    from src.fetching.models import AgendaItem, DocumentReference, SessionDetail, SessionReference
    ids = ['145203', '145578', '145460', '145378', '145459', '145377']
    reference = SessionReference('Ausschuss', 'Sitzung', '8174', date(2026, 11, 19),
                                 None, fetch.BASE_URL + '/si0057.asp?__ksinr=8174')
    docs = [DocumentReference('Anlage ' + value, fetch.BASE_URL + '/getfile.asp?id=' + value + '&type=do',
                               on_agenda_item='Ö 13') for value in ids]
    detail = SessionDetail(reference, [AgendaItem('Ö 13', 'Sportstättenförderung', documents=docs)],
                           datetime.now(timezone.utc), '<html></html>')
    client = fetch.RiFetchClient(base_url=fetch.BASE_URL, storage_root=tmp_path, persist_raw=False)
    monkeypatch.setattr(client, '_fetch_document_payload',
                        lambda doc: (b'%PDF-1.4 test', {'Content-Type': 'application/pdf'}))
    monkeypatch.setattr(client, '_head_document', lambda doc: {})
    yield client, detail
    client.session.close()


def read_visibility_manifest(client, detail):
    import json
    path = client._build_session_directory(detail.reference) / 'manifest.json'
    return json.loads(path.read_text())['documents']


@pytest.mark.integration
def test_8174_o13_manifest_marks_four_ri_only_documents(visibility_client, monkeypatch):
    client, detail = visibility_client
    events = []

    def compare(reference):
        events.append('compare')
        return {'145203', '145578'}

    def payload(doc):
        assert events[0] == 'compare'
        events.append('download')
        return b'%PDF-1.4 test', {'Content-Type': 'application/pdf'}

    monkeypatch.setattr(fetch, 'fetch_public_document_ids', compare)
    monkeypatch.setattr(client, '_fetch_document_payload', payload)
    client.download_documents(detail)
    entries = read_visibility_manifest(client, detail)
    assert len(entries) == 6
    for entry in entries:
        expected = 'öffentlich' if entry['document_id'] in {'145203', '145578'} else 'nicht öffentlich'
        assert entry['visibility'] == expected
        assert entry['bi_comparison_status'] == 'erfolgreich'
        assert entry['visibility_checked_at']
        assert entry['url'].startswith(fetch.BASE_URL)


@pytest.mark.integration
def test_failed_bi_comparison_replaces_previous_public_labels(visibility_client, monkeypatch):
    client, detail = visibility_client
    monkeypatch.setattr(fetch, 'fetch_public_document_ids', lambda ref: {'145203', '145578'})
    client.download_documents(detail)

    def failed(reference):
        raise TimeoutError

    monkeypatch.setattr(fetch, 'fetch_public_document_ids', failed)
    monkeypatch.setattr(client, '_is_unchanged_document', lambda entry, headers: True)

    def unexpected_download(document):
        pytest.fail('Vorhandene unveränderte Datei soll wiederverwendet werden')

    monkeypatch.setattr(client, '_fetch_document_payload', unexpected_download)
    client.download_documents(detail)
    entries = read_visibility_manifest(client, detail)
    assert len(entries) == 6
    assert all(entry['visibility'] == 'nicht öffentlich' for entry in entries)
    assert all(entry['bi_comparison_status'] == 'fehlgeschlagen' for entry in entries)


@pytest.mark.integration
def test_public_comparison_reads_only_html_with_separate_session(visibility_client, monkeypatch):
    client, detail = visibility_client
    public = fetch.SessionNetClient(persist_raw=False)
    assert public.session is not client.session
    assert not public.session.cookies
    calls = []

    class Response:
        status_code = 200
        headers = {'Content-Type': 'text/html'}
        encoding = 'utf-8'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, size):
            yield b'<table class="smctablesitzung"><tr><td>O 13</td><td>TOP</td><td><a href="getfile.asp?id=145203&amp;type=do">Vorlage</a></td></tr></table>'

    def get(url, **kwargs):
        assert url == 'https://session.melle.info/bi/si0057.asp?__ksinr=8174'
        assert kwargs['allow_redirects'] is False
        calls.append(url)
        return Response()

    monkeypatch.setattr(public.session, 'get', get)
    monkeypatch.setattr(fetch, 'SessionNetClient', lambda **kwargs: public)
    assert fetch.fetch_public_document_ids(detail.reference) == {'145203'}
    assert len(calls) == 1


@pytest.mark.integration
@pytest.mark.parametrize('failure_mode', ['size', 'stream'])
@pytest.mark.parametrize('retain_old_entry', [False, True])
def test_download_failures_reach_exit_status_after_later_success(
    visibility_client, monkeypatch, tmp_path, capsys, caplog, failure_mode, retain_old_entry
):
    from contextlib import contextmanager
    from dataclasses import replace
    import logging
    import requests
    from src.fetching import sessionnet_client

    client, detail = visibility_client
    monkeypatch.setattr('src.config.ri.RI_ROOT', tmp_path)
    monkeypatch.setattr(fetch, 'fetch_public_document_ids', lambda ref: set())
    if retain_old_entry:
        client.download_documents(detail)
        previous = next(entry for entry in read_visibility_manifest(client, detail)
                        if entry['document_id'] == '145203')
    client.max_document_bytes = 16
    client.max_retries = 2
    client.ri_cleanup_warning = client.proton_cleanup_warning = False
    monkeypatch.setattr(client, '_fetch_document_payload',
                        sessionnet_client.SessionNetClient._fetch_document_payload.__get__(client))
    monkeypatch.setattr(sessionnet_client.time, 'sleep', lambda seconds: None)
    later = replace(detail, reference=replace(detail.reference, session_id='9999'))
    visited = []
    attempts = []
    failure_enabled = True

    def fetch_detail(reference):
        visited.append(reference.session_id)
        return detail if reference.session_id == detail.reference.session_id else later

    class Response:
        def __init__(self, failed):
            self.failed = failed
            self.headers = {'Content-Type': 'application/pdf',
                            'Content-Length': '99' if failed and failure_mode == 'size' else '9'}

        def iter_content(self, chunk_size):
            if self.failed and failure_mode == 'stream':
                raise requests.RequestException('Synthetic stream failure')
            yield b'%PDF-test'

        def close(self):
            pass

    def request(method, url, **kwargs):
        assert method == 'GET'
        failed = (failure_enabled and visited[-1] == detail.reference.session_id
                  and fetch.document_id(url) == '145203')
        if failed:
            attempts.append(url)
        return Response(failed)

    @contextmanager
    def fake_login(**kwargs):
        try:
            yield client
        finally:
            visited.append('logout')

    monkeypatch.setattr(client, 'fetch_month', lambda **kwargs: [detail.reference, later.reference])
    monkeypatch.setattr(client, 'fetch_session', fetch_detail)
    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(fetch, 'login', fake_login)
    monkeypatch.setattr(fetch, 'configure_file_logging', lambda *args: None)
    caplog.set_level(logging.INFO)

    assert fetch.main(['2026', '--months', '11', '--force-download']) == 2

    assert visited == [detail.reference.session_id, later.reference.session_id, 'logout']
    assert len(attempts) == (1 if failure_mode == 'size' else client.max_retries)
    output = capsys.readouterr().out
    assert f'{detail.reference.session_id}/145203' in output
    assert 'https://' not in output
    assert 'vollständige_sitzungen=1' in caplog.text
    entries = read_visibility_manifest(client, detail)
    failed_entries = [entry for entry in entries if entry['document_id'] == '145203']
    if retain_old_entry:
        assert failed_entries[0]['path'] == previous['path']
        assert failed_entries[0]['verified_at'] == previous['verified_at']
    else:
        assert failed_entries == []
    assert len(read_visibility_manifest(client, later)) == len(detail.agenda_items[0].documents)

    # A subsequent successful run must not retain the previous incomplete status.
    failure_enabled = False
    assert fetch.main(['2026', '--months', '11', '--force-download']) == 0
