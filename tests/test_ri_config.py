"""Focused RI boundary and logging checks; no live access."""
import json
import logging

import pytest

from src.config import ri
from src.config.ri_proton import RiAccessError
from src import paths


def test_ri_root_is_outside_public_sources():
    assert paths.RI_DATA_DIR == paths.DATA_ROOT / 'ri'
    assert not paths.RI_RAW_DATA_DIR.is_relative_to(paths.RAW_DATA_DIR)
    assert not paths.RI_DB_DIR.is_relative_to(paths.DB_DIR)
    assert paths.RI_LOCAL_INDEX_DB != paths.LOCAL_INDEX_DB
    assert paths.RI_ONLINE_INDEX_DB != paths.ONLINE_INDEX_DB


@pytest.mark.integration
def test_local_config_overrides_default_and_invalid_config_aborts(tmp_path, monkeypatch):
    monkeypatch.setattr(ri, 'RI_ROOT', tmp_path)
    assert ri.select_months(2026, [10, 11, 12]) == (11, 12)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'earliest_month': '2026-12'}), encoding='utf-8')
    assert ri.select_months(2026, [11, 12]) == (12,)
    config.write_text('invalid', encoding='utf-8')
    with pytest.raises(RiAccessError):
        ri.select_months(2026, [11, 12])


def test_ri_formatter_hides_urls_in_message_and_exception():
    formatter = ri.RiFormatter('%(levelname)s %(message)s')
    url = 'https://session.melle.info/ri/getfile.asp?id=123&type=do'
    try:
        raise RuntimeError(url)
    except RuntimeError:
        import sys
        record = logging.LogRecord('test', logging.ERROR, '', 0, 'Failed %s', (url,), sys.exc_info())
    result = formatter.format(record)
    assert url not in result
    assert 'getfile.asp' not in result
    assert '[RI-URL]' in result
