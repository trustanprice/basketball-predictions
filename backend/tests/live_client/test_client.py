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


def _fake_nba_api_endpoint(dict_result=None, side_effects=None):
    """A stand-in for an nba_api Endpoint instance: get_request() does the (fake)
    network call, get_dict() returns whatever it fetched — mirrors the real
    nba_api.stats.endpoints._base.Endpoint interface get_via_nba_api relies on."""
    endpoint = MagicMock()
    if side_effects is not None:
        endpoint.get_request.side_effect = side_effects
    endpoint.get_dict.return_value = dict_result
    return endpoint


def test_get_via_nba_api_returns_dict_on_first_success():
    client = NBAStatsClient(max_retries=3)
    endpoint = _fake_nba_api_endpoint(dict_result={"ok": True})
    result = client.get_via_nba_api(endpoint)
    assert result == {"ok": True}
    endpoint.get_request.assert_called_once()


def test_get_via_nba_api_retries_then_succeeds():
    client = NBAStatsClient(max_retries=3, backoff_seconds=0)
    failing = requests.exceptions.ConnectionError("boom")
    endpoint = _fake_nba_api_endpoint(
        dict_result={"ok": True}, side_effects=[failing, failing, None]
    )
    with patch("live_client.client.time.sleep") as mock_sleep:
        result = client.get_via_nba_api(endpoint)
    assert result == {"ok": True}
    assert endpoint.get_request.call_count == 3
    assert mock_sleep.call_count == 2


def test_get_via_nba_api_raises_after_exhausting_retries():
    client = NBAStatsClient(max_retries=2, backoff_seconds=0)
    endpoint = _fake_nba_api_endpoint(side_effects=requests.exceptions.ConnectionError("boom"))
    with patch("live_client.client.time.sleep"):
        with pytest.raises(NBAClientError):
            client.get_via_nba_api(endpoint)


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
