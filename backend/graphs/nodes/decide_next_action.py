"""
Graph 2 groundwork — NOT wired into any graph yet. Reusable core of the
future `decide_next_action` node: given a goal, the current page's
simplified DOM summary, and recent step history, ask Gemini for exactly one
next action from a fixed enum. Exposed as a plain function so
test_navigate_shortlist.py can exercise it standalone before Graph 2 exists.

Model is Gemini Flash (not Claude) per the settled multi-model split —
this is the high-volume/lower-judgment navigation loop; Claude stays
reserved for the weekly scoring pass (agent_memory/sentinel_project.md).
"""
import json
import time

from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

MODEL_NAME = "gemma-4-26b-a4b-it"
REQUEST_TIMEOUT_MS = 20_000
MAX_ATTEMPTS = 3

PAGE_STATES = [
    "signin_required",
    "application_form",
    "verification_required",
    "captcha_present",
    "confirmation_page",
    "in_transit",
]

ACTION_TYPES = ["click", "fill", "select", "dismiss", "wait", "navigate"]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "page_state": {"type": "string", "enum": PAGE_STATES},
        "reasoning": {"type": "string"},
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ACTION_TYPES},
                "target": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["type", "target"],
        },
    },
    "required": ["page_state", "reasoning", "action"],
}

PROMPT_TEMPLATE = """\
You are navigating a web browser toward a goal. You will not get another \
turn after this one for this step — decide now.

Goal: {goal}

Current page URL: {current_url}
(Use the domain to inform your judgment — e.g. major platforms like \
LinkedIn commonly show persistent nav-bar sign-in elements on every page \
regardless of whether login is actually required to proceed toward the \
goal; a company's own ATS/careers domain (Ashby, Greenhouse, Lever, \
Workday, etc.) is more likely to have its real application form directly \
reachable.)

Current page summary:
{page_summary_json}

Notes on reading this summary:
- `modals` lists any overlay/modal/popup/dialog elements detected on the \
page (matched by role=dialog, aria-modal, or modal/popup/overlay-style \
class names), each with its own `visible` flag and the buttons/links \
inside it. If any entry here has `visible: true`, it is sitting on top of \
the page right now and must be dealt with before anything else — treat \
this list as authoritative for "is something blocking me," don't rely on \
spotting a stray button/link in the other lists to infer a popup exists.
- `forms` groups fields by their actual enclosing <form>, each with its \
own `submit_buttons` and a `visible` flag. `visible: false` means that \
form exists in the DOM but is not currently shown on screen (e.g. a login \
modal that only appears after clicking a "Sign in" trigger) — it cannot \
be blocking your goal right now if it isn't visible.
- `loose_fields` are inputs not inside any <form> tag — treat these as \
lower-confidence/no known submit action.
- `buttons`/`links` outside of any form are page-level navigation, not \
tied to a specific field set.
- Duplicate/repeated elements have already been collapsed to one entry \
each.

Recent history (your last few actions on this task, oldest first — use \
this to avoid repeating an action that already didn't move you forward):
{history_json}

First classify the current page into exactly one page_state:
- signin_required: reaching the goal from here genuinely requires logging in first — not just that a sign-in element exists somewhere on the page
- application_form: this page IS the job application form itself (has fields for name/resume/answers specific to applying, not just a search/login bar)
- verification_required: an email/OTP/phone verification step is being asked for
- captcha_present: a CAPTCHA is present — you cannot solve it, only report it
- confirmation_page: an application was just submitted and this confirms it
- in_transit: none of the above — just a step along the way (e.g. cookie banner, job description page, an "Apply" link to follow, an aggregator page you need to click through)

Before proposing an action, check the `modals` list for ANY entry with \
`visible: true` — cookie banners, newsletter/email-alert signups, survey \
prompts, notification permission dialogs, etc. There is often more than \
one, and they can stack (e.g. a cookie banner AND a separate email-alert \
modal at once). Dismissing one does NOT mean the page is clear — check \
the current summary's `modals` list itself, not just your last action, \
and check history for any modal you've already dismissed this task to \
confirm you're not still missing another one. If ANY modal is still \
visible, your action this turn MUST target dismissing it, using one of \
its own `buttons`/`links` as the target (page_state: in_transit) — do \
not skip ahead to the main goal action while a modal is still visible, \
even one you consider minor.

Then propose exactly ONE next action to move toward the goal, from this \
fixed set: click, fill, select, dismiss, wait, navigate. `target` is a \
short freeform description of the element (its visible text/label/\
placeholder) so it can be matched against the real DOM. `value` is only \
used for fill/select — omit or leave empty otherwise.

You do NOT have access to real login credentials and must never invent \
one. If the field you're filling is an email/username/phone or password \
field belonging to a sign-in form, set `value` to the literal string \
"__CREDENTIAL__" — the executor substitutes the real stored value \
locally, you never see or choose it. Only ever use "__CREDENTIAL__" for \
that exact case; for every other fill/select, put the real value \
yourself as normal.

`reasoning` must do two things, specifically — a generic sentence that \
could apply to any job page (e.g. "this is a transitional page, clicking \
Apply moves toward the goal") is not acceptable and will be treated as a \
wrong answer:
1. Name the specific element(s) from the summary above (exact text/label/\
name) that justify the page_state you picked.
2. Explicitly say whether you considered signin_required for this page, \
and if you rejected it, ground it in the `forms`/`visible` data above — \
e.g. "the login form is present but visible: false, so it isn't blocking \
anything right now" vs "no login form exists on this page at all" vs \
whatever is actually true here. Don't assert a page_state without \
checking the forms array first.
"""


def decide(goal: str, page_summary: dict, current_url: str = "", history: list[str] | None = None) -> dict:
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
    )
    prompt = PROMPT_TEMPLATE.format(
        goal=goal,
        current_url=current_url,
        page_summary_json=json.dumps(page_summary, indent=2),
        history_json=json.dumps(history or [], indent=2),
    )

    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                ),
            )
            return json.loads(response.text)
        except genai_errors.ServerError as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2 * (attempt + 1))
    raise last_exc
