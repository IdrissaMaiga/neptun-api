"""MCP server for Neptun API.

Run with stdio (for Claude Code / Claude Desktop):
    python -m neptun_api.mcp_server --username CODE --password PASS

Run with SSE (for remote / port-forwarded access):
    python -m neptun_api.mcp_server --username CODE --password PASS --transport sse --port 8000

Environment variables are also supported:
    NEPTUN_USERNAME, NEPTUN_PASSWORD, NEPTUN_BASE_URL,
    NEPTUN_TOTP_SECRET (only for instances with two-factor login, e.g. Debrecen)
"""

import argparse
import inspect
import json
import os
import re
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from .client import NeptunAPI
from .exceptions import NeptunAPIError

mcp = FastMCP(
    "neptun-api",
    instructions="Neptun university system API — academics, grades, exams, messages, finances, surveys, and more.",
)

_api: NeptunAPI | None = None


def _get_api() -> NeptunAPI:
    global _api
    if _api is None:
        username = os.environ.get("NEPTUN_USERNAME", "")
        password = os.environ.get("NEPTUN_PASSWORD", "")
        base_url = os.environ.get("NEPTUN_BASE_URL", "https://neptun.uni-obuda.hu/ujhallgato/api/")
        totp_secret = os.environ.get("NEPTUN_TOTP_SECRET") or None
        if not username or not password:
            raise RuntimeError("Set NEPTUN_USERNAME and NEPTUN_PASSWORD environment variables or pass --username/--password")
        _api = NeptunAPI(username, password, base_url=base_url, totp_secret=totp_secret)
        _api.authenticate()
    return _api


def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (dict, list, str, int, float, bool, type(None))):
        return obj
    return _scrub_str(str(obj))  # scrub the str() fallback too (defense-in-depth)


# Credential-bearing keys that must never be serialized into a tool result /
# model context / transcript, regardless of which method produced them.
# Exact (lower-cased) key match — so 'token' is redacted but 'continuationToken'
# / 'token_type' / 'sortAndPage.token' are preserved.
SENSITIVE_KEYS = {
    "accesstoken", "access_token", "token", "refreshtoken", "refresh_token",
    "idtoken", "encryptedtoken", "jwt", "bearer", "authorization",
    "password", "pwd", "userpassword", "secret", "secretkey", "clientsecret",
    "sharedkey", "manualentrykey", "qrcodeurl", "recoverycodes",
    "apikey", "cookie", "setcookie", "sessionid", "sid",
}

# Secrets also hide inside string VALUES (key-based redaction can't see those):
# a raw JWT, or a token carried in a URL query string (e.g. the Unipoll fill URL
# returned by get_unipoll_url_with_token_for_fill).
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}")
_URL_SECRET_RE = re.compile(
    r"((?:[?&])(?:access_?token|refresh_?token|token|auth|jwt|sid|sessionid|"
    r"code|key|apikey|pwd|password|ticket|sig|signature|secret|encryptedtoken)=)[^&#\s\"']+",
    re.IGNORECASE,
)


def _scrub_str(s: str) -> str:
    s = _JWT_RE.sub("***REDACTED***", s)
    s = _URL_SECRET_RE.sub(r"\1***REDACTED***", s)
    return s


def _redact(obj):
    """Recursively strip credentials: by key name (dicts) and by value pattern
    (JWTs / token-bearing URLs in strings), so no tool can emit a secret."""
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if isinstance(k, str) and k.lower() in SENSITIVE_KEYS
                else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    if isinstance(obj, str):
        return _scrub_str(obj)
    return obj


# Methods that must not be invoked through the generic call_method tool:
# credential/auth operations — pointless via the tool and high-harm if a
# prompt-injection (e.g. a malicious Neptun message) tricks the model into them.
CALL_METHOD_DENYLIST = {"authenticate", "refresh_token", "change_password", "reset_password"}

