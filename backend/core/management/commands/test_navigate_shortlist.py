import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from playwright.sync_api import sync_playwright

URL = "https://www.linkedin.com/jobs/view/4395479506/"

# Gitignored — real session cookies, never committed.
STATE_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "linkedin_state.json"

GOAL = "Complete and submit the job application on this page, step by step."

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "target": {"type": "string"},
    },
    "required": ["reasoning", "target"],
}


def ask_gemini(current_url: str, buttons: list[str], links: list[str], history: list[str]) -> dict:
    prompt = f"""\
You are helping complete a job application. You will not get another turn \
after this one — decide now.

Goal: {GOAL}

Current page URL: {current_url}

Buttons on this page: {json.dumps(buttons)}
Links on this page: {json.dumps(links)}

Recent history (what you already clicked, oldest first): {json.dumps(history)}

Pick exactly ONE button or link text from the lists above to click next to \
move the application forward. Put that exact text in `target`. Explain \
your choice briefly in `reasoning`.
"""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Gemini occasionally returns a transient 503 ("model currently
    # experiencing high demand") that has nothing to do with our prompt or
    # data — retry a few times with a short delay before giving up.
    last_exc = None
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                ),
            )
            return json.loads(response.text)
        except genai_errors.ServerError as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
    raise last_exc


def click_and_follow(context, page, element):
    """Clicks `element` and returns whichever page is now active — the
    same `page` if it just navigated in place, or a new page if the click
    opened a new tab (common for LinkedIn's off-site "Apply" links, which
    is why simply re-reading the original `page` after clicking looked
    like nothing happened: the real destination was in a tab we never
    looked at)."""
    try:
        with context.expect_page(timeout=4000) as new_page_info:
            element.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("load", timeout=15000)
        return new_page
    except Exception:
        # No new tab opened within the window — assume it navigated the
        # current page in place, which is the common case.
        return page


class Command(BaseCommand):
    help = "Open a fixed LinkedIn job URL, click Apply, then let Gemini drive the application step by step."

    def add_arguments(self, parser):
        parser.add_argument(
            "--login",
            action="store_true",
            help="Open a blank LinkedIn login page, let you log in by hand, then save the session to linkedin_state.json.",
        )

    def handle(self, *args, **options):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)

            if options["login"]:
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://www.linkedin.com/login", timeout=30000)
                input("Log in manually in the opened browser, then press Enter here once you're on your LinkedIn feed... ")
                context.storage_state(path=str(STATE_PATH))
                self.stdout.write(f"Session saved to {STATE_PATH}")
                browser.close()
                return

            if STATE_PATH.exists():
                context = browser.new_context(storage_state=str(STATE_PATH))
                self.stdout.write("Loaded saved LinkedIn session.")
            else:
                context = browser.new_context()
                self.stdout.write("No saved session found (run with --login first) — continuing logged out.")

            page = context.new_page()
            page.goto(URL, timeout=30000, wait_until="load")
            page.wait_for_timeout(2000)

            elements = page.query_selector_all("button, a")
            for el in elements:
                text = (el.inner_text() or "").strip()
                if text:
                    self.stdout.write(f"[{el.evaluate('e => e.tagName')}] {text}")

            apply_button = None
            for el in elements:
                text = (el.inner_text() or "").strip()
                if "apply" in text.lower() and el.is_visible():
                    apply_button = el
                    break

            if apply_button:
                page = click_and_follow(context, page, apply_button)
                self.stdout.write(f"Clicked Apply. Now on: {page.url}")
            else:
                self.stdout.write("No visible Apply button found.")

            page.wait_for_timeout(3000)

            history: list[str] = []
            while True:
                elements = page.query_selector_all("button, a")
                buttons, links = [], []
                for el in elements:
                    text = (el.inner_text() or "").strip()
                    if not text or not el.is_visible():
                        continue
                    tag = el.evaluate("e => e.tagName")
                    (buttons if tag == "BUTTON" else links).append(text)
                buttons = list(dict.fromkeys(buttons))
                links = list(dict.fromkeys(links))

                self.stdout.write(f"\nbuttons: {buttons}")
                self.stdout.write(f"links: {links}")

                decision = ask_gemini(page.url, buttons, links, history)
                self.stdout.write(f"gemini_reasoning: {decision['reasoning']}")
                self.stdout.write(f"gemini_target: {decision['target']}")

                answer = input("Click this? [y/N/q to stop] ").strip().lower()
                if answer == "q":
                    break
                if answer != "y":
                    continue

                target = decision["target"]
                matched = None
                for el in elements:
                    if (el.inner_text() or "").strip() == target and el.is_visible():
                        matched = el
                        break
                if not matched:
                    self.stdout.write("Could not find that element anymore — skipping.")
                    continue

                page = click_and_follow(context, page, matched)
                history.append(target)
                self.stdout.write(f"Now on: {page.url}")
                page.wait_for_timeout(2000)

            while input("Press q then Enter to close the browser: ").strip().lower() != "q":
                pass

            browser.close()
