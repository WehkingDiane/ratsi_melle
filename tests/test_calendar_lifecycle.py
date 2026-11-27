"""Lifecycle parsing and persistence without network access or production data."""
from datetime import date
from pathlib import Path
import json
import sqlite3

import pytest

from src.fetching import SessionNetClient
from src.fetching.calendar_status import calendar_metadata, merge_calendar_rows
from src.fetching.ri_session import RiOnlineClient, RiCalendarChanged, RiPageUnavailable, checked_metadata_url
from src.indexing.calendar_metadata import ensure_calendar_columns, sync_saved_calendars

FIXTURE = Path(__file__).parent / 'fixtures/si0040_lifecycle_synthetic.html'


def test_calendar_parser_preserves_identity_and_separates_notices():
    client=SessionNetClient(base_url='https://session.melle.info/ri', persist_raw=False)
    try:
        refs={r.session_id:r for r in client._parse_overview(FIXTURE.read_text(),2026,12)}
    finally:
        client.session.close()
    assert refs['9514'].start_time == '19:00 Uhr'
    assert refs['9514'].location == 'Testsaal'
    assert refs['8181'].date == date(2026,12,9)
    assert refs['8181'].rescheduled_date == date(2026,12,7)
    assert refs['8181'].replacement_session_id == '9514'
    assert refs['8181'].start_time is None
    assert refs['9516'].rescheduled_date == date(2027,1,12)
    assert refs['9516'].replacement_session_id is None
    assert refs['7168'].calendar_status == refs['7169'].calendar_status == 'cancelled'
    assert refs['9999'].calendar_status == 'unknown'


def test_legacy_notices_and_fresh_observations_do_not_leave_stale_status():
    assert calendar_metadata({'start_time':'abgesagt'})['calendar_status']=='cancelled'
    old={'calendar_status':'cancelled','calendar_note':'abgesagt','calendar_observed_at':'2026-11-20T10:00:00+00:00'}
    fresh={'calendar_status':'scheduled','calendar_note':None,'calendar_observed_at':'2026-11-21T10:00:00+00:00'}
    assert merge_calendar_rows(old,fresh)['calendar_status']=='scheduled'
    assert merge_calendar_rows(old,fresh)['calendar_note'] is None
    assert merge_calendar_rows(fresh,old)['calendar_status']=='scheduled'


@pytest.mark.integration
def test_schema_upgrade_is_additive_and_saved_calendar_preserves_documents(tmp_path):
    from scripts import build_ri_local_index as builder
    raw=tmp_path/'raw';month=raw/'2026/12';month.mkdir(parents=True)
    (month/'2026-12_overview.html').write_text(FIXTURE.read_text())
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE sessions (session_id TEXT PRIMARY KEY,date TEXT,year INTEGER,month INTEGER,committee TEXT,meeting_name TEXT,start_time TEXT,location TEXT,detail_url TEXT,session_path TEXT)')
        db.execute("INSERT INTO sessions (session_id,date) VALUES ('8181','2026-12-09')")
        ensure_calendar_columns(db);ensure_calendar_columns(db)
        db.execute('CREATE TABLE documents (id INTEGER PRIMARY KEY,session_id TEXT,title TEXT)')
        db.execute("INSERT INTO documents VALUES (1,'8181','Existing')")
        client=SessionNetClient(persist_raw=False)
        try:sync_saved_calendars(db,raw,client)
        finally:client.session.close()
        assert db.execute("SELECT calendar_status,rescheduled_date,replacement_session_id FROM sessions WHERE session_id='8181'").fetchone()==('postponed','2026-12-07','9514')
        assert db.execute('SELECT * FROM documents').fetchall()==[(1,'8181','Existing')]
        assert db.execute("SELECT calendar_status FROM sessions WHERE session_id='7168'").fetchone()==('cancelled',)
        assert db.execute("SELECT 1 FROM sessions WHERE session_id='9514'").fetchone() is None


@pytest.mark.integration
@pytest.mark.parametrize('content,changed', [(b'<html><p>Die Sitzung ist abgesagt.</p></html>',True),
                                           (b'<html><p>Unbekannte Ansicht</p></html>',False)])
def test_ri_status_view_requires_explicit_status_and_same_id(monkeypatch,content,changed):
    import requests
    from src.fetching.models import SessionReference
    response=requests.Response();response.status_code=200;response.headers['Content-Type']='text/html'
    response._content=content;response._content_consumed=True;response.url='https://session.melle.info/ri/si0050.asp?__ksinr=8181'
    client=RiOnlineClient(persist_raw=False,min_request_interval=0)
    monkeypatch.setattr(client.session,'get',lambda *a,**kw:response)
    reference=SessionReference('Test','Test','8181',date(2026,12,9),None,response.url)
    try:
        with pytest.raises(RiCalendarChanged if changed else RiPageUnavailable):client.fetch_session(reference)
        if changed:assert reference.calendar_status=='cancelled'
        with pytest.raises(RiPageUnavailable):checked_metadata_url('https://session.melle.info/ri/si0050.asp?__ksinr=8181&extra=1')
    finally:client.session.close()


