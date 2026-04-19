# neptun-api

The most complete Python API wrapper for the Hungarian **Neptun** university system. Reverse-engineered from the Angular web client, covering **1,100+ endpoints** across 75+ controllers.

Built and tested against [Obuda University](https://neptun.uni-obuda.hu), but should work with any Neptun instance by changing the base URL.

## Installation

```bash
pip install -e .                   # core API wrapper
pip install -e ".[survey]"         # + automated survey filler
pip install -e ".[all]"            # + survey + dev/test tools
```

For survey auto-fill, also run after install:
```bash
python -m playwright install chromium
```

**Requirements:** Python 3.11+, `requests`

## Quick Start

```python
from neptun_api import NeptunAPI

api = NeptunAPI("YOUR_NEPTUN_CODE", "YOUR_PASSWORD",
                base_url="https://neptun.uni-obuda.hu/ujhallgato/api/")
api.authenticate()

# Get your GPA
averages = api.get_term_averages()
for term in averages["termAveragesByTrainings"]:
    print(f'{term["average"]} avg, {term["creditIndex"]} credit index')

# Get current courses
terms = api.get_taken_subjects_terms()
subjects = api.get_taken_subjects(terms[1]["value"])  # [1] skips "0. felev"
for s in subjects:
    print(f'[{s["subjectCode"]}] {s["subjectName"]} - {s["subjectCredit"]} credits')

# Get unread messages
count = api.get_unread_message_count()
messages = api.get_received_messages(0, 20)

# Calendar
from datetime import datetime
events = api.get_calendar_events(datetime(2025, 9, 1), datetime(2026, 1, 31))

# Finances
impositions = api.get_financial_impositions()

# Auto-fill all pending semester surveys (rating 1-5)
from neptun_api import fill_all_surveys
results = fill_all_surveys(api, rating=5)
```

## What's Covered

| Area | Methods | Examples |
|---|---|---|
| **Dashboard** | 6 | GPA, credit progress, exam entries |
| **Messages** | 18+ | Inbox, sent, deleted, compose, recipients |
| **Calendar** | 29 | Events, export, subscriptions, filters |
| **Subjects & Courses** | 60+ | Taken subjects, registration, course changes |
| **Exams** | 30+ | Registration, results, remaining exams |
| **Grades & Advancement** | 21 | Term averages, credit index, curriculum progress |
| **Financial** | 50+ | Impositions, payments, invoices, scholarships |
| **Personal Data** | 113 | Addresses, emails, phones, documents, language exams |
| **Documents** | 49 | Upload, download, containers, folders |
| **Timetable & Rooms** | 38+ | Room schedule, booking, institutional timetable |
| **Curriculum** | 12 | Templates, subject groups, completable subjects |
| **Request Forms** | 62 | Submit, track, attachments, judgements |
| **Student Card** | 12 | Claims, address, status |
| **Tasks** | 28 | Assignments, documentation, deadlines |
| **Questionnaires** | 17 + auto-fill | List, fill out via browser automation, view results |
| **Consultation** | 12 | Appointments, sign up, drop |
| **E-Materials** | 28 | Course materials, downloads |
| **Online Occasions** | 24 | Virtual classes, Webex/Teams links |
| **Thesis** | 46+ | Application, upload, published theses |
| **Practice** | 26 | External practice, documentation |
| **Erasmus** | 15 | Applications, learning contracts |
| **Dormitory** | 16 | Registration, periods, applications |
| **Final Exams** | 15 | Periods, topics, applications |
| **MeetStreet** | 70+ | Forums, news, events, votes, e-learning |
| **Bank Account** | 17 | Manage payment accounts |
| **Publications** | 18 | Academic publications |
| **User Profile** | 29 | Settings, avatars, onboarding |
| **And more...** | | Specializations, modules, registry sheets, legal remedies |

**Total: 1,100+ methods**

## Auto-Fill Semester Surveys

Neptun's end-of-semester opinion surveys (Unipoll) can be filled automatically using browser automation. The filler handles both English and Hungarian survey interfaces.

```python
from neptun_api import NeptunAPI, fill_all_surveys

api = NeptunAPI("code", "password", base_url="https://neptun.uni-obuda.hu/ujhallgato/api/")
api.authenticate()

# Fill all pending surveys with 5/5 rating
results = fill_all_surveys(api, rating=5)

# Custom rating (1-5) and optional text comment
results = fill_all_surveys(api, rating=4, text_answer="Great course!")

# Dry run — fills forms but doesn't submit
results = fill_all_surveys(api, rating=5, dry_run=True)

# Show browser window (useful for debugging)
results = fill_all_surveys(api, rating=5, headless=False)
```

Each result dict contains `subject`, `course`, and `status` (`"submitted"`, `"failed"`, or `"error"`).

> **Requires:** `pip install playwright && python -m playwright install chromium`

## MCP Server

Run Neptun as an MCP server so any MCP-compatible AI (Claude Desktop, Claude Code, Cursor, etc.) can access your university data.

**Stdio** (local — Claude Desktop / Claude Code):
```bash
pip install -e ".[mcp]"
python -m neptun_api --username YOUR_CODE --password YOUR_PASS
```

**SSE** (remote / port-forwarded):
```bash
python -m neptun_api --username YOUR_CODE --password YOUR_PASS --transport sse --port 8000
```

**Streamable HTTP**:
```bash
python -m neptun_api --username YOUR_CODE --password YOUR_PASS --transport streamable-http --port 8000
```

Or use environment variables:
```bash
export NEPTUN_USERNAME=YOUR_CODE
export NEPTUN_PASSWORD=YOUR_PASS
export NEPTUN_BASE_URL=https://neptun.uni-obuda.hu/ujhallgato/api/
python -m neptun_api --transport sse --port 8000
```

### Claude Desktop config

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "neptun": {
      "command": "python",
      "args": ["-m", "neptun_api"],
      "env": {
        "NEPTUN_USERNAME": "YOUR_CODE",
        "NEPTUN_PASSWORD": "YOUR_PASS"
      }
    }
  }
}
```

### Available MCP Tools (26)

| Tool | Description |
|---|---|
| `get_student_info` | Student profile, neptun code, training |
| `get_dashboard_data` | GPA, credit progress, unread messages |
| `get_term_averages` | GPA and credit index per semester |
| `get_taken_subjects` | Subjects taken in a term |
| `get_exam_list` | Available exams |
| `register_for_exam` | Register for an exam |
| `get_received_messages` | Read inbox messages |
| `send_message` | Send a message |
| `get_calendar_events` | Calendar events by date range |
| `get_financial_impositions` | Tuition and fee obligations |
| `get_pending_surveys` | Unfilled semester surveys |
| `fill_all_surveys` | Auto-fill all surveys (Playwright) |
| `call_method` | Call any of the 1,100+ API methods by name |
| `list_methods` | Search/discover all available methods |
| *...and 12 more* | Timetable, courses, documents, registration |

## Authentication

The wrapper uses JWT Bearer tokens. Authentication is automatic — if your token expires mid-session, the client re-authenticates and retries transparently.

```python
api = NeptunAPI("code", "password", base_url="https://your-university.hu/ujhallgato/api/")
api.authenticate()

