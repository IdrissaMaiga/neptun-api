import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from neptun_api.client import NeptunAPI
from neptun_api.exceptions import NeptunAuthError, NeptunRequestError


@pytest.fixture
def api():
    return NeptunAPI(username="test", password="pass123")


@pytest.fixture
def authed_api(api):
    api.token = "fake-token"
    return api


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


class TestAuthenticate:
    def test_success(self, api):
        resp = _mock_response(200, {"data": {"accessToken": "tok123", "neptunCode": "ABC"}})
        api.session.post = MagicMock(return_value=resp)
        data = api.authenticate()
        assert api.token == "tok123"
        assert api.neptun_code == "ABC"
        assert data["accessToken"] == "tok123"

    def test_auth_error_400(self, api):
        resp = _mock_response(400, {
            "modelStateErrors": [{"errors": ["Bad credentials"]}]
        })
        api.session.post = MagicMock(return_value=resp)
        with pytest.raises(NeptunAuthError, match="Bad credentials"):
            api.authenticate()

    def test_http_error(self, api):
        resp = _mock_response(500, text="Server error")
        api.session.post = MagicMock(return_value=resp)
        with pytest.raises(NeptunRequestError, match="HTTP 500"):
            api.authenticate()

    def test_request_exception(self, api):
        import requests
        api.session.post = MagicMock(side_effect=requests.ConnectionError("timeout"))
        with pytest.raises(NeptunRequestError, match="Request failed"):
            api.authenticate()


class TestEnsureAuth:
    def test_auto_auth(self, api):
        resp = _mock_response(200, {"data": {"accessToken": "tok", "neptunCode": "X"}})
        api.session.post = MagicMock(return_value=resp)
        api.session.get = MagicMock(return_value=_mock_response(200, {"data": []}))
        api.get_trainings()
        assert api.token == "tok"


class TestGet:
    def test_success(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {"data": "ok"}))
        result = authed_api._get("TestEndpoint")
        assert result == {"data": "ok"}

    def test_retry_on_401(self, authed_api):
        resp_401 = _mock_response(401)
        resp_ok = _mock_response(200, {"data": "retried"})
        authed_api.session.get = MagicMock(side_effect=[resp_401, resp_ok])
        auth_resp = _mock_response(200, {"data": {"accessToken": "new", "neptunCode": "X"}})
        authed_api.session.post = MagicMock(return_value=auth_resp)
        result = authed_api._get("TestEndpoint")
        assert result == {"data": "retried"}

    def test_http_error(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(500, text="err"))
        with pytest.raises(NeptunRequestError):
            authed_api._get("TestEndpoint")


class TestPost:
    def test_success(self, authed_api):
        authed_api.session.post = MagicMock(return_value=_mock_response(200, {"accessToken": "new"}))
        result = authed_api._post("Account/GetNewTokens")
        assert result == {"accessToken": "new"}

    def test_204_returns_empty(self, authed_api):
        authed_api.session.post = MagicMock(return_value=_mock_response(204))
        result = authed_api._post("SomeEndpoint")
        assert result == {}


class TestRefreshToken:
    def test_refresh(self, authed_api):
        authed_api.session.post = MagicMock(
            return_value=_mock_response(200, {"accessToken": "refreshed"})
        )
        authed_api.refresh_token()
        assert authed_api.token == "refreshed"


class TestEndpoints:
    def test_get_trainings(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {"data": [{"code": "A"}]}))
        result = authed_api.get_trainings()
        assert result == [{"code": "A"}]

    def test_get_received_messages(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": {"receivedMessages": [{"messageId": "m1"}]}
        }))
        result = authed_api.get_received_messages(0, 10)
        assert result["receivedMessages"][0]["messageId"] == "m1"

    def test_get_unread_message_count(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": {"count": 5}
        }))
        result = authed_api.get_unread_message_count()
        assert result == 5

    def test_get_taken_subjects(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": [{"subjectName": "DB"}]
        }))
        result = authed_api.get_taken_subjects("term-1")
        assert result == [{"subjectName": "DB"}]

    def test_get_calendar_events(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {"data": []}))
        start = datetime(2025, 1, 1)
        end = datetime(2025, 6, 1)
        result = authed_api.get_calendar_events(start, end)
        assert result == []
        call_args = authed_api.session.get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params["startDate"] == "2025-01-01T00:00:00.000"

    def test_get_term_averages(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": {"defaultTerm": 70632, "terms": []}
        }))
        result = authed_api.get_term_averages()
        assert result["defaultTerm"] == 70632

    def test_get_financial_impositions(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": [{"balanceOfImpositions": 80000.0, "currency": "HUF"}]
        }))
        result = authed_api.get_financial_impositions()
        assert result[0]["currency"] == "HUF"

    def test_raw_get(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {"data": "raw"}))
        result = authed_api.raw_get("Custom/Endpoint", params={"k": "v"})
        assert result == {"data": "raw"}

    def test_raw_post(self, authed_api):
        authed_api.session.post = MagicMock(return_value=_mock_response(200, {"ok": True}))
        result = authed_api.raw_post("Custom/Endpoint", data={"x": 1})
        assert result == {"ok": True}


class TestBaseUrl:
    def test_trailing_slash_added(self):
        api = NeptunAPI("u", "p", base_url="https://example.com/api")
        assert api.base_url == "https://example.com/api/"

    def test_trailing_slash_not_doubled(self):
        api = NeptunAPI("u", "p", base_url="https://example.com/api/")
        assert api.base_url == "https://example.com/api/"