# call_method is SAFE-BY-DEFAULT: it only runs read-only, non-sensitive methods.
# A method must start with a read-verb prefix AND contain no sensitive substring.
# This blocks the whole dangerous surface at once — every write/auth-lifecycle
# method (change_password, delete_totp_key, raw_post/put/delete, sign_up_*,
# save_*, ...) fails the prefix gate, and credential/URL/2FA/PII reads
# (get_*_url, get_token_registration_data, get_*_avatar, get_*_pdf,
# get_calendar_export_links, ...) fail the substring gate. Writes must go
# through the dedicated curated tools, not call_method.
_CALL_METHOD_READ_PREFIXES = ("get_", "list_", "is_", "has_", "search_", "count_")
_CALL_METHOD_BLOCK_SUBSTRINGS = (
    "token", "secret", "otp", "password", "pwd", "credential",
    "url", "uri", "link", "export", "avatar", "pdf", "attachment",
    "download", "file", "ticket", "panopto",
    "login", "logout", "auth", "oauth", "saml", "sso", "captcha",
    "qrcode", "recovery", "cookie", "session", "key",
)


def _call_method_allowed(name: str) -> bool:
    """True only for safe, read-only, non-sensitive client methods."""
    if name.startswith("_") or name in CALL_METHOD_DENYLIST:
        return False
    if not name.startswith(_CALL_METHOD_READ_PREFIXES):
        return False
    low = name.lower()
    return not any(sub in low for sub in _CALL_METHOD_BLOCK_SUBSTRINGS)


def _to_json(data) -> str:
    return json.dumps(_redact(data), default=_serialize, ensure_ascii=False, indent=2)


# ── Dashboard & Profile ──


@mcp.tool()
async def get_student_info() -> str:
    """Get current session info: neptun code, session timeout, days until password expiry.

    Returns only non-sensitive fields — never the Bearer/access token.
    """
    api = _get_api()
    auth = api._auth_data or {}
    safe_keys = (
        "neptunCode",
        "sessionTimeoutInMinutes",
        "numberOfDaysUntilADPasswordExpires",
        "isTwoFactorRequired",
        "isCaptchaRequired",
    )
    return _to_json({k: auth.get(k) for k in safe_keys})


@mcp.tool()
async def get_dashboard_data() -> str:
    """Get dashboard summary: term averages (GPA), credit progress, and unread message count."""
    api = _get_api()
    data = {}
    for key, fn in (
        ("term_averages", api.get_term_averages),
        ("credit_progress", api.get_dashboard_credit_progress),
        ("unread_messages", api.get_unread_message_count),
    ):
        try:
            data[key] = fn()
        except Exception as e:  # surface per-endpoint failures instead of hiding them
            data[f"{key}_error"] = f"{type(e).__name__}: {e}"
    return _to_json(data)


# ── Grades & Academics ──


@mcp.tool()
async def get_term_averages() -> str:
    """Get GPA and credit index for each semester."""
    api = _get_api()
    return _to_json(api.get_term_averages())


@mcp.tool()
async def get_all_grades() -> str:
    """Get the grade for every subject across all terms (full transcript).

    Includes midterm marks and recognised/transfer grades that the dedicated
    results endpoints omit. Each item has term, subjectCode, subjectName, credit,
    requirementType, grade (1-5 or null), gradeName, and passed.
    """
    api = _get_api()
    return _to_json(api.get_all_grades())


@mcp.tool()
async def get_subject_grade(subject_id: str) -> str:
    """Get the result/grade for one subject by its subject ID (resultValue, resultName, passed)."""
    api = _get_api()
    return _to_json(api.get_subject_grade(subject_id))


@mcp.tool()
async def get_taken_subjects(term_id: str) -> str:
    """Get subjects taken in a specific term. Use get_taken_subjects_terms() first to get term IDs."""
    api = _get_api()
    return _to_json(api.get_taken_subjects(term_id))


@mcp.tool()
async def get_taken_subjects_terms() -> str:
    """Get list of available terms (semesters) with their IDs."""
    api = _get_api()
    return _to_json(api.get_taken_subjects_terms())


