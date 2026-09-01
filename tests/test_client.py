import pytest
from unittest.mock import MagicMock
from datetime import datetime
from neptun_api.client import NeptunAPI, generate_totp
from neptun_api.exceptions import (
    NeptunAuthError, NeptunRequestError, NeptunTwoFactorRequired, NeptunCaptchaRequired,
)


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

    def test_get_subject_grade(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": {"subjectResult": {"resultValue": 4, "resultName": "Jó", "passed": True}}
        }))
        result = authed_api.get_subject_grade("subj-1")
        assert result["resultValue"] == 4
        assert result["passed"] is True

    def test_get_subject_grade_empty_when_no_result(self, authed_api):
        authed_api.session.get = MagicMock(return_value=_mock_response(200, {
            "data": {"subjectName": "Thesis", "subjectResult": None}
        }))
        assert authed_api.get_subject_grade("subj-2") == {}

    def test_get_all_grades(self, authed_api):
        authed_api.session.get = MagicMock(side_effect=[
            _mock_response(200, {"data": [{"value": "t1", "text": "2023/24/1"}]}),       # taken_subjects_terms
            _mock_response(200, {"data": [{"subjectId": "s1", "subjectCode": "NMXMA1EBNF",
                                            "subjectName": "Basic Mathematics", "subjectCredit": 6,
                                            "requirementType": "Évközi jegy"}]}),         # taken_subjects(t1)
            _mock_response(200, {"data": {"subjectResult": {"resultValue": 4, "resultName": "Jó",
                                                            "passed": True}}}),           # subject_details(s1)
        ])
        grades = authed_api.get_all_grades()
        assert len(grades) == 1
        assert grades[0]["subjectCode"] == "NMXMA1EBNF"
        assert grades[0]["term"] == "2023/24/1"
        assert grades[0]["grade"] == 4
        assert grades[0]["gradeName"] == "Jó"

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


