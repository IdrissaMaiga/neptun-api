# neptun-api

The most complete Python API wrapper for the Hungarian **Neptun** university system. Reverse-engineered from the Angular web client, covering **1,100+ endpoints** across 75+ controllers.

Built and tested against [Obuda University](https://neptun.uni-obuda.hu), but should work with any Neptun instance by changing the base URL. Instances that require two-factor login (e.g. University of Debrecen) are supported, see [Two-factor authentication](#two-factor-authentication).

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

# Get the grade for every subject across all terms (full transcript).
# This is the reliable way to read grades — including midterm marks and
# transfer/recognised grades — which get_subject_results_list does not return
# on many instances. (get_subject_result / get_subject_results_list are kept
# only as raw endpoint wrappers; prefer these.)
for g in api.get_all_grades():
    print(f'{g["term"]} [{g["subjectCode"]}] {g["subjectName"]}: {g["grade"]} ({g["gradeName"]})')

# Or one subject's result by its subject id
result = api.get_subject_grade(subject_id)   # {"resultValue": 4, "resultName": "Jó", "passed": True}

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
export NEPTUN_TOTP_SECRET=BASE32SECRET   # only for two-factor instances (see below)
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

There is also an installed console command equivalent to `python -m neptun_api`:
```bash
neptun-mcp --username YOUR_CODE --password YOUR_PASS
```

### Available MCP Tools (23)

| Tool | Description |
|---|---|
| `get_student_info` | Student profile, neptun code, training |
| `get_dashboard_data` | GPA, credit progress, unread messages |
| `get_term_averages` | GPA and credit index per semester |
| `get_all_grades` | Grade for every subject across all terms (full transcript) |
| `get_subject_grade` | Result/grade for one subject by ID |
| `get_taken_subjects` | Subjects taken in a term |
| `get_exam_results` / `get_exam_results_terms` | Exam results per term |
| `get_exams_list` | Available exams for a subject in a term |
| `get_received_messages` / `get_message_detail` | Read inbox / a thread |
| `get_calendar_events` | Calendar events by date range |
| `get_financial_impositions` / `get_financial_payments` | Fees and transactions |
| `get_pending_surveys` / `fill_all_surveys` | Surveys (Playwright auto-fill) |
| `call_method` / `list_methods` | Call/discover any of the 1,100+ API methods |
| *...and more* | Curriculum, documents, surveys |

## Authentication

The wrapper uses JWT Bearer tokens. Authentication is automatic — if your token expires mid-session, the client re-authenticates and retries transparently.

```python
api = NeptunAPI("code", "password", base_url="https://your-university.hu/ujhallgato/api/")
api.authenticate()

# Token refresh
api.refresh_token()

# Auto-retry on 401 is built in — you don't need to handle token expiry
```

### Two-factor authentication

Some universities (for example the **University of Debrecen**) require an authenticator-app code on every login. Their Neptun answers the first login with **HTTP 202** and `"isTwoFactorRequired": true` instead of a token; the official web client then re-sends the login with the 6-digit code in a `token` field. `authenticate()` does the same, and you have three ways to supply the code:

```python
from neptun_api import NeptunAPI, NeptunTwoFactorRequired

DEBRECEN = "https://www-h-ng.neptun.unideb.hu/hallgato_ng/api/"

# 1. Pass the code from your authenticator app for this login only
api = NeptunAPI("code", "password", base_url=DEBRECEN)
api.authenticate(totp_code=input("Authenticator code: "))

# 2. Ask for it whenever the client needs to (re-)authenticate
api = NeptunAPI("code", "password", base_url=DEBRECEN,
                two_factor_callback=lambda: input("Authenticator code: "))
api.authenticate()

# 3. Fully unattended: give the TOTP secret and codes are generated for you
#    (this is the base32 key behind the QR code shown when you registered the
#    authenticator — most apps let you view or export it; otherwise delete the
#    key in Neptun and register it again, noting the key this time).
api = NeptunAPI("code", "password", base_url=DEBRECEN, totp_secret="JBSWY3DPEHPK3PXP")
api.authenticate()
```

If none of these is provided and the instance asks for a second factor, `authenticate()` raises `NeptunTwoFactorRequired` (a `NeptunAuthError`). A wrong or expired code raises `NeptunAuthError`; after repeated failed logins Neptun may also demand a captcha, which surfaces as `NeptunCaptchaRequired` — log in once through the website to clear it.

Option 1 only covers the initial login: if the session later expires (401) the client cannot re-authenticate without a fresh code, so long-running scripts should use option 2 or 3. `generate_totp(secret)` is exported if you need the current code yourself; it is a dependency-free RFC 6238 implementation (6 digits, 30 s, SHA-1, the Google Authenticator defaults Neptun uses).

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

# University of Debrecen (two-factor login, see Authentication above)
api = NeptunAPI("code", "pass", base_url="https://www-h-ng.neptun.unideb.hu/hallgato_ng/api/",
                two_factor_callback=lambda: input("Authenticator code: "))

# Any Neptun instance — take the URL of the new student web (it ends in
# /ujhallgato/ or /hallgato_ng/ depending on the university) and append api/
```

> **Note:** Not all universities may have the same endpoints enabled. Some features (booking, theses, practice) may return 403 depending on your institution's configuration.

## Running Tests

```bash
# Unit tests
pip install -e ".[dev]"
pytest

# Live integration test (requires NEPTUN_USERNAME / NEPTUN_PASSWORD env vars)
NEPTUN_USERNAME=YOUR_CODE NEPTUN_PASSWORD=YOUR_PASS python tests/test_live_comprehensive.py
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
  test_client.py             # client unit tests (incl. grade API)
  test_models.py             # dataclass model tests
  test_mcp_server.py         # guards MCP tools against client drift
  test_live_comprehensive.py # live smoke test (run directly, needs creds)
docs/
  request_forms.md           # guide to the request-form (petition) endpoints
```

## License

MIT