@pytest.mark.integration
def test_changed_terms_do_not_count_against_upcoming_limit(monkeypatch):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'web'))
    from core.services import session_inventory as inventory
    rows=[{'session_id':'old','date':'2026-12-03','start_time':'verschoben auf den 12.01.2027'},
          {'session_id':'cancelled','date':'2026-12-01','calendar_status':'cancelled'},
          {'session_id':'normal','date':'2026-12-07','start_time':'19:00 Uhr'}]
    monkeypatch.setattr(inventory,'_read_index',lambda *a:rows)
    result=inventory.dashboard_session_groups([],date(2026,11,27),limit=1)
    assert [s['session_id'] for s in result['upcoming_sessions']]==['normal']
    assert {s['session_id'] for s in result['changed_sessions']}=={'old','cancelled'}
    assert next(s for s in result['changed_sessions'] if s['session_id']=='old')['start_time'] is None


@pytest.mark.integration
def test_download_status_sidecar_reaches_local_index_without_documents(monkeypatch,tmp_path):
    from scripts import fetch_ri_sessions as fetch
    from src.fetching.models import SessionReference
    raw=tmp_path/'raw';month=raw/'2026/12';month.mkdir(parents=True)
    (month/'2026-12_overview.html').write_text(FIXTURE.read_text())
    reference=SessionReference('Test','Test','8181',date(2026,12,9),None,'https://session.melle.info/ri/si0057.asp?__ksinr=8181')
    client=fetch.RiFetchClient(storage_root=raw,persist_raw=True)
    monkeypatch.setattr(client,'fetch_month',lambda **kwargs:[reference])
    def changed(ref):
        ref.calendar_status='postponed';ref.rescheduled_date=date(2026,12,8);ref.calendar_note='verschoben auf den 08.12.2026'
        raise RiCalendarChanged({'calendar_status':'postponed'})
    monkeypatch.setattr(client,'fetch_session',changed)
    monkeypatch.setattr(client,'download_documents',lambda *a,**kw:pytest.fail('Changed calendar entry downloaded documents'))
    try:
        result=fetch.fetch_months(client,2026,[12])
        assert not result.skipped_sessions
        with sqlite3.connect(':memory:') as db:
            from scripts import build_ri_local_index as builder
            builder._create_tables(db)
            sync_saved_calendars(db,raw,client)
            assert db.execute("SELECT calendar_status,rescheduled_date FROM sessions WHERE session_id='8181'").fetchone()==('postponed','2026-12-08')
    finally:client.session.close()


@pytest.mark.integration
def test_online_calendar_change_updates_without_refetch_or_losing_documents(tmp_path):
    from scripts import build_ri_online_index_db as builder
    from src.fetching.models import SessionReference,SessionDetail,AgendaItem,DocumentReference
    from datetime import datetime,timezone
    class Client:
        unavailable_details=0
        def __init__(self):
            self.ref=SessionReference('Test','Test','8181',date(2026,12,9),'19:00', 'https://session.melle.info/ri/si0057.asp?__ksinr=8181')
            self.calls=0
        def fetch_month(self,**kw):return [self.ref]
        def fetch_session(self,ref):
            self.calls+=1
            return SessionDetail(ref,[AgendaItem('Ö 1','Test',documents=[DocumentReference('Test','https://session.melle.info/ri/getfile.asp?id=1&type=do')])],datetime.now(timezone.utc),'test')
    client=Client()
    with sqlite3.connect(':memory:') as db:
        builder._create_tables(db)
        builder._populate(db,client,2026,[12],False,False)
        client.ref.calendar_status='postponed';client.ref.calendar_note='verschoben auf den 07.12.2026';client.ref.rescheduled_date=date(2026,12,7);client.ref.start_time=None
        builder._populate(db,client,2026,[12],False,False)
        assert client.calls==1
        assert db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==1
        assert db.execute('SELECT calendar_status,rescheduled_date FROM sessions').fetchone()==('postponed','2026-12-07')


@pytest.mark.parametrize('text',['öffentlicher Teil entfällt','nicht abgesagt','nicht verschoben'])
def test_partial_or_negated_notice_is_not_a_confirmed_cancellation(text):
    from src.fetching.calendar_status import parse_calendar_notices
    assert parse_calendar_notices([text])['calendar_status']=='unknown'


def test_replacement_id_is_not_taken_from_a_foreign_link():
    html=FIXTURE.read_text().replace('href="si0057.asp?__ksinr=9514">Neuer Termin', 'href="https://outside.invalid/ri/si0057.asp?__ksinr=9514">Neuer Termin')
    client=SessionNetClient(base_url='https://session.melle.info/ri',persist_raw=False)
    try:
        ref=next(r for r in client._parse_overview(html,2026,12) if r.session_id=='8181')
        assert ref.replacement_session_id is None
        assert ref.rescheduled_date==date(2026,12,7)
    finally:client.session.close()


@pytest.mark.integration
def test_status_redirect_cannot_change_requested_session(monkeypatch):
    import requests
    response=requests.Response();response.status_code=302;response._content=b'';response._content_consumed=True
    response.headers['Location']='https://session.melle.info/ri/si0050.asp?__ksinr=9999'
    client=RiOnlineClient(base_url='https://session.melle.info/ri',persist_raw=False,min_request_interval=0)
    calls=[]
    def get(*args,**kwargs):calls.append(args[0]);return response
    monkeypatch.setattr(client.session,'get',get)
    try:
        with pytest.raises(RiPageUnavailable):client._get('https://session.melle.info/ri/si0057.asp?__ksinr=8181')
        assert len(calls)==1
    finally:client.session.close()


def test_rescheduled_date_uses_explicit_target_not_original_date():
    from src.fetching.calendar_status import parse_calendar_notices
    value=parse_calendar_notices(['Sitzung vom 03.12.2026 verschoben auf den 12.01.2027'])
    assert value['rescheduled_date']==date(2027,1,12)
