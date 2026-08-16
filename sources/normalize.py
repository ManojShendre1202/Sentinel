"""
normalize(raw) -> canonical dict per source, matching JobListing's columns
plus a curated `signals` dict (seniority/technology_slugs/salary/etc. —
high-value extras beyond the canonical fields, omitted if absent, no
keyword_slugs — too noisy). raw_payload keeps the untouched original.
Returns None (hard discard) if no apply URL is found.
"""
from typing import Any


def _theirstack_jobspipe_signals(raw: dict[str, Any]) -> dict[str, Any]:
    """Shared signal extraction — TheirStack and JobsPipe return the same
    underlying schema for every field used here."""
    signals: dict[str, Any] = {}

    if raw.get("seniority"):
        signals["seniority"] = raw["seniority"]

    if raw.get("technology_slugs"):
        signals["technology_slugs"] = raw["technology_slugs"]

    if raw.get("salary_string") or raw.get("min_annual_salary_usd") or raw.get("max_annual_salary_usd"):
        signals["salary_usd_range"] = {
            "string": raw.get("salary_string"),
            "min_usd": raw.get("min_annual_salary_usd"),
            "max_usd": raw.get("max_annual_salary_usd"),
        }

    if raw.get("employment_statuses"):
        signals["employment_type"] = raw["employment_statuses"]

    if raw.get("easy_apply") is not None:
        signals["easy_apply"] = raw["easy_apply"]

    if raw.get("work_arrangement"):
        signals["work_arrangement"] = raw["work_arrangement"]

    company_object = raw.get("company_object") or {}
    if company_object.get("industry"):
        signals["company_industry"] = company_object["industry"]
    if company_object.get("employee_count"):
        signals["company_employee_count"] = company_object["employee_count"]

    return signals


def normalize_theirstack(raw: dict[str, Any]) -> dict[str, Any] | None:
    url = raw.get("final_url") or raw.get("url")
    if not url:
        return None
    return {
        "source": "theirstack",
        "external_id": str(raw["id"]),
        "title": raw.get("job_title") or "",
        "company": raw.get("company") or "",
        "location": raw.get("location") or "",
        "remote": bool(raw.get("remote")),
        "url": url,
        "description": raw.get("description") or "",
        "signals": _theirstack_jobspipe_signals(raw),
        "raw_payload": raw,
    }


def normalize_jobspipe(raw: dict[str, Any]) -> dict[str, Any] | None:
    url = raw.get("final_url") or raw.get("url")
    if not url:
        return None
    remote = raw.get("remote")
    if remote is None:
        remote = raw.get("work_arrangement") == "remote"
    return {
        "source": "jobspipe",
        "external_id": str(raw["id"]),
        "title": raw.get("job_title") or "",
        "company": raw.get("company") or "",
        "location": raw.get("location") or "",
        "remote": bool(remote),
        "url": url,
        "description": raw.get("description") or "",
        "signals": _theirstack_jobspipe_signals(raw),
        "raw_payload": raw,
    }


def normalize_adzuna(raw: dict[str, Any]) -> dict[str, Any] | None:
    url = raw.get("redirect_url")
    if not url:
        return None

    signals: dict[str, Any] = {}
    if raw.get("salary_min") or raw.get("salary_max"):
        signals["salary_inr_range"] = {
            "min": raw.get("salary_min"),
            "max": raw.get("salary_max"),
            "is_predicted": raw.get("salary_is_predicted") == "1",
        }
    if raw.get("contract_time"):
        signals["employment_type"] = raw["contract_time"]
    category = raw.get("category") or {}
    if category.get("label"):
        signals["company_industry"] = category["label"]

    return {
        "source": "adzuna",
        "external_id": str(raw["id"]),
        "title": raw.get("title") or "",
        "company": (raw.get("company") or {}).get("display_name") or "",
        "location": (raw.get("location") or {}).get("display_name") or "",
        # Adzuna exposes no remote flag at all (known gap, not a bug) —
        # left False rather than guessed from title/description text.
        "remote": False,
        "url": url,
        "description": raw.get("description") or "",
        "signals": signals,
        "raw_payload": raw,
    }
