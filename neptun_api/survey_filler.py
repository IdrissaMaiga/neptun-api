"""Automated Unipoll survey filler for Neptun questionnaires.

Requires: pip install playwright && python -m playwright install chromium
"""

import time
from playwright.sync_api import sync_playwright, Page


DEFAULT_RATING = 5
DEFAULT_TEXT = ""


def _fill_survey_page(page: Page, rating: int, text_answer: str) -> None:
    """Fill a single survey page: select ratings and optionally fill text fields."""
    radio_groups: dict[str, list] = {}
    radios = page.locator('input[type="radio"]').all()
    for radio in radios:
        name = radio.get_attribute("name") or ""
        if name not in radio_groups:
            radio_groups[name] = []
        radio_groups[name].append(radio)

    for name, group in radio_groups.items():
        if len(group) == 5:
            idx = max(0, min(rating - 1, 4))
        elif len(group) > 0:
            idx = len(group) - 1
        else:
            continue
        group[idx].click(force=True)
        time.sleep(0.1)

    if text_answer:
        textareas = page.locator("textarea").all()
        for ta in textareas:
            if ta.is_visible():
                ta.fill(text_answer)

    page.wait_for_timeout(500)


def fill_single_survey(
    page: Page,
    url: str,
    rating: int = DEFAULT_RATING,
    text_answer: str = DEFAULT_TEXT,
    dry_run: bool = False,
) -> bool:
    """Navigate to a Unipoll survey URL, fill it out, and submit.

    Args:
        page: Playwright page instance.
        url: Unipoll survey URL (from GetUnipollURLWithTokenForFill).
        rating: Rating to give for all 1-5 scale questions (1-5).
        text_answer: Text to write in free-text fields (empty = skip).
        dry_run: If True, fill but don't click submit.

    Returns:
        True if submitted successfully.
    """
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    start_btn = page.locator("button:has-text('START'), button:has-text('INDÍTÁS')")
    if start_btn.count() > 0:
        start_btn.first.click()
        page.wait_for_timeout(4000)
        page.wait_for_load_state("networkidle")

    max_pages = 20
    for _ in range(max_pages):
        _fill_survey_page(page, rating, text_answer)

        submit = page.locator("button:has-text('SUBMIT'), button:has-text('BEKÜLDÉS')")
        if submit.count() > 0 and submit.first.is_visible():
            if dry_run:
                return True
            submit.first.click()
            page.wait_for_timeout(2000)
            dialog_submit = page.locator(".cdk-overlay-container button:has-text('SUBMIT'), .cdk-overlay-container button:has-text('BEKÜLDÉS')")
            if dialog_submit.count() > 0:
                dialog_submit.first.click(force=True)
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle")
            return True

        next_btn = page.locator("button:has-text('NEXT'), button:has-text('Next'), button:has-text('TOVÁBB'), button:has-text('KÖVETKEZŐ')")
        if next_btn.count() > 0 and next_btn.first.is_visible():
            next_btn.first.click()
            page.wait_for_timeout(3000)
            page.wait_for_load_state("networkidle")
            continue

        break

    return False


def fill_all_surveys(
    neptun_api,
    rating: int = DEFAULT_RATING,
    text_answer: str = DEFAULT_TEXT,
    dry_run: bool = False,
    headless: bool = True,
) -> list[dict]:
    """Fill all pending Unipoll questionnaires.

    Args:
        neptun_api: Authenticated NeptunAPI instance.
        rating: Rating for all 1-5 scale questions.
        text_answer: Text for free-text fields.
        dry_run: If True, fill forms but don't submit.
        headless: Run browser without GUI.

    Returns:
        List of dicts with survey name, status, and any errors.
    """
    questionnaires = neptun_api.get_questionnaires()
    if isinstance(questionnaires, dict) and "data" in questionnaires:
        questionnaires = questionnaires["data"]

    pending = [q for q in questionnaires if q.get("uiDisplayState", {}).get("type") in (0, 2)]

    if not pending:
        return [{"status": "no_pending", "message": "No pending surveys found."}]

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        for q in pending:
            subject = q.get("subjectName", "Unknown")
            course = q.get("courseCode", "Unknown")
            report_id = q["unipollReportId"]
            entry = {"subject": subject, "course": course, "report_id": report_id}

            try:
                survey_url = neptun_api.get_unipoll_url_with_token_for_fill(report_id)
                if isinstance(survey_url, dict):
                    survey_url = survey_url.get("data", survey_url.get("url", ""))
                survey_url = str(survey_url)

                if not survey_url:
                    entry["status"] = "error"
                    entry["message"] = "Could not get survey URL"
                    results.append(entry)
                    continue

                success = fill_single_survey(page, survey_url, rating, text_answer, dry_run)
                entry["status"] = "submitted" if success else "failed"
                if dry_run and success:
                    entry["status"] = "dry_run_ok"

            except Exception as e:
                entry["status"] = "error"
                entry["message"] = str(e)

            results.append(entry)
            print(f"  {'OK' if entry['status'] in ('submitted', 'dry_run_ok') else 'FAIL'}: "
                  f"{subject} ({course}) - {entry['status']}")

        browser.close()

    return results
