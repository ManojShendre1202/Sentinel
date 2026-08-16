"""
Raw fetch for TheirStack's /v1/jobs/search endpoint. One call, no
pagination — page_size in search_filters.yaml is the real cap.

Guardrail: checks the live credit-balance endpoint first and aborts
(SourceFetchError) if remaining credits can't cover the planned page_size
(1 credit per job returned) — real usage number from TheirStack itself,
not a locally-tracked counter that could drift out of sync.
"""
import requests

from sources import SourceFetchError
from sources.query_builder import build_theirstack_body, load_filters

SEARCH_URL = "https://api.theirstack.com/v1/jobs/search"
BALANCE_URL = "https://api.theirstack.com/v0/billing/credit-balance"


def check_credit_balance(api_key: str) -> dict:
    r = requests.get(BALANCE_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch(api_key: str) -> list[dict]:
    filters = load_filters()
    page_size = filters["page_size"]["theirstack"]

    try:
        balance = check_credit_balance(api_key)
    except requests.exceptions.RequestException as exc:
        raise SourceFetchError(f"theirstack: credit-balance check failed: {exc}") from exc

    remaining = balance.get("api_credits", 0) - balance.get("used_api_credits", 0)
    if remaining < page_size:
        raise SourceFetchError(
            f"theirstack: only {remaining} credits remaining, need {page_size} for this fetch — skipped"
        )

    try:
        body = build_theirstack_body(filters)
        r = requests.post(
            SEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise SourceFetchError(f"theirstack: search request failed: {exc}") from exc

    return r.json().get("data", [])