@mcp.tool()
async def get_curriculum_completable_subjects(curriculum_id: str = "") -> str:
    """Get completable subjects for a curriculum. If curriculum_id is omitted, uses the student's first curriculum template."""
    api = _get_api()
    if not curriculum_id:
        templates = api.get_curriculum_templates()
        if not templates:
            return _to_json({"error": "No curriculum templates found"})
        curriculum_id = templates[0].get("curriculumTemplateId")
    return _to_json(api.get_curriculum_completable_subjects(curriculum_id))


# ── Exams ──


@mcp.tool()
async def get_exam_results_terms() -> str:
    """Get the list of terms that have exam results (with their IDs)."""
    api = _get_api()
    return _to_json(api.get_exam_results_terms())


@mcp.tool()
async def get_exam_results(term_id: str) -> str:
    """Get exam results for a term. Use get_exam_results_terms() first for term IDs."""
    api = _get_api()
    return _to_json(api.get_exam_results_list(term_id))


@mcp.tool()
async def get_exams_list(subject_id: str, term_id: str) -> str:
    """Get available exams for a subject in a term."""
    api = _get_api()
    return _to_json(api.get_exams_list(subject_id, term_id))


# Exam sign-up / unsubscribe are destructive writes whose exact POST body shape
# (ExamRegistration/SignUpForExam, /UnSubscribe) is not verified, so they are not
# exposed as curated tools. Use the client methods api.sign_up_for_exam(data) /
# api.unsubscribe_from_exam(data) (or call_method) once the payload is confirmed.


# ── Messages ──


@mcp.tool()
async def get_unread_message_count() -> str:
    """Get count of unread messages."""
    api = _get_api()
    return _to_json(api.get_unread_message_count())


@mcp.tool()
async def get_received_messages(first_row: int = 0, last_row: int = 20) -> str:
    """Get received messages (paginated)."""
    api = _get_api()
    return _to_json(api.get_received_messages(first_row, last_row))


@mcp.tool()
async def get_message_detail(message_id: str) -> str:
    """Read a specific message thread by ID (its posts)."""
    api = _get_api()
    return _to_json(api.get_message_posts(message_id))


# ── Calendar ──


@mcp.tool()
async def get_calendar_events(start_date: str, end_date: str) -> str:
    """Get calendar events between two dates (format: YYYY-MM-DD)."""
    api = _get_api()
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return _to_json(api.get_calendar_events(start, end))


# ── Finances ──


@mcp.tool()
async def get_financial_impositions() -> str:
    """Get all financial obligations (tuition, fees, etc.)."""
    api = _get_api()
    return _to_json(api.get_financial_impositions())


@mcp.tool()
async def get_financial_payments() -> str:
    """Get payment / transaction history."""
    api = _get_api()
    return _to_json(api.get_student_previous_transactions())


# ── Questionnaires / Surveys ──


@mcp.tool()
async def get_pending_surveys() -> str:
    """Get list of pending (unfilled) semester surveys."""
    api = _get_api()
    return _to_json(api.get_questionnaires())


@mcp.tool()
async def get_finished_surveys() -> str:
    """Get list of already completed surveys."""
    api = _get_api()
    return _to_json(api.get_finished_questionnaires())


@mcp.tool()
async def fill_all_surveys(rating: int = 5, text_answer: str = "") -> str:
    """Auto-fill all pending semester surveys using browser automation.

    Args:
        rating: Rating to give for all scale questions (1-5, default 5).
        text_answer: Optional text for free-text fields.

    Returns:
        List of results with subject, course, and status for each survey.
    """
    api = _get_api()
    from .survey_filler import fill_all_surveys as _fill
    results = _fill(api, rating=rating, text_answer=text_answer, headless=True)
    return _to_json(results)


# ── Documents ──


@mcp.tool()
async def get_document_containers() -> str:
    """Get document containers (folders) for uploading/downloading documents."""
    api = _get_api()
    return _to_json(api.get_document_container_dashboard())


