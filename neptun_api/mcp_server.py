"""MCP server for Neptun API.

Run with stdio (for Claude Code / Claude Desktop):
    python -m neptun_api.mcp_server --username CODE --password PASS

Run with SSE (for remote / port-forwarded access):
    python -m neptun_api.mcp_server --username CODE --password PASS --transport sse --port 8000

Environment variables are also supported:
    NEPTUN_USERNAME, NEPTUN_PASSWORD, NEPTUN_BASE_URL
"""

import argparse
import inspect
import json
import os
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
        if not username or not password:
            raise RuntimeError("Set NEPTUN_USERNAME and NEPTUN_PASSWORD environment variables or pass --username/--password")
        _api = NeptunAPI(username, password, base_url=base_url)
        _api.authenticate()
    return _api


def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (dict, list, str, int, float, bool, type(None))):
        return obj
    return str(obj)


def _to_json(data) -> str:
    return json.dumps(data, default=_serialize, ensure_ascii=False, indent=2)


# ── Dashboard & Profile ──


@mcp.tool()
async def get_student_info() -> str:
    """Get current student profile: name, neptun code, training, active term."""
    api = _get_api()
    return _to_json(api._auth_data)


@mcp.tool()
async def get_dashboard_data() -> str:
    """Get dashboard summary: GPA, credit progress, upcoming exams, messages."""
    api = _get_api()
    data = {}
    try:
        data["term_averages"] = api.get_term_averages()
    except Exception:
        pass
    try:
        data["credit_progress"] = api.get_dashboard_credit_progress()
    except Exception:
        pass
    try:
        data["unread_messages"] = api.get_unread_message_count()
    except Exception:
        pass
    return _to_json(data)


# ── Grades & Academics ──


@mcp.tool()
async def get_term_averages() -> str:
    """Get GPA and credit index for each semester."""
    api = _get_api()
    return _to_json(api.get_term_averages())


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
async def get_curriculum_completable_subjects() -> str:
    """Get subjects remaining to complete in the curriculum."""
    api = _get_api()
    return _to_json(api.get_curriculum_completable_subjects())


# ── Exams ──


@mcp.tool()
async def get_exam_list() -> str:
    """Get all available exams for the current term."""
    api = _get_api()
    return _to_json(api.get_exam_list())


@mcp.tool()
async def get_taken_exams() -> str:
    """Get exam results for the current term."""
    api = _get_api()
    return _to_json(api.get_taken_exams())


@mcp.tool()
async def register_for_exam(exam_id: str) -> str:
    """Register for an exam by its ID."""
    api = _get_api()
    return _to_json(api.register_for_exam({"examId": exam_id}))


@mcp.tool()
async def unregister_from_exam(exam_id: str) -> str:
    """Unregister from an exam by its ID."""
    api = _get_api()
    return _to_json(api.unregister_from_exam({"examId": exam_id}))


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
    """Read a specific message by ID."""
    api = _get_api()
    return _to_json(api.get_message_detail(message_id))


@mcp.tool()
async def send_message(subject: str, body: str, recipient_ids: list[str]) -> str:
    """Send a message to one or more recipients."""
    api = _get_api()
    return _to_json(api.send_message({
        "subject": subject,
        "detail": body,
        "recipientIds": recipient_ids,
    }))


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
    """Get payment history."""
    api = _get_api()
    return _to_json(api.get_financial_payments())


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
    return _to_json(api.get_document_containers())


# ── Timetable ──


@mcp.tool()
async def get_timetable(term_id: str) -> str:
    """Get timetable for a specific term."""
    api = _get_api()
    return _to_json(api.get_timetable(term_id))


# ── Course Registration ──


@mcp.tool()
async def get_registrable_subjects() -> str:
    """Get subjects available for registration in the current period."""
    api = _get_api()
    return _to_json(api.get_registrable_subjects())


@mcp.tool()
async def get_registrable_courses(subject_id: str) -> str:
    """Get available courses for a registrable subject."""
    api = _get_api()
    return _to_json(api.get_registrable_courses(subject_id))


# ── Generic Method Caller ──


@mcp.tool()
async def call_method(method_name: str, args: str = "{}") -> str:
    """Call any NeptunAPI method by name. Use list_methods() to discover available methods.

    Args:
        method_name: Exact method name (e.g. 'get_term_averages', 'get_exam_list').
        args: JSON string of arguments. For positional args use a list, for keyword args use an object.
              Examples: '{}', '{"term_id": "abc"}', '["value1", "value2"]'
    """
    api = _get_api()
    method = getattr(api, method_name, None)
    if method is None or method_name.startswith("_"):
        return _to_json({"error": f"Method '{method_name}' not found. Use list_methods() to see available methods."})
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
    """List all available NeptunAPI methods. Optionally filter by keyword.

    Args:
        filter_text: Optional keyword to filter methods (e.g. 'exam', 'message', 'financial').
    """
    api = _get_api()
    methods = []
    for name in sorted(dir(api)):
        if name.startswith("_"):
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
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.username:
        os.environ["NEPTUN_USERNAME"] = args.username
    if args.password:
        os.environ["NEPTUN_PASSWORD"] = args.password
    if args.base_url:
        os.environ["NEPTUN_BASE_URL"] = args.base_url

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