class TestTwoFactor:
    """Instances such as University of Debrecen answer the first login with
    HTTP 202 + isTwoFactorRequired; the client must re-post with the code in
    a `token` field, exactly like the official web client."""

    CHALLENGE = {"data": {"neptunCode": None, "accessToken": None,
                          "numberOfDaysUntilADPasswordExpires": 0,
                          "isCaptchaRequired": False, "isTwoFactorRequired": True,
                          "sessionTimeoutInMinutes": 0}, "notification": []}
    SUCCESS = {"data": {"accessToken": "tok2fa", "neptunCode": "DEB123",
                        "isCaptchaRequired": False, "isTwoFactorRequired": True,
                        "sessionTimeoutInMinutes": 30}}

    def test_required_without_code_raises(self, api):
        api.session.post = MagicMock(return_value=_mock_response(202, self.CHALLENGE))
        with pytest.raises(NeptunTwoFactorRequired, match="two-factor") as exc:
            api.authenticate()
        assert exc.value.error_data["isTwoFactorRequired"] is True
        assert api.token is None
        assert api.session.post.call_count == 1

    def test_explicit_code_is_resent_as_token(self, api):
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE), _mock_response(200, self.SUCCESS)])
        data = api.authenticate(totp_code="123456")
        assert api.token == "tok2fa"
        assert api.neptun_code == "DEB123"
        assert data["sessionTimeoutInMinutes"] == 30
        assert api.session.headers["Authorization"] == "Bearer tok2fa"
        first, second = [c.kwargs["json"] for c in api.session.post.call_args_list]
        assert "token" not in first
        assert second["token"] == "123456"
        assert second["userName"] == "test" and second["password"] == "pass123"

    def test_no_second_request_when_not_required(self, api):
        api.session.post = MagicMock(return_value=_mock_response(200, self.SUCCESS))
        api.authenticate(totp_code="123456")
        assert api.session.post.call_count == 1
        assert "token" not in api.session.post.call_args.kwargs["json"]

    def test_secret_generates_code(self, monkeypatch):
        api = NeptunAPI("test", "pass123", totp_secret="JBSW Y3DP EHPK 3PXP")
        monkeypatch.setattr("neptun_api.client.generate_totp", lambda secret: f"code-for-{secret}")
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE), _mock_response(200, self.SUCCESS)])
        api.authenticate()
        sent = api.session.post.call_args_list[1].kwargs["json"]["token"]
        assert sent == "code-for-JBSWY3DPEHPK3PXP"

    def test_callback_supplies_code(self):
        api = NeptunAPI("test", "pass123", two_factor_callback=lambda: " 654321 ")
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE), _mock_response(200, self.SUCCESS)])
        api.authenticate()
        assert api.session.post.call_args_list[1].kwargs["json"]["token"] == "654321"

    def test_explicit_code_wins_over_secret(self, monkeypatch):
        api = NeptunAPI("test", "pass123", totp_secret="JBSWY3DPEHPK3PXP")
        monkeypatch.setattr("neptun_api.client.generate_totp", lambda secret: "999999")
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE), _mock_response(200, self.SUCCESS)])
        api.authenticate(totp_code="123456")
        assert api.session.post.call_args_list[1].kwargs["json"]["token"] == "123456"

    def test_rejected_code_raises_auth_error(self, api):
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE), _mock_response(202, self.CHALLENGE)])
        with pytest.raises(NeptunAuthError, match="rejected"):
            api.authenticate(totp_code="000000")
        assert api.token is None

    def test_rejected_code_400_surfaces_server_message(self, api):
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE),
            _mock_response(400, {"modelStateErrors": [{"errors": ["Invalid token"]}]})])
        with pytest.raises(NeptunAuthError, match="Invalid token"):
            api.authenticate(totp_code="000000")

    def test_captcha_required_raises(self, api):
        data = {"data": {**self.CHALLENGE["data"], "isCaptchaRequired": True,
                         "isTwoFactorRequired": False}}
        api.session.post = MagicMock(return_value=_mock_response(202, data))
        with pytest.raises(NeptunCaptchaRequired, match="captcha"):
            api.authenticate()

    def test_reauth_on_401_uses_secret(self, monkeypatch):
        api = NeptunAPI("test", "pass123", totp_secret="JBSWY3DPEHPK3PXP")
        api.token = "expired"
        monkeypatch.setattr("neptun_api.client.generate_totp", lambda secret: "111111")
        api.session.get = MagicMock(side_effect=[
            _mock_response(401), _mock_response(200, {"data": {"ok": True}})])
        api.session.post = MagicMock(side_effect=[
            _mock_response(202, self.CHALLENGE), _mock_response(200, self.SUCCESS)])
        assert api._get("Anything") == {"data": {"ok": True}}
        assert api.token == "tok2fa"
        assert api.session.post.call_args_list[1].kwargs["json"]["token"] == "111111"


class TestGenerateTotp:
    # RFC 6238 appendix B vectors (SHA-1, ASCII secret "12345678901234567890"),
    # truncated to the 6 digits Neptun's authenticator dialog accepts.
    SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

    @pytest.mark.parametrize("at,expected", [
        (59, "287082"), (1111111109, "081804"), (1111111111, "050471"),
        (1234567890, "005924"), (2000000000, "279037"), (20000000000, "353130"),
    ])
    def test_rfc6238_vectors(self, at, expected):
        assert generate_totp(self.SECRET, at=at) == expected

    def test_ignores_spaces_dashes_and_case(self):
        assert generate_totp("gezd-gnbv gy3t qojq gezd gnbv gy3t qojq", at=59) == "287082"

    def test_unpadded_secret(self):
        # Authenticator apps hand out secrets without base32 padding.
        assert generate_totp("JBSWY3DPEHPK3PXP", at=0) == generate_totp("JBSWY3DPEHPK3PXP", at=29)

    def test_uses_current_time_by_default(self, monkeypatch):
        monkeypatch.setattr("neptun_api.client.time.time", lambda: 59.0)
        assert generate_totp(self.SECRET) == "287082"

    def test_invalid_secret(self):
        with pytest.raises(ValueError, match="base32"):
            generate_totp("not-base32!!")
