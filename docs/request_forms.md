# Neptun Request Forms - Search, Fill & Submit Guide

Complete guide to working with Neptun university request forms (kerveny) programmatically via the `neptun_api` Python wrapper. Covers template discovery, field inspection, form filling, and submission.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Step 1: Search for Form Templates](#step-1-search-for-form-templates)
- [Step 2: Start a Form](#step-2-start-a-form)
- [Step 3: Inspect the Current Page](#step-3-inspect-the-current-page)
- [Step 4: Extract Field Information](#step-4-extract-field-information)
- [Step 5: Fill and Advance Pages](#step-5-fill-and-advance-pages)
- [Step 6: Preview and Submit](#step-6-preview-and-submit)
- [High-Level Helper](#high-level-helper)
- [Common Form Types](#common-form-types)
- [Payload Format (Critical)](#payload-format-critical)
- [Field Naming Conventions](#field-naming-conventions)
- [Tracking Submitted Forms](#tracking-submitted-forms)
- [Error Handling](#error-handling)
- [Pitfalls and Gotchas](#pitfalls-and-gotchas)
- [Full Example: Submit OE-0074 Petition](#full-example-submit-oe-0074-petition)
- [API Reference](#api-reference)

---

## Overview

Neptun's request form system allows students to submit official petitions, applications, and administrative requests to the university. The web UI renders forms inside iframes using server-generated HTML + jQuery. The API exposes this through two controller groups:

- **`RequestForm`** - Read-only operations: list templates, view submitted/sent-back/invalidated forms, download attachments
- **`RequestFormCore`** - Interactive operations: start a form, get pages, save fields, advance, submit

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  1. Get          │────>│  2. Start Form   │────>│  3. Get Current │
│  Templates       │     │  (session-based) │     │  Page           │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          v
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  6. Submit       │<────│  5. Preview Page  │<────│  4. Fill Fields │
│                  │     │  (isPreviewPage)  │     │  & Step Next    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

Key design points:
- The active form is **session-based** - only one form can be in progress at a time per session
- Template IDs are **session-specific GUIDs** that change every login
- Pages advance server-side; `GetCurrentPage` takes no parameters
- Fields must be sent in **jQuery `serializeArray()` format**, not as a flat dict

---

## Step 1: Search for Form Templates

```python
from neptun_api import NeptunAPI

api = NeptunAPI("YOUR_CODE", "YOUR_PASS",
                base_url="https://neptun.uni-obuda.hu/ujhallgato/api/")
api.authenticate()

# Get all available form templates
templates = api.get_student_request_form_templates()

for t in templates:
    print(f"  {t['templateName']} -> ID: {t['requestFormTemplateId']}")
```

Each template object contains:

| Field | Type | Description |
|-------|------|-------------|
| `requestFormTemplateId` | `str` (GUID) | Session-specific ID, changes every login |
| `templateName` | `str` | Display name (e.g., "OE-0074 - Altalanos kerelem") |
| `isFree` | `bool` | Whether submission is free or costs a fee |
| `price` | `int` | Fee in HUF (e.g., 4000 for OE-0052) |

You can also check forms you've already started but not yet submitted:

```python
started = api.get_started_request_form_templates()
```

### Searching by name

```python
# Find a specific form type
query = "OE-0074"
matches = [t for t in templates if query.lower() in t['templateName'].lower()]
print(f"Found {len(matches)} match(es): {[m['templateName'] for m in matches]}")
```

---

## Step 2: Start a Form

```python
template_id = matches[0]['requestFormTemplateId']
form_info = api.start_request_form(template_id)
```

This sets the active form context for the session. All subsequent `GetCurrentPage`, `SavePageAndStepNext`, and `Submit` calls operate on this form.

> **Warning:** Template IDs are session-specific GUIDs. Never hardcode them. Always fetch fresh from `get_student_request_form_templates()` in the same session.

---

## Step 3: Inspect the Current Page

```python
page = api.get_request_form_current_page()
```

The page object contains:

| Field | Type | Description |
|-------|------|-------------|
| `pageHTML` | `str` | Raw HTML of the form page (inputs, textareas, selects) |
| `pageJavascripts` | `list[str]` | JavaScript snippets (contain required field info) |
| `isPreviewPage` | `bool` | `True` when all pages are filled and ready to submit |
| `pageNumber` | `int` | Current page number (1-based) |
| `totalPages` | `int` | Total number of pages in the form |

---

## Step 4: Extract Field Information

Use the built-in field parser to extract structured info from the raw HTML:

```python
fields = api.get_request_form_page_fields(page)

for f in fields:
    req = " [REQUIRED]" if f['required'] else ""
    print(f"  {f['name']} ({f['tag']}){req}")
    if f['options']:
        for val, label in f['options']:
            print(f"    - '{val}' = {label}")
```

Example output for OE-0030:
```
  T_1 (textarea)
  D_2 (select) [REQUIRED]
    - '---' = ---
    - '1' = 2024/25/2
    - '2' = 2025/26/1
  T_3 (textarea)
  D_4 (select) [REQUIRED]
    - '---' = ---
    - '101' = Matematika I.
    - '102' = Programozas alapjai
  ...
```

### Field types

| Tag | Prefix | Description |
|-----|--------|-------------|
| `textarea` | `T_` | Free-text area for longer input |
| `input` | `T_` | Single-line text input |
| `select` | `D_` | Dropdown menu with predefined options |

---

## Step 5: Fill and Advance Pages

```python
# Fill fields for the current page
page_fields = {
    'T_1': 'I respectfully request to drop the subject Declarative Programming...',
    'D_2': '2',  # Select option value, NOT the display label
}

response = api.save_request_form_page_next(page_fields)
```

The method internally converts the flat dict to the correct wire format (see [Payload Format](#payload-format-critical)).

### Checking for validation errors

```python
notifications = response.get('notification', [])
errors = [n for n in notifications if n.get('type') == 0]
if errors:
    for e in errors:
        print(f"  ERROR: {e['description']}")
    # The page did NOT advance - fix the fields and retry
```

If the server rejects the page (missing required fields, invalid values), it returns the **same page** with error notifications. The page does not advance.

### Multi-page forms

Some forms have multiple pages. After `save_request_form_page_next`, call `get_request_form_current_page()` again to get the next page's fields:

```python
for page_num in range(20):  # safety limit
    page = api.get_request_form_current_page()
    
    if page.get('isPreviewPage', False):
        print("Reached preview page - ready to submit!")
        break
    
    fields = api.get_request_form_page_fields(page)
    page_fields = {}
    for f in fields:
        page_fields[f['name']] = your_values.get(f['name'], '')
    
    api.save_request_form_page_next(page_fields)
```

---

## Step 6: Preview and Submit

Once `isPreviewPage` is `True`, the form is ready:

```python
page = api.get_request_form_current_page()
assert page['isPreviewPage'] == True

# Preview the filled content (the HTML shows a read-only summary)
print(page['pageHTML'])  # Shows what will be submitted

# Submit
result = api.submit_request_form()
print("Form submitted successfully!")
```

---

## High-Level Helper

For simple forms, use the all-in-one helper that handles template search, page iteration, and submission:

```python
result = api.fill_and_submit_request_form(
    template_name='OE-0074',
    fields={
        'T_1': 'I request permission to drop Declarative Programming (NSWDEPHBNF). '
               'My specialization courses require significant time investment, '
               'and I am unable to give this elective adequate attention this semester.',
    },
    submit=True  # Set to False to stop at preview without submitting
)
```

Parameters:
- `template_name` - Partial match against template names (case-insensitive)
- `fields` - Dict of all field names to values across ALL pages
- `submit` - Whether to submit or stop at preview

The helper:
1. Searches available templates by name
2. Falls back to started templates if no match
3. Iterates through all pages, filling matching fields
4. Raises `NeptunRequestError` on validation errors
5. Submits when the preview page is reached

---

## Common Form Types

Form types at Obuda University (may vary by institution):

| Code | Name | Fee | Use Case |
|------|------|-----|----------|
| **OE-0074** | Altalanos kerelem (General petition) | Free | General-purpose request: drop subjects, deadline extensions, etc. |
| **OE-0052** | Dékáni méltányossági kérelem (Dean's mercy petition) | 4,000 HUF | Grade correction, failed exam re-take, exceptional circumstances |
| **OE-0030** | Tantárgyfelvételi kérelem (Subject registration request) | Varies | Request to register for a subject outside normal registration period |
| **OE-0031** | Vizsgajelentkezési kérelem (Exam registration request) | Varies | Request to register for an exam outside normal period |
| **OE-0041** | Passzív félév (Passive semester) | Varies | Request for a passive (gap) semester |
| **OE-0069** | Kreditelismerési kérelem (Credit recognition) | Varies | Transfer credits from another institution |

> **Tip:** OE-0074 (free general petition) is the most flexible. It can be used for almost any administrative request. OE-0052 (dean's mercy) has a fee but carries more weight for grade-related requests.

---

## Payload Format (Critical)

Neptun's backend expects fields in **jQuery `serializeArray()` format**:

```json
{
  "FormData": [
    {"name": "T_1", "value": "My request text..."},
    {"name": "D_2", "value": "2"}
  ]
}
```

**DO NOT** send a flat dict like `{"T_1": "text", "D_2": "2"}`. The server will accept it with HTTP 200 but **silently ignore all field values**, resulting in a blank submission.

The library handles this conversion automatically via `_build_form_data()`, so when using the wrapper methods you just pass a normal dict:

```python
# You write this:
api.save_request_form_page_next({'T_1': 'text', 'D_2': '2'})

# The library sends this:
# POST RequestFormCore/SavePageAndStepNext
# {"FormData": [{"name": "T_1", "value": "text"}, {"name": "D_2", "value": "2"}]}
```

If you ever need to build the payload manually (e.g., for `raw_post`):

```python
payload = NeptunAPI._build_form_data({'T_1': 'text', 'D_2': '2'})
api.raw_post("RequestFormCore/SavePageAndStepNext", data=payload)
```

---

## Field Naming Conventions

Field names in Neptun forms follow a pattern:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `T_1`, `T_3` | Text field (textarea or input) | Free text: justification, description |
| `D_2`, `D_4`, `D_7` | Dropdown (select) | Semester selection, subject selection |
| Numbers are sequential | Per-page field ordering | `T_1` is the first text field on the page |

### Dropdown values

For `<select>` fields, use the **option `value`**, not the display label:

```html
<select name="D_2">
  <option value="---">---</option>        <!-- Placeholder - do NOT use -->
  <option value="1">2024/25/2</option>    <!-- Use value="1" -->
  <option value="2">2025/26/1</option>    <!-- Use value="2" -->
</select>
```

```python
# Correct
page_fields['D_2'] = '2'       # Selects "2025/26/1"

# Wrong - placeholder, will be rejected as empty
page_fields['D_2'] = '---'

# Wrong - this is the display label, not the value
page_fields['D_2'] = '2025/26/1'
```

---

## Tracking Submitted Forms

After submission, track your forms through various states:

```python
# All submitted forms
submitted = api.get_submitted_request_forms()
for form in submitted:
    print(f"  {form['templateName']} - Status: {form['statusName']}")

# Forms sent back for correction
sent_back = api.get_sent_back_request_forms()

# Invalidated forms
invalidated = api.get_invalidated_request_forms()

# Detailed view of a specific submission
details = api.get_submitted_request_form_details(form_id)

# Download the form as PDF
pdf = api.download_request_form(form_id)

# View admin opinions/decisions
opinions = api.view_request_form_opinions(form_id)
filings = api.view_request_form_filings(form_id)

# Check scores (if applicable)
scores = api.get_request_form_scores(form_id)
total = api.get_request_form_total_score(form_id)
```

### Form lifecycle states

```
Available Template
    │
    v
Started (in progress)
    │
    v
Submitted ──────> Sent Back for Correction ──> Re-submitted
    │                                               │
    v                                               v
Approved / Rejected                          Approved / Rejected
    │
    v
Invalidated (if withdrawn or voided)
```

---

## Error Handling

```python
from neptun_api import NeptunRequestError

try:
    api.fill_and_submit_request_form('OE-0074', {'T_1': 'My request...'})
except NeptunRequestError as e:
    print(f"Form error: {e}")
    # Possible causes:
    # - "No template found matching 'OE-0074'"
    # - "Form validation failed: Required field is empty"
    # - "Form did not reach preview page after 20 pages"
```

### Common validation errors

| Error | Cause | Fix |
|-------|-------|-----|
| Required field is empty | A required dropdown or text field was not filled | Check `get_request_form_page_fields()` for `required: True` fields |
| Page doesn't advance | Same page returned after `SavePageAndStepNext` | Fill all required fields with valid (non-placeholder) values |
| 403 Forbidden | Session expired or form context lost | Re-authenticate and start the form again |
| Template not found | Template name doesn't match any available form | Check exact names with `get_student_request_form_templates()` |

---

## Pitfalls and Gotchas

### 1. Session-specific template IDs
Template IDs are GUIDs generated per session. **Never hardcode them.** Always fetch fresh:
```python
# Wrong - this ID won't work in a new session
api.start_request_form("a1b2c3d4-e5f6-...")

# Correct - fetch fresh each time
templates = api.get_student_request_form_templates()
template_id = templates[0]['requestFormTemplateId']
api.start_request_form(template_id)
```

### 2. Flat dict payloads are silently accepted but ignored
The server returns HTTP 200 for flat dict payloads but saves nothing. Your form will be submitted blank. Always use the wrapper methods which handle the conversion, or use `_build_form_data()` for raw calls.

### 3. GetCurrentPage takes no parameters
The endpoint is session-based. Passing an ID parameter causes a 403 error.

### 4. Dropdown placeholder `---` is rejected
The `---` option in dropdowns is a placeholder. The server treats it as empty for required fields. Always select a real option value.

### 5. One active form per session
Starting a new form replaces the previous active form. You cannot fill two forms simultaneously in one session.

### 6. Registration period enforcement is server-side
You cannot bypass closed registration periods through the API. The server checks the academic calendar regardless of what endpoint or payload you use. Use request forms (like OE-0074) to petition for changes outside the registration period.

---

## Full Example: Submit OE-0074 Petition

Complete working example to submit a general petition to drop a subject:

```python
from neptun_api import NeptunAPI, NeptunRequestError

api = NeptunAPI("YOUR_CODE", "YOUR_PASSWORD",
                base_url="https://neptun.uni-obuda.hu/ujhallgato/api/")
api.authenticate()

# --- Method 1: High-level helper (recommended) ---

try:
    result = api.fill_and_submit_request_form(
        template_name='OE-0074',
        fields={
            'T_1': (
                'Tisztelt Tanulmányi Osztály!\n\n'
                'Kérem, hogy a Deklaratív programozás (NSWDEPHBNF) '
                'tárgyat a 2025/26/2 félévben leadhassam. '
                'A szakirányos tárgyaim jelentős időráfordítást igényelnek, '
                'és nem tudok kellő figyelmet szentelni ennek a szabadon '
                'választható tárgynak.\n\n'
                'Köszönöm a segítséget!'
            ),
        },
        submit=True
    )
    print("Petition submitted successfully!")
except NeptunRequestError as e:
    print(f"Failed: {e}")


# --- Method 2: Step-by-step (for complex forms) ---

# 1. Find the template
templates = api.get_student_request_form_templates()
oe74 = [t for t in templates if 'OE-0074' in t['templateName']][0]

# 2. Start the form
api.start_request_form(oe74['requestFormTemplateId'])

# 3. Get and inspect the first page
page = api.get_request_form_current_page()
fields = api.get_request_form_page_fields(page)

print("Fields on this page:")
for f in fields:
    req = " [REQUIRED]" if f['required'] else ""
    print(f"  {f['name']} ({f['tag']}){req}")
    if f['options']:
        for val, label in f['options']:
            if val != '---':
                print(f"    '{val}' = {label}")

# 4. Fill the fields and advance
response = api.save_request_form_page_next({
    'T_1': 'My petition text here...',
})

# Check for errors
notifications = response.get('notification', [])
errors = [n for n in notifications if n.get('type') == 0]
if errors:
    print("Validation errors:")
    for e in errors:
        print(f"  - {e['description']}")
else:
    # 5. Check if we reached the preview page
    page = api.get_request_form_current_page()
    if page.get('isPreviewPage'):
        # 6. Submit
        result = api.submit_request_form()
        print("Submitted!")
    else:
        print("More pages to fill...")
```

---

## API Reference

### RequestForm (read-only, 26 methods)

| Method | Description |
|--------|-------------|
| `get_number_of_request_forms()` | Count of active request forms |
| `get_student_request_form_templates()` | List all available form templates |
| `get_student_request_form_template_details(id)` | Details of a specific template |
| `get_started_request_form_templates()` | Forms started but not submitted |
| `get_started_request_form_template_details(id)` | Details of a started form |
| `get_submitted_request_forms()` | List all submitted forms |
| `get_submitted_request_form_details(id)` | Details of a submitted form |
| `get_sent_back_request_forms()` | Forms sent back for correction |
| `get_sent_back_request_form_details(id)` | Details of a sent-back form |
| `get_invalidated_request_forms()` | Invalidated/voided forms |
| `get_invalidated_request_form_details(id)` | Details of an invalidated form |
| `get_request_form_scores(id)` | Scoring details for a form |
| `get_request_form_total_score(id)` | Total score for a form |
| `get_request_form_attachments(id)` | List attachments on a form |
| `get_request_form_attachment_details(id)` | Details of an attachment |
| `get_request_form_attach_appendix_info(id)` | Appendix info for a form |
| `save_request_form_attachments(data)` | Upload attachments |
| `delete_request_form_attachment(id)` | Delete an attachment |
| `get_document_library_for_request_form()` | Available documents to attach |
| `download_request_form(id)` | Download form as PDF |
| `download_request_form_attachments(params)` | Download attachments |
| `download_request_form_forms(params)` | Download form documents |
| `download_request_form_judgement_documents(params)` | Download judgement docs |
| `download_request_form_resolution(id)` | Download resolution document |
| `view_request_form_filings(id)` | View filing history |
| `view_request_form_opinions(id)` | View admin opinions/decisions |

### RequestFormCore (interactive, 12+ methods)

| Method | Description |
|--------|-------------|
| `start_request_form(template_id)` | Start filling a form (sets session context) |
| `get_request_form_current_page()` | Get the current page (session-based, no params) |
| `save_request_form_page_next(fields)` | Save fields and advance to next page |
| `save_request_form_page_prev(fields)` | Save fields and go back to previous page |
| `submit_request_form()` | Submit the active form (must be on preview page) |
| `get_request_form_page_fields(page)` | Parse field info from a page's HTML |
| `fill_and_submit_request_form(name, fields, submit)` | High-level: search, fill, submit |
| `interrupt_request_form(data)` | Interrupt/pause an active form |
| `invalidate_request_form(data)` | Invalidate a form |
| `revoke_request_form(data)` | Revoke a submitted form |
| `get_request_form_for_correction(id)` | Load a sent-back form for correction |
| `get_request_form_for_subject(params)` | Start a subject-specific form |
| `get_request_form_for_exam(params)` | Start an exam-specific form |
| `get_request_form_for_imposition(params)` | Start a financial imposition form |
| `get_request_form_for_registration(params)` | Start a registration-related form |
| `get_request_form_for_subject_equivalence(params)` | Start a credit equivalence form |

### Helper

| Method | Description |
|--------|-------------|
| `_build_form_data(fields)` | Static: convert `{'key': 'val'}` to `{"FormData": [{"name": "key", "value": "val"}]}` |