# Course registration (SubjectApplication) is period- and instance-dependent
# (needs an open registration window, SubjectApplication term IDs and a subject
# type), so it is not exposed as a curated tool. The read-only parts
# (get_subject_application_* / get_schedulable_subjects) are reachable via
# call_method; the writes (subject_signin etc.) are intentionally not.


# ── Generic Method Caller ──


@mcp.tool()
async def call_method(method_name: str, args: str = "{}") -> str:
    """Call a read-only NeptunAPI method by name. Use list_methods() to discover callable methods.

    For safety this is restricted to read-only, non-sensitive methods (get_/list_/is_/…
    that do not return tokens, URLs-with-tokens, 2FA secrets, or binary/PII blobs).
    Write/auth operations must use the dedicated tools, not call_method.

    Args:
        method_name: Exact method name (e.g. 'get_term_averages', 'get_exam_results_list').
        args: JSON string of arguments. For positional args use a list, for keyword args use an object.
              Examples: '{}', '{"term_id": "abc"}', '["value1", "value2"]'
    """
    api = _get_api()
    method = getattr(api, method_name, None)
    if method is None:
        return _to_json({"error": f"Method '{method_name}' not found. Use list_methods() to see callable methods."})
    if not _call_method_allowed(method_name):
        return _to_json({"error": f"Method '{method_name}' is not callable via call_method "
                                  f"(only safe read-only methods are allowed; use the dedicated tools for writes)."})
    try:
        parsed = json.loads(args)
        if isinstance(parsed, dict):
            result = method(**parsed)
        elif isinstance(parsed, list):
            result = method(*parsed)
        else:
            result = method(parsed)
        return _to_json(result)
    except NeptunAPIError as e:
        return _to_json({"error": str(e)})
    except Exception as e:
        return _to_json({"error": f"{type(e).__name__}: {str(e)}"})


@mcp.tool()
async def list_methods(filter_text: str = "") -> str:
    """List the read-only NeptunAPI methods callable via call_method. Optionally filter by keyword.

    Only methods that call_method will actually run are listed (safe, read-only,
    non-sensitive). Writes/auth/secret-returning methods are intentionally hidden.

    Args:
        filter_text: Optional keyword to filter methods (e.g. 'exam', 'message', 'financial').
    """
    api = _get_api()
    methods = []
    for name in sorted(dir(api)):
        if not _call_method_allowed(name):
            continue
        attr = getattr(api, name, None)
        if not callable(attr):
            continue
        if filter_text and filter_text.lower() not in name.lower():
            continue
        try:
            sig = str(inspect.signature(attr))
        except (ValueError, TypeError):
            sig = "(...)"
        methods.append(f"{name}{sig}")
    return _to_json({"count": len(methods), "methods": methods})


def main():
    parser = argparse.ArgumentParser(description="Neptun API MCP Server")
    parser.add_argument("--username", help="Neptun code (or set NEPTUN_USERNAME)")
    parser.add_argument("--password", help="Neptun password (or set NEPTUN_PASSWORD)")
    parser.add_argument("--base-url", help="Neptun API base URL (or set NEPTUN_BASE_URL)")
    parser.add_argument("--totp-secret", help="Base32 TOTP secret for two-factor instances (or set NEPTUN_TOTP_SECRET)")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Bind address for sse/streamable-http (default 127.0.0.1, loopback only). "
             "This server has NO authentication and exposes a fully-authenticated, "
             "write-capable Neptun session — only bind a non-loopback address on a "
             "network you fully trust.",
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.username:
        os.environ["NEPTUN_USERNAME"] = args.username
    if args.password:
        os.environ["NEPTUN_PASSWORD"] = args.password
    if args.base_url:
        os.environ["NEPTUN_BASE_URL"] = args.base_url
    if args.totp_secret:
        os.environ["NEPTUN_TOTP_SECRET"] = args.totp_secret

    if args.transport != "stdio" and args.host not in ("127.0.0.1", "localhost", "::1"):
        import sys
        print(
            f"WARNING: binding {args.host}:{args.port} with no authentication. "
            "Anyone who can reach this port controls your Neptun account.",
            file=sys.stderr,
        )

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
