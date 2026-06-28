"""Static guard: every NeptunAPI method referenced by an MCP tool must exist.

This prevents the MCP tool layer from drifting away from client.py (which had
~11 tools calling non-existent methods before this guard was added). It parses
the source rather than importing the optional `mcp` dependency.
"""
import re
import pathlib

import pytest

from neptun_api.client import NeptunAPI

MCP_SOURCE = pathlib.Path(__file__).resolve().parent.parent / "neptun_api" / "mcp_server.py"


def test_mcp_tools_reference_real_client_methods():
    text = MCP_SOURCE.read_text(encoding="utf-8")
    # Match both api.method(...) calls AND bare api.method references (e.g. passing
    # the bound method as a callable), so neither form can drift from the client.
    called = set(re.findall(r"\bapi\.([a-zA-Z_][a-zA-Z0-9_]*)", text))
    # ignore private attribute access (e.g. api._auth_data)
    called = {m for m in called if not m.startswith("_")}
    missing = sorted(m for m in called if not hasattr(NeptunAPI, m))
    assert not missing, f"MCP tools reference NeptunAPI members that do not exist: {missing}"


def test_get_student_info_does_not_expose_access_token():
    """The Bearer/access token must never be serialized into a tool result."""
    text = MCP_SOURCE.read_text(encoding="utf-8")
    assert "_to_json(api._auth_data)" not in text, \
        "get_student_info must not serialize the raw auth payload (it contains accessToken)"
    assert "accessToken" not in text, \
        "No MCP tool should reference/forward the accessToken"


def test_to_json_redacts_credentials_dynamically():
    """Defense-in-depth: _to_json must strip credential values from ANY payload
    (e.g. what call_method('authenticate'/'refresh_token') would return), so no
    tool can serialize the Bearer token into the model context."""
    pytest.importorskip("mcp")
    from neptun_api.mcp_server import _to_json
    out = _to_json({
        "accessToken": "SECRET_JWT_VALUE",
        "neptunCode": "ABC123",
        "nested": {"refreshToken": "RT_SECRET", "ok": 1},
        "list": [{"token": "T_SECRET"}],
    })
    assert "SECRET_JWT_VALUE" not in out
    assert "RT_SECRET" not in out
    assert "T_SECRET" not in out
    assert "ABC123" in out  # non-sensitive fields preserved


def test_call_method_denies_credential_methods():
    pytest.importorskip("mcp")
    from neptun_api.mcp_server import CALL_METHOD_DENYLIST
    assert {"authenticate", "refresh_token"} <= CALL_METHOD_DENYLIST


def test_call_method_gate_is_read_only_and_blocks_sensitive():
    """call_method must be safe-by-default: allow plain read methods, block all
    writes/auth and every secret/URL/2FA/PII-returning method confirmed leaky."""
    pytest.importorskip("mcp")
    from neptun_api.mcp_server import _call_method_allowed
    from neptun_api.client import NeptunAPI

    allowed = ["get_term_averages", "get_taken_subjects", "get_all_grades",
               "get_exam_results_list", "get_financial_impositions",
               "get_subject_application_terms"]
    blocked = [
        # writes / auth-lifecycle
        "authenticate", "refresh_token", "change_password", "reset_password",
        "logout", "delete_totp_key", "outer_login", "forgotten_password",
        "raw_get", "raw_post", "raw_put", "raw_delete", "sign_up_for_exam",
        "subject_signin", "save_request_form_page_next", "submit_request_form",
        # secret / URL-with-token / 2FA / PII reads
        "get_calendar_export_links", "generate_new_calendar_export_links",
        "get_omhv_report_url", "get_unipoll_url_with_token_for_fill",
        "get_xeropan_url", "get_token_registration_data",
        "get_user_avatar", "get_message_pdf", "download_invoice_attachment",
        # capability *_uri / *_ticket / panopto / file reads (substring gate)
        "get_unipoll_exam_uri", "get_unipoll_task_uri",
        "get_panopto_ticket", "get_panopto_request", "get_gdpr_statement_file",
    ]
    for m in allowed:
        assert _call_method_allowed(m), f"{m} should be callable"
    for m in blocked:
        assert not _call_method_allowed(m), f"{m} must be blocked"
    # every blocked name that is a real method confirms the gate covers real surface
    for m in blocked:
        if hasattr(NeptunAPI, m):
            assert not _call_method_allowed(m)


def test_to_json_scrubs_secrets_in_string_values():
    """Key-based redaction can't see secrets inside string values (e.g. a token
    in a URL, or a raw JWT). _to_json must scrub those too."""
    pytest.importorskip("mcp")
    from neptun_api.mcp_server import _to_json
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpM"
    out = _to_json({
        "surveyUrl": f"https://unipoll.example.hu/fill?token={jwt}&lang=hu",
        "rawJwt": jwt,
        "keep": "https://neptun.example.hu/page?lang=hu&id=5",
    })
    assert jwt not in out
    assert "token=" + jwt not in out
    assert "lang=hu" in out          # non-secret query params preserved
    assert "id=5" in out             # benign data preserved


def test_redact_preserves_non_secret_values():
    pytest.importorskip("mcp")
    from neptun_api.mcp_server import _to_json
    out = _to_json({"neptunCode": "ABC123", "average": 4.35, "items": [1, 2, 3]})
    assert "ABC123" in out and "4.35" in out


def test_mcp_calls_have_correct_required_arity():
    """Each api.<method>(...) call in mcp_server must supply all required args."""
    import inspect
    text = MCP_SOURCE.read_text(encoding="utf-8")
    problems = []
    for m in sorted(set(re.findall(r"\bapi\.([a-zA-Z_][a-zA-Z0-9_]*)\(", text))):
        if m.startswith("_") or not hasattr(NeptunAPI, m):
            continue
        fn = getattr(NeptunAPI, m)
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        required = [p for p in sig.parameters.values()
                    if p.name != "self" and p.default is inspect._empty
                    and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
        # find the call(s) and count supplied args (rough: commas at top level + kwargs)
        for call in re.findall(rf"api\.{m}\((.*?)\)", text):
            supplied = 0 if call.strip() == "" else call.count(",") + 1
            if supplied < len(required):
                problems.append(f"{m}: needs {len(required)} args, call supplies {supplied}")
    assert not problems, "MCP calls missing required args: " + "; ".join(problems)
