from pathlib import Path
import sys

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no branch - test safety
    sys.path.insert(0, str(REPO_ROOT))

from src.fetching.sessionnet_client import SessionNetClient


def test_get_retries_with_backoff(monkeypatch, tmp_path):
    client = SessionNetClient(
        storage_root=tmp_path,
        min_request_interval=0,
        max_retries=2,
        retry_backoff=2.0,
    )

    attempts = {"count": 0}

    class _Response:
        headers = {}
        content = b""
        text = ""

        @staticmethod
        def raise_for_status():
            return None

    def fake_session_get(url, params=None, timeout=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise requests.RequestException("boom")
        return _Response()

    sleep_calls = []

    monkeypatch.setattr(client.session, "get", fake_session_get)
    monkeypatch.setattr(
        "src.fetching.sessionnet_client.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    monkeypatch.setattr("src.fetching.sessionnet_client.time.monotonic", lambda: 0.0)

    response = client._get("https://example.org/doc")

    assert isinstance(response, _Response)
    assert attempts["count"] == 2
    assert sleep_calls == [1.0]


def test_respect_rate_limit_triggers_sleep(monkeypatch, tmp_path):
    client = SessionNetClient(storage_root=tmp_path, min_request_interval=1.0)
    client._last_request_ts = 0.0

    sleep_calls = []

    monkeypatch.setattr(
        "src.fetching.sessionnet_client.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    # first call should skip because last_request_ts <= 0
    client._respect_rate_limit()
    assert sleep_calls == []

    # simulate a previous request timestamp and rerun
    client._last_request_ts = 0.25
    timeline = iter([1.0])

    monkeypatch.setattr("src.fetching.sessionnet_client.time.monotonic", lambda: next(timeline))
    client._respect_rate_limit()
    assert sleep_calls == [0.25]
