"""Focused offline tests for the BI copy and separate RI login; no real secrets."""
from contextlib import contextmanager
from datetime import date, datetime, UTC
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from src.fetching import ri_session as auth
from scripts import build_ri_online_index_db as builder
from scripts import build_bi_online_index_db as bi
from src.fetching.models import SessionReference, SessionDetail, AgendaItem, DocumentReference


class FakeClient:
    unavailable_details = 0
    def __init__(self):
        self.calls = []
        self.references = [SessionReference('Synthetic committee', 'Synthetic meeting', '9509', date(2026,11,18), '18:00', auth.BASE_URL + '/si0057.asp?__ksinr=9509')]
    def fetch_month(self, **kwargs): return self.references
    def fetch_session(self, reference):
        self.calls.append(reference.session_id)
        doc = DocumentReference('Synthetic template', auth.BASE_URL + '/getfile.asp?type=do&id=synthetic', 'VO')
        return SessionDetail(reference, [AgendaItem('Ö 1','Synthetic topic',documents=[doc])], datetime.now(UTC), '<synthetic>')


@pytest.fixture
def db_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, 'RI_ROOT', tmp_path / 'ri')
    folder = tmp_path / 'ri/db'
    return folder/'online_session_index.sqlite', folder/'local_index.sqlite'


def test_schema_matches_bi():
    with sqlite3.connect(':memory:') as left, sqlite3.connect(':memory:') as right:
        bi._create_tables(left); builder._create_tables(right)
        for table in ('sessions','agenda_items','documents'):
            assert left.execute(f'PRAGMA table_info({table})').fetchall() == right.execute(f'PRAGMA table_info({table})').fetchall()


@pytest.mark.integration
def test_repeated_build_reuses_db_refreshes_without_duplicates(db_paths):
    output, local = db_paths
    client = FakeClient()
    builder.build_session_db(client,2026,[11],output,False,False,local)
    builder.build_session_db(client,2026,[11],output,False,False,local)
    assert client.calls == ['9509']
    builder.build_session_db(client,2026,[11],output,True,False,local)
    assert client.calls == ['9509','9509']
    with sqlite3.connect(output) as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM agenda_items').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM documents').fetchone()[0] == 1
    assert len(list(output.parent.glob('*.sqlite'))) == 1


@pytest.mark.integration
def test_only_refresh_does_not_add_new_sessions(db_paths):
    output, local = db_paths
    client = FakeClient()
    builder.build_session_db(client,2026,[11],output,False,False,local)
    first=client.references[0]
    client.references.append(SessionReference(first.committee,first.meeting_name,'9999',first.date,first.start_time,auth.BASE_URL+'/si0057.asp?__ksinr=9999'))
    builder.build_session_db(client,2026,[11],output,True,True,local)
    assert client.calls == ['9509','9509']
    with sqlite3.connect(output) as db:
        assert db.execute('SELECT session_id FROM sessions').fetchall() == [('9509',)]


@pytest.mark.integration
def test_unavailable_detail_does_not_destroy_existing_session(db_paths):
    output, local = db_paths
    client = FakeClient()
    builder.build_session_db(client,2026,[11],output,False,False,local)
    def unavailable(reference): raise auth.RiPageUnavailable('Synthetic unavailable view')
    client.fetch_session = unavailable
    builder.build_session_db(client,2026,[11],output,True,False,local)
    assert client.unavailable_details == 1
    with sqlite3.connect(output) as db:
        assert db.execute('SELECT count(*) FROM documents').fetchone()[0] == 1
        assert db.execute('SELECT detail_url FROM sessions').fetchone()[0]


@pytest.mark.integration
def test_new_unavailable_detail_remains_retryable_calendar_entry(db_paths):
    output, local = db_paths
    client = FakeClient()
    def unavailable(reference): raise auth.RiPageUnavailable('Synthetic unavailable view')
    client.fetch_session = unavailable
    builder.build_session_db(client,2026,[11],output,False,False,local)
    with sqlite3.connect(output) as db:
        assert db.execute('SELECT detail_url FROM sessions').fetchone()[0] == ''
        assert db.execute('SELECT count(*) FROM documents').fetchone()[0] == 0


@pytest.mark.integration
def test_expired_login_aborts_without_storing_session(db_paths):
    output, local = db_paths
    client = FakeClient()
    def expired(reference): raise auth.RiAccessError('RI-Anmeldung abgelaufen')
    client.fetch_session = expired
    with pytest.raises(auth.RiAccessError):
        builder.build_session_db(client,2026,[11],output,False,False,local)
    with sqlite3.connect(output) as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0


@pytest.mark.integration
def test_output_cannot_write_public_data(db_paths, tmp_path):
    with pytest.raises(auth.RiAccessError):
        builder.build_session_db(FakeClient(),2026,[11],tmp_path/'public.sqlite',False,False,db_paths[1])
    assert not (tmp_path/'public.sqlite').exists()


@pytest.mark.parametrize('target', ['https://other.invalid/ri/si0057.asp?__ksinr=9509', auth.BASE_URL+'/getfile.asp?type=do&id=synthetic', 'https://session.melle.info/bi/si0057.asp?__ksinr=9509'])
def test_login_client_does_not_fetch_files_or_foreign_pages(target):
    client=auth.RiOnlineClient(base_url=auth.BASE_URL,persist_raw=False)
    client.session.close()
    client.session=SimpleNamespace(get=lambda *a,**kw:pytest.fail('Forbidden request'))
    with pytest.raises(auth.RiAccessError): client._get(target)


def test_login_form_is_not_returned_as_metadata():
    client=auth.RiOnlineClient(base_url=auth.BASE_URL,persist_raw=False)
    client.session.close()
    class Response:
        status_code=200
        headers={'Content-Type':'text/html'}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def iter_content(self,size): yield b'<form id="smclogon"><input type="password"></form>'
    client.session=SimpleNamespace(get=lambda *a,**kw:Response())
    with pytest.raises(auth.RiAccessError,match='abgelaufen'):
        client._get('si0057.asp?__ksinr=9509')


def test_login_logs_out_after_builder_failure(monkeypatch,capsys):
    calls=[]
    class Proton:
        cleanup_warning=False
        def __init__(self,token): pass
        def __enter__(self): return self
        def __exit__(self,*args): calls.append('proton_logout')
        def credentials(self): return SimpleNamespace(username='private-user',password='private-password')
    class Probe:
        def __init__(self,session): pass
        def get(self,url):
            if 'ri_logout' in calls: return auth.BASE_URL+'/ylogon.asp',b'<form id="smclogon"><input type="password"></form>'
            return auth.PROTECTED,b'<h1>Authenticated</h1>'
        def _request(self,method,url,data=None):
            calls.append('post' if method=='POST' else 'ri_logout')
            return 200,None,b''
        def logout_link(self,body,url): return auth.BASE_URL+'/ylogoff.asp'
    monkeypatch.setattr(auth,'ProtonRiSession',Proton)
    monkeypatch.setattr(auth,'read_token',lambda:'pst_synthetic::private-token')
    monkeypatch.setattr(auth,'RiLoginProbe',Probe)
    monkeypatch.setattr(auth,'login_payload',lambda *a:(auth.BASE_URL+'/ylogon2.asp',{'password':'private-password'}))
    with pytest.raises(RuntimeError):
        with auth.login(): raise RuntimeError('Synthetic builder error')
    assert calls == ['post','ri_logout','proton_logout']
    assert 'private-' not in repr(capsys.readouterr())