# Token refresh
api.refresh_token()

# Auto-retry on 401 is built in — you don't need to handle token expiry
```

## Raw Requests

For endpoints not yet wrapped, use the raw methods:

```python
# GET
data = api.raw_get("SomeController/SomeAction", params={"key": "value"})

# POST
data = api.raw_post("SomeController/SomeAction", data={"key": "value"})

# PUT / DELETE
data = api.raw_put("SomeController/SomeAction", data={"key": "value"})
data = api.raw_delete("SomeController/SomeAction", params={"key": "value"})
```

## Other Universities

Change the `base_url` to point to your university's Neptun instance:

```python
# Obuda University
api = NeptunAPI("code", "pass", base_url="https://neptun.uni-obuda.hu/ujhallgato/api/")

# BME
api = NeptunAPI("code", "pass", base_url="https://neptun.bme.hu/ujhallgato/api/")

# ELTE
api = NeptunAPI("code", "pass", base_url="https://neptun.elte.hu/ujhallgato/api/")

# Any Neptun instance — just find the /ujhallgato/api/ path
```

> **Note:** Not all universities may have the same endpoints enabled. Some features (booking, theses, practice) may return 403 depending on your institution's configuration.

## Running Tests

```bash
# Unit tests
pip install -e ".[dev]"
pytest

# Live integration test (requires real credentials in .env)
python test_live_comprehensive.py
```

## Project Structure

```
neptun_api/
  __init__.py        # Public exports
  __main__.py        # Entry point for python -m neptun_api
  client.py          # API wrapper (1,100+ methods)
  mcp_server.py      # MCP server (stdio / SSE / streamable-http)
  survey_filler.py   # Automated Unipoll survey filler (Playwright)
  models.py          # Dataclasses for common response types
  exceptions.py      # NeptunAuthError, NeptunRequestError
tests/
  test_client.py     # 22 unit tests
  test_models.py     # 17 model tests
```

## License

MIT
