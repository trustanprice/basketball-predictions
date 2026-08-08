from unittest.mock import MagicMock, patch

import pytest
import requests

from live_client.client import DEFAULT_HEADERS, NBAClientError, NBAStatsClient


def _mock_response(json_data=None, status_ok=True):
    resp = MagicMock()
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.HTTPError("500")
    resp.json.return_value = json_data or {}
    return resp


def test_get_json_returns_parsed_body_on_first_success():
    client = NBAStatsClient(max_retries=3)
    with patch.object(client.session, "get", return_value=_mock_response({"ok": True})) as mock_get:
        result = client.get_json("https://example.com/x", params={"a": 1})
    assert result == {"ok": True}
    mock_get.assert_called_once()


def test_get_json_retries_then_succeeds():
    client = NBAStatsClient(max_retries=3, backoff_seconds=0)
    failing = requests.exceptions.ConnectionError("boom")
    good = _mock_response({"ok": True})
    with patch.object(client.session, "get", side_effect=[failing, failing, good]) as mock_get, \
         patch("live_client.client.time.sleep") as mock_sleep:
        result = client.get_json("https://example.com/x")
    assert result == {"ok": True}
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2  # backoff before the 2nd and 3rd attempts


def test_get_json_raises_after_exhausting_retries():
    client = NBAStatsClient(max_retries=2, backoff_seconds=0)
    with patch.object(client.session, "get", side_effect=requests.exceptions.ConnectionError("boom")), \
         patch("live_client.client.time.sleep"):
        with pytest.raises(NBAClientError):
            client.get_json("https://example.com/x")


def test_get_json_retries_on_bad_json_body():
    """NBA.com occasionally returns a 200 with an HTML error page instead of JSON."""
    client = NBAStatsClient(max_retries=2, backoff_seconds=0)
    bad = MagicMock()
    bad.raise_for_status.return_value = None
    bad.json.side_effect = ValueError("not json")
    good = _mock_response({"ok": True})
    with patch.object(client.session, "get", side_effect=[bad, good]), \
         patch("live_client.client.time.sleep"):
        result = client.get_json("https://example.com/x")
    assert result == {"ok": True}


def test_default_headers_present_and_extra_headers_merge():
    client = NBAStatsClient(extra_headers={"X-Custom": "1"})
    for key, value in DEFAULT_HEADERS.items():
        assert client.session.headers[key] == value
    assert client.session.headers["X-Custom"] == "1"


def test_context_manager_closes_session():
    with NBAStatsClient() as client:
        session = client.session
        assert session is not None
    # closed session's adapters are gone; calling close() again should not raise
    session.close()
